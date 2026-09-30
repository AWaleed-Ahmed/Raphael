"""Reusable Kubernetes cluster management utilities for Raphael E2E testing."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from typing import List, Optional

logger = logging.getLogger("raphael.e2e.cluster")


def run_cmd(args: List[str], check: bool = False, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=check)


def ensure_docker_running() -> bool:
    """Check if Docker daemon is active; attempt systemctl start docker.socket if not."""
    res = run_cmd(["docker", "info"], check=False)
    if res.returncode == 0:
        return True

    logger.info("Docker daemon not responsive; attempting systemctl start docker.socket...")
    run_cmd(["systemctl", "start", "docker.socket"], check=False)
    time.sleep(2)
    res = run_cmd(["docker", "info"], check=False)
    return res.returncode == 0


def ensure_kind_cluster(
    cluster_name: str = "raphael-sandbox",
    node_image: str = "kindest/node:v1.33.1",
    timeout_seconds: int = 180,
) -> str:
    """Ensure a local kind cluster exists and is Ready. Returns the kube context name."""
    if not ensure_docker_running():
        raise RuntimeError("Docker daemon is not running and could not be started.")

    if not shutil.which("kind"):
        raise RuntimeError("kind CLI is not installed or not in PATH.")
    if not shutil.which("kubectl"):
        raise RuntimeError("kubectl CLI is not installed or not in PATH.")

    res = run_cmd(["kind", "get", "clusters"])
    existing = [line.strip() for line in res.stdout.splitlines() if line.strip()]

    context_name = f"kind-{cluster_name}"

    if cluster_name not in existing:
        logger.info(f"Creating kind cluster '{cluster_name}' with image '{node_image}'...")
        create_res = run_cmd(
            ["kind", "create", "cluster", "--name", cluster_name, "--image", node_image],
            timeout=timeout_seconds,
        )
        if create_res.returncode != 0:
            raise RuntimeError(
                f"Failed to create kind cluster '{cluster_name}': {create_res.stderr}\n{create_res.stdout}"
            )
        logger.info(f"Kind cluster '{cluster_name}' created successfully.")
    else:
        logger.info(f"Kind cluster '{cluster_name}' already exists.")

    # Wait for node Ready
    deadline = time.time() + 60
    ready = False
    while time.time() < deadline:
        node_res = run_cmd(["kubectl", "--context", context_name, "get", "nodes", "-o", "json"])
        if node_res.returncode == 0:
            try:
                data = json.loads(node_res.stdout)
                items = data.get("items", [])
                if items:
                    conds = items[0].get("status", {}).get("conditions", [])
                    if any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds):
                        ready = True
                        break
            except Exception:
                pass
        time.sleep(2)

    if not ready:
        raise RuntimeError(f"Cluster '{cluster_name}' node failed to enter Ready state within 60s")

    return context_name


def preload_images(cluster_name: str, images: List[str]) -> None:
    """Pre-pull images directly inside kind node to avoid pull throttling."""
    node_name = f"{cluster_name}-control-plane"
    for img in images:
        logger.info(f"Ensuring image '{img}' is available in kind node '{node_name}'...")
        res = run_cmd(["docker", "exec", node_name, "crictl", "pull", img], timeout=120)
        if res.returncode == 0:
            logger.info(f"Preloaded '{img}' into kind node.")
        else:
            logger.warning(f"Failed to pull '{img}' in kind node: {res.stderr}")


def cleanup_test_namespaces(cluster_name: str, prefix: str = "raphael-run-") -> None:
    """Delete any leftover test namespaces matching prefix."""
    context_name = f"kind-{cluster_name}"
    res = run_cmd(["kubectl", "--context", context_name, "get", "ns", "-o", "jsonpath={.items[*].metadata.name}"])
    if res.returncode != 0:
        return
    ns_list = res.stdout.split()
    for ns in ns_list:
        if ns.startswith(prefix) or ns.startswith("raphael-sb-"):
            logger.info(f"Cleaning test namespace '{ns}'...")
            run_cmd(["kubectl", "--context", context_name, "delete", "ns", ns, "--wait=false"])


def destroy_kind_cluster(cluster_name: str = "raphael-sandbox") -> None:
    """Destroy the kind cluster completely."""
    if not shutil.which("kind"):
        return
    logger.info(f"Deleting kind cluster '{cluster_name}'...")
    run_cmd(["kind", "delete", "cluster", "--name", cluster_name], timeout=120)
