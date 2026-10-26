"""Real kind repair of Google's pinned Online Boutique product catalog workload."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
from typing import Any

import yaml

from cluster import CONTEXT, cleanup_namespace, kube, pods, ready, wait_for
from run_kind_verification import CatalogFixture, ROOT, catalog_baseline, commit_fixture, run_case

FIXTURE = ROOT / "e2e/fixtures/google-productcatalog"
HEALTHY_IMAGE = "us-central1-docker.pkg.dev/google-samples/microservices-demo/productcatalogservice:v0.10.4"
ABSENT_IMAGE = HEALTHY_IMAGE.rsplit(":", 1)[0] + ":raphael-proof-absent-20261026-49"


def fixture_manifest() -> str:
    """Check the pinned fixture before generating a single-image fault."""
    manifest = (FIXTURE / "app.yaml").read_text()
    provenance = json.loads((FIXTURE / "upstream.json").read_text())
    assert hashlib.sha256(manifest.encode()).hexdigest() == provenance["fixture_sha256"]
    objects = list(yaml.safe_load_all(manifest))
    deployment = next(item for item in objects if item["kind"] == "Deployment")
    assert deployment["metadata"]["name"] == "productcatalogservice"
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1 and containers[0]["name"] == "server"
    assert containers[0]["image"] == HEALTHY_IMAGE
    assert manifest.count(HEALTHY_IMAGE) == 1
    return manifest


def google_baseline(source_commit: str) -> dict[str, Any]:
    """Use the harness's scoped catalog identity with Google's workload identity."""
    baseline = catalog_baseline(source_commit)
    baseline["runtime_identity"] = {
        "resource_kind": "Deployment", "resource_name": "productcatalogservice",
        "container_images": {"server": HEALTHY_IMAGE},
    }
    return baseline


def main() -> int:
    """Run both real-hook cases and retain independently observed Kubernetes evidence."""
    assert os.getenv("GITHUB_ACTIONS") == "true", "hosted disposable CI only"
    assert kube("config", "current-context").strip() == CONTEXT
    output = ROOT / "e2e/kind-remediation-out/google-productcatalog"
    output.mkdir(parents=True, exist_ok=True)
    manifest = fixture_manifest()
    provenance = json.loads((FIXTURE / "upstream.json").read_text())
    namespace = "raphael-google-baseline-" + uuid.uuid4().hex[:8]
    owned: set[str] = set()
    try:
        with tempfile.TemporaryDirectory(prefix="google-image-proof-") as temp:
            source = Path(temp) / "proof-source"
            seed = Path(temp) / "seed"
            target = seed / "deploy/manifests/app.yaml"
            target.parent.mkdir(parents=True)
            target.write_text(manifest)
            healthy_sha = commit_fixture(seed, source / "healthy")
            target.write_text(manifest.replace(HEALTHY_IMAGE, ABSENT_IMAGE))
            bad_sha = commit_fixture(seed, source / "bad-image")
            kube("create", "namespace", namespace)
            owned.add(namespace)
            kube("apply", "-n", namespace, "-f", str(source / "healthy/deploy/manifests/app.yaml"))
            healthy = wait_for(lambda: next((pod for pod in pods(namespace) if ready(pod)), None),
                               "Google product catalog independently Ready")
            container = healthy["spec"]["containers"][0]
            assert container["name"] == "server" and container["image"] == HEALTHY_IMAGE
            assert healthy["status"]["containerStatuses"][0]["imageID"]
            baseline = google_baseline(healthy_sha)
            (output / "baseline.json").write_text(json.dumps({
                "catalog_row": baseline, "ready_pod": healthy, "upstream": provenance,
                "healthy_fixture_commit": healthy_sha, "failing_fixture_commit": bad_sha,
                "healthy_image": HEALTHY_IMAGE, "absent_image": ABSENT_IMAGE,
                "ignis_revision": os.environ.get("IGNIS_REF"),
                "raphael_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "scope": "Public Google sample with injected fault; loopback catalog, not live ingestion or a production incident.",
            }, indent=2))
            run_case("image-without-provenance", source / "bad-image", bad_sha, output,
                     expected_image=HEALTHY_IMAGE)
            with CatalogFixture(baseline) as catalog:
                run_case("image-with-verified-provenance", source / "bad-image", bad_sha,
                         output, catalog, expected_image=HEALTHY_IMAGE)
                (output / "catalog-requests.json").write_text(json.dumps(catalog.requests, indent=2))
            (output / "summary.json").write_text(json.dumps({
                "passed": True, "upstream": provenance, "fault": "injected absent image tag",
                "positive": "bad_image_reference / fix_finalized; image-only patch; independent Ready Pod",
                "negative": "verified runtime absence without baseline / patch_value_unavailable; no patch or publish",
            }, indent=2))
    finally:
        if namespace in owned:
            cleanup_namespace(namespace, owned)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
