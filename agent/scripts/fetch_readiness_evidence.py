"""Rehydrate only locked public source bytes; never execute downloaded code."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
import zlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from raphael_agent.readiness import ReadinessError, digest_file, validate_manifest

HOSTS = {
    "api.github.com",
    "raw.githubusercontent.com",
    "codeload.github.com",
    "github.com",
    "drive.usercontent.google.com",
}
MAX_FILE_BYTES = 1_500_000_000
ROOT = Path(__file__).resolve().parents[2]


def cache_path(root: Path, relative: str) -> Path:
    """Keep downloads and derived reads inside the selected cache."""
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ReadinessError("evidence_outside_cache")
    return path


def write_verified(chunks: Iterable[bytes], item: dict[str, Any], path: Path) -> None:
    """Publish a cache file only after its locked size/hash and ZIP CRC match."""
    if not 0 < item["bytes"] <= MAX_FILE_BYTES:
        raise ReadinessError("source_size_outside_budget")
    path.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256()
    count = crc = 0
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            for data in chunks:
                count += len(data)
                if count > item["bytes"]:
                    raise ReadinessError("source_size_mismatch")
                sha.update(data)
                crc = zlib.crc32(data, crc)
                output.write(data)
            if count != item["bytes"] or sha.hexdigest() != item["sha256"]:
                raise ReadinessError("source_hash_mismatch")
            if "crc32" in item and f"{crc:08x}" != item["crc32"]:
                raise ReadinessError("source_zip_crc_mismatch")
            output.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def projected_bytes(item: dict[str, Any], root: Path) -> bytes:
    """Allow only recorded field projections, never evaluator answer fields."""
    source = cache_path(root, item["derived_from"])
    if item["projection"] == "github_report_body":
        return (json.loads(source.read_text()).get("body") or "").encode()
    if item["projection"] == "csv_instruction":
        with source.open() as stream:
            for row in csv.DictReader(stream):
                if row["task_index"] == item["row_id"]:
                    return (row["instruction"] + "\n").encode()
        raise ReadinessError("original_task_missing")
    raise ReadinessError("unknown_source_projection")


def fetch_item(client: httpx.Client, item: dict[str, Any], root: Path) -> None:
    """Fetch HTTPS originals or locked archive byte ranges with no redirects."""
    path = cache_path(root, item["path"])
    if path.is_file():
        if path.stat().st_size != item["bytes"] or digest_file(path) != item["sha256"]:
            raise ReadinessError("existing_cache_hash_mismatch")
        return
    if "derived_from" in item:
        write_verified([projected_bytes(item, root)], item, path)
        return
    url = item["url"]
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ReadinessError("source_url_not_allowed")
    headers = {}
    if "member" in item:
        start = item["compressed_start"]
        end = start + item["compressed_bytes"] - 1
        if start < 0 or end >= item["archive_bytes"]:
            raise ReadinessError("source_zip_range_invalid")
        url += f"&range_start={start}&range_end={end}"
        headers["Range"] = f"bytes={start}-{end}"
    with client.stream("GET", url, headers=headers, follow_redirects=False) as response:
        response.raise_for_status()
        if "member" in item:
            if (
                response.status_code != 206
                or response.headers.get("content-range")
                != f"bytes {start}-{end}/{item['archive_bytes']}"
            ):
                raise ReadinessError("source_zip_range_mismatch")
            decoder = zlib.decompressobj(-15)

            def inflated() -> Iterable[bytes]:
                compressed = 0
                for chunk in response.iter_bytes(1024 * 1024):
                    compressed += len(chunk)
                    pending = chunk
                    while pending:
                        data = decoder.decompress(pending, 8 * 1024 * 1024)
                        pending = decoder.unconsumed_tail
                        yield data
                yield decoder.flush()
                if (
                    not decoder.eof
                    or decoder.unused_data
                    or compressed != item["compressed_bytes"]
                ):
                    raise ReadinessError("source_zip_stream_invalid")

            write_verified(inflated(), item, path)
        elif item.get("projection") == "canonical_commit_json":
            response.read()
            data = (json.dumps(response.json(), sort_keys=True) + "\n").encode()
            write_verified([data], item, path)
        else:
            write_verified(response.iter_bytes(1024 * 1024), item, path)


def main() -> None:
    """Rehydrate immutable expected bytes, refusing upstream snapshot changes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "agent/fixtures/production_readiness/source-manifest.json",
    )
    parser.add_argument("--cache-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text())
        schema = json.loads(
            (
                ROOT / "agent/fixtures/production_readiness/source-manifest.schema.json"
            ).read_text()
        )
        validate_manifest(manifest, schema)
        args.cache_root.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=180) as client:
            for case in manifest["cases"]:
                for item in case["files"]:
                    fetch_item(client, item, args.cache_root)
                print(case["id"] + ":verified", flush=True)
    except (
        ReadinessError,
        httpx.HTTPError,
        OSError,
        KeyError,
        ValueError,
        zlib.error,
    ) as exc:
        parser.exit(
            1,
            (
                str(exc) + "\n"
                if isinstance(exc, ReadinessError)
                else "source_acquisition_failed\n"
            ),
        )


if __name__ == "__main__":
    main()
