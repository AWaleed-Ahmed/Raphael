"""Operations scoped to the hosted disposable remediation-proof cluster."""
from __future__ import annotations

import json
import subprocess
import time

CONTEXT = "kind-raphael-remediation-proof"


def kube(*args):
    return subprocess.check_output(["kubectl", "--context", CONTEXT, *args],
                                   text=True, stderr=subprocess.STDOUT, timeout=45)


def pods(namespace):
    try:
        return json.loads(kube("get", "pods", "-n", namespace, "-o", "json"))["items"]
    except subprocess.CalledProcessError as exc:
        if "NotFound" in exc.output and namespace in exc.output:
            return []  # Terminal cleanup can remove the namespace before the last sample.
        raise


def ready(pod):
    statuses = pod.get("status", {}).get("containerStatuses", [])
    return bool(statuses) and all(item.get("ready") is True for item in statuses)


def wait_for(check, description, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.2)
    raise AssertionError(f"timeout: {description}")


def cleanup_namespace(namespace, owned):
    if namespace not in owned:
        raise ValueError("refusing cleanup of a namespace not owned by this proof")
    kube("delete", "namespace", namespace, "--ignore-not-found=true", "--wait=false")
