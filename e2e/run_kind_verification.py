"""Reusable real-cluster (kind) closed loop remediation verification runner.

Executes Raphael remediation scenarios against a live local kind cluster,
verifying that real Kubernetes reports failures, deterministic templates generate
minimal patches, Kubernetes reconciles patched workloads to Ready, and jobs
reach fix_finalized.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E2E = ROOT / "e2e"
EVALS = ROOT / "evals"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from e2e.cluster import (
    cleanup_test_namespaces,
    destroy_kind_cluster,
    ensure_docker_running,
    ensure_kind_cluster,
    preload_images,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("raphael.e2e.kind_verification")

DEFAULT_IMAGES = [
    "hashicorp/http-echo:1.0",
    "docker.io/library/busybox:1.36",
]


def run_eval_scenarios(
    scenarios: list[str],
    ignis_bin: str,
    cluster_context: str,
    output_dir: Path,
) -> bool:
    """Invoke evals/run_evals.py with kind cluster backend and kube context."""
    import subprocess

    cmd = [
        sys.executable,
        str(EVALS / "run_evals.py"),
        "--output-dir",
        str(output_dir),
    ]
    for sc in scenarios:
        cmd.extend(["--scenario", sc])

    env = os.environ.copy()
    env["E2E_IGNIS_BIN"] = ignis_bin
    env["E2E_CLUSTER_BACKEND"] = "kind"
    env["E2E_KUBE_CONTEXT"] = cluster_context
    env["RAPHAEL_CLUSTER_BACKEND"] = "kind"
    env["RAPHAEL_KUBE_CONTEXT"] = cluster_context

    logger.info(f"Executing scenarios {scenarios} against context '{cluster_context}'...")
    res = subprocess.run(cmd, env=env, text=True, check=False)
    return res.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster-name", default=os.getenv("E2E_KIND_CLUSTER", "raphael-sandbox"))
    parser.add_argument(
        "--ignis-bin",
        default=os.getenv(
            "E2E_IGNIS_BIN",
            str(ROOT.parent / "Ignis" / "controller" / "target" / "debug" / "raphael-sandbox-controller"),
        ),
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario to verify (default: probe_misconfiguration, bad_image_reference)",
    )
    parser.add_argument("--output-dir", default=str(EVALS / "out" / "kind-verification"))
    parser.add_argument("--keep-cluster", action="store_true", help="Do not destroy cluster after run")
    parser.add_argument("--teardown-only", action="store_true", help="Tear down kind cluster and exit")
    args = parser.parse_args(argv)

    if args.teardown_only:
        cleanup_test_namespaces(args.cluster_name)
        destroy_kind_cluster(args.cluster_name)
        logger.info("Teardown complete.")
        return 0

    if not Path(args.ignis_bin).is_file():
        logger.error(f"Ignis binary not found at '{args.ignis_bin}'")
        return 1

    if not ensure_docker_running():
        logger.error("Docker daemon is not running.")
        return 1

    context = ensure_kind_cluster(args.cluster_name)
    logger.info(f"Using cluster context: {context}")

    preload_images(args.cluster_name, DEFAULT_IMAGES)
    cleanup_test_namespaces(args.cluster_name)

    scenarios = args.scenario or ["probe_misconfiguration", "bad_image_reference"]
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    passed = run_eval_scenarios(scenarios, args.ignis_bin, context, output_dir)

    cleanup_test_namespaces(args.cluster_name)

    if not args.keep_cluster and not os.getenv("E2E_KEEP_CLUSTER"):
        destroy_kind_cluster(args.cluster_name)
        logger.info(f"Destroyed cluster '{args.cluster_name}'.")

    if passed:
        logger.info("All real-cluster scenarios PASSED.")
        return 0
    else:
        logger.error("One or more real-cluster scenarios FAILED.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
