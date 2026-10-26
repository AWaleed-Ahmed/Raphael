"""Load only release-approved bytes; manifests are verified, never trust roots."""

from __future__ import annotations

import hashlib
import sys
import warnings
from functools import lru_cache
from importlib.metadata import version
from io import BytesIO
from pathlib import Path
from typing import Any

# Release-owned identities, independent of the operator-supplied model directory.
# Tuple: manifest SHA-256, artifact SHA-256, artifact byte count.
TRUSTED_ARTIFACTS = {
    "candidate_ranker": (
        "62123b3688cc14fc41a711b5977c75746d1977ccc16566fd8e0314a4b75b63c1",
        "036eca89dc9bb450d665dab516096f8012fb31775f6e187af6a05db2e1cd6b47",
        37018,
    ),
    "failure_classifier": (
        "594c7cba8a776a81457d65b6130f0fb52f4197f804ae37041dc9c5d515346d0d",
        "c029aca6c4c0ac197b1e26c444fe2883001a46289101b972b3e181502f5b0d80",
        120859,
    ),
    "incident_similarity": (
        "3e5f4bed2ebfdad39b07b707c7f97ba8fa7acbf78439c6b8632065b96158917d",
        "38115467e972fd9498637e33b5a9cfab3f6e08029af8d09f34bb5b707bc45a41",
        4456283,
    ),
    "patch_selector": (
        "b2ee948ca4c4eaf2c8dd9c4bc4e6f42f3bdcaf35841e291305c36fb9605f1c79",
        "ed7a9ed3f9713b64bf102e54e734b445b3b6be3e12df8fede4101f6f15741c49",
        269845,
    ),
    "trace_anomaly": (
        "77c7f1704dc6ae2da3b723105193a78f159167a637740bd844d76d0af67a6670",
        "b946fabc97bb703b4449595126f2c29872e1a6319559fd2de4410f75c8415020",
        3324,
    ),
}

# Qualified by real-artifact tests; other versions fail before deserialization.
RUNTIME_VERSIONS = {
    "joblib": "1.6.0",
    "numpy": "2.5.2",
    "scipy": "1.18.1",
    "scikit-learn": "1.9.0",
}


class ArtifactUnavailable(ValueError):
    """A bounded diagnostic safe to expose through the gateway."""


def check_compatibility() -> None:
    """Reject unqualified Python/library versions before reading pickle data."""
    if sys.version_info[:2] != (3, 12):
        raise ArtifactUnavailable("unsupported_python_version")
    for distribution, expected in RUNTIME_VERSIONS.items():
        if version(distribution) != expected:
            raise ArtifactUnavailable("incompatible_runtime_dependencies")


def load_bundle(root: Path, name: str) -> dict[str, Any]:
    """Load an approved deployment bundle, reusing at most five estimators."""
    return _load_bundle(root.resolve(), name)


@lru_cache(maxsize=5)
def _load_bundle(root: Path, name: str) -> dict[str, Any]:
    check_compatibility()
    if name not in TRUSTED_ARTIFACTS:
        raise ArtifactUnavailable("unknown_model")
    manifest_hash, artifact_hash, artifact_size = TRUSTED_ARTIFACTS[name]
    try:
        with (root / name / "manifest.json").open("rb") as handle:
            manifest = handle.read(65537)
        if hashlib.sha256(manifest).hexdigest() != manifest_hash:
            raise ArtifactUnavailable("manifest_hash_mismatch")
        with (root / name / "model.joblib").open("rb") as handle:
            data = handle.read(artifact_size + 1)
    except OSError as exc:
        raise ArtifactUnavailable("artifact_files_unavailable") from exc
    if len(data) != artifact_size or hashlib.sha256(data).hexdigest() != artifact_hash:
        raise ArtifactUnavailable("artifact_hash_mismatch")
    # Load the SAME bytes we hashed, avoiding a path replacement between checks.
    import joblib
    from sklearn.exceptions import InconsistentVersionWarning

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            value = joblib.load(BytesIO(data))
    except Exception as exc:
        raise ArtifactUnavailable("artifact_deserialization_failed") from exc
    if not isinstance(value, dict) or value.get("format_version") != 1:
        raise ArtifactUnavailable("unsupported_artifact_format")
    return value
