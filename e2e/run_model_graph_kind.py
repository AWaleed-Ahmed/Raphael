"""Exercise actual model graph hooks through a real disposable kind repair."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from cluster import CONTEXT, kube
from run_kind_verification import (
    ROOT,
    CatalogFixture,
    catalog_baseline,
    commit_fixture,
    run_case,
)


def main() -> None:
    assert os.getenv("GITHUB_ACTIONS") == "true", "disposable hosted CI only"
    assert kube("config", "current-context").strip() == CONTEXT
    output = ROOT / "e2e/kind-remediation-out/model-graph"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="model-graph-kind-") as temporary:
        source = Path(temporary) / "proof-source" / "probe"
        source.parent.mkdir()
        sha = commit_fixture(ROOT / "e2e/fixtures/kind-remediation/probe", source)
        baseline = catalog_baseline(sha)
        baseline.update(company_id="fixture-company-a", client_id="fixture-client-a1")
        with CatalogFixture(baseline) as catalog:
            run_case("probe", source, sha, output, catalog, model_proof=True)


if __name__ == "__main__":
    main()
