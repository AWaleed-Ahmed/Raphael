[CmdletBinding()]
param(
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$versionPath = Join-Path $repoRoot 'CONTRACTS_VERSION'
$remote = 'https://github.com/AWaleed-Ahmed/Ignis.git'

if (-not (Test-Path -LiteralPath $versionPath -PathType Leaf)) {
    throw 'Missing CONTRACTS_VERSION at repository root.'
}

$versions = @(Get-Content -LiteralPath $versionPath | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($versions.Count -ne 1) {
    throw 'CONTRACTS_VERSION must contain exactly one non-empty tag line.'
}
$version = $versions[0]
if ($version -notmatch '^contracts-v[0-9]+\.[0-9]+\.[0-9]+$') {
    throw "Unsupported contract tag: $version"
}

$remoteLines = @(git ls-remote $remote "refs/tags/$version*")
if ($LASTEXITCODE -ne 0 -or $remoteLines.Count -eq 0) {
    throw "Ignis tag not found: $version"
}
$peeledPattern = "refs/tags/$([regex]::Escape($version))\^\{\}$"
$peeled = $remoteLines | Where-Object { $_ -match $peeledPattern } | Select-Object -First 1
if (-not $peeled) {
    throw "Ignis tag must resolve to a peeled commit: $version"
}
$expectedCommit = ($peeled -split '\s+')[0]
if ($expectedCommit -notmatch '^[0-9a-f]{40}$') {
    throw "Could not resolve commit for tag: $version"
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('raphael-contract-sync-' + [guid]::NewGuid().ToString('N'))
try {
    git clone --quiet --depth 1 --branch $version $remote $tempRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fetch Ignis tag: $version"
    }
    $actualCommit = (git -C $tempRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $actualCommit -ne $expectedCommit) {
        throw "Fetched tag commit mismatch. Expected $expectedCommit, got $actualCommit"
    }

    $source = Join-Path $tempRoot 'contracts\sandbox'
    $destination = Join-Path $repoRoot 'contracts\sandbox'
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw 'Tagged Ignis snapshot has no contracts/sandbox directory.'
    }

    function Get-TreeFiles([string]$Root) {
        if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
            return @()
        }
        return @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force | ForEach-Object {
            $_.FullName.Substring($Root.Length).TrimStart('\', '/').Replace('\', '/')
        } | Sort-Object)
    }

    function Get-TreeHash([string]$Root, [string]$Relative) {
        $path = Join-Path $Root ($Relative -replace '/', '\')
        return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }

    $sourceFiles = @(Get-TreeFiles $source)
    $destinationFiles = @(Get-TreeFiles $destination)
    $drift = @()
    $drift += Compare-Object -ReferenceObject $sourceFiles -DifferenceObject $destinationFiles
    if ($drift.Count -eq 0) {
        foreach ($relative in $sourceFiles) {
            if ((Get-TreeHash $source $relative) -ne (Get-TreeHash $destination $relative)) {
                $drift += $relative
            }
        }
    }

    if ($Check) {
        if ($drift.Count -gt 0) {
            $items = ($drift | Select-Object -First 20 | ForEach-Object { $_.InputObject }) -join ', '
            throw "Vendored contracts drift from $version @ $expectedCommit`: $items"
        }
        Write-Host "Contracts clean: $version @ $expectedCommit"
        exit 0
    }

    if (Test-Path -LiteralPath $destination) {
        Remove-Item -LiteralPath $destination -Recurse -Force
    }
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse -Force
    Write-Host "Synced contracts/sandbox from Ignis $version @ $expectedCommit"
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
