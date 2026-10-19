"""Choose one immutable Ignis reference for every cross-repository CI job."""
from __future__ import annotations

import os
from pathlib import Path
import re


def resolve_ignis_ref(requested: str, version_file: Path) -> str:
    """Use an explicit tag/SHA override, otherwise the committed contract tag."""
    reference = requested.strip()
    if not reference:
        versions = version_file.read_text(encoding="utf-8").split()
        if len(versions) != 1 or not re.fullmatch(r"contracts-v\d+\.\d+\.\d+", versions[0]):
            raise ValueError("CONTRACTS_VERSION must contain exactly one contract tag")
        reference = versions[0]
    if not re.fullmatch(r"(?:contracts-v\d+\.\d+\.\d+|[0-9a-fA-F]{40})", reference):
        raise ValueError("Ignis reference must be a contract tag or full commit SHA")
    return reference


def main() -> None:
    reference = resolve_ignis_ref(
        os.getenv("IGNIS_REF_REQUESTED", ""), Path(__file__).resolve().parents[1] / "CONTRACTS_VERSION"
    )
    print(f"Ignis reference for all paired jobs: {reference}")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"ref={reference}\n")


if __name__ == "__main__":
    main()
