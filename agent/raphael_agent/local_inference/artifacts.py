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
        "6491bcd97172d3fa408f42d5fc7426d7fbb11a03ea6229b8d057ea49c0f027f2",
        "97628b5467befd828f3b7464ed4aae9fd7eb36a95162468952753fb7ab929327",
        46006,
    ),
    "incident_similarity": (
        "8eda85b8a4486165c66e1103f49203ffeb29d04feb9f986da54af8a9fcb68b54",
        "5fc33e1a21d0e6a600e674ee0a64722e989c491b6e92c602d633f84ef8811644",
        2424029,
    ),
    "patch_selector": (
        "b2ee948ca4c4eaf2c8dd9c4bc4e6f42f3bdcaf35841e291305c36fb9605f1c79",
        "ed7a9ed3f9713b64bf102e54e734b445b3b6be3e12df8fede4101f6f15741c49",
        269845,
    ),
    "trace_anomaly": (
        "37d2bf8ce3d9439934cc7c9f577ed59654e6e5bac9683b4488fd5bad04b89acc",
        "8da4ed8eef50733a39828544cb3e8e0ab648d7ce12cc2efabbd7e845ca97b8a8",
        3045,
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
    if not isinstance(value, dict) or value.get("format_version") != (
        2 if name == "incident_similarity" else 1
    ):
        raise ArtifactUnavailable("unsupported_artifact_format")
    return value
