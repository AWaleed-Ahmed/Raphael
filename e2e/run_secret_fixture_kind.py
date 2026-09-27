"""Narrow real-kind proof: configured fixture is consumed, omission prevents startup."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from run_real_job import wait_ready, http_post, trace_records

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = "kind-raphael-fixture-proof"


def command(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.STDOUT, timeout=45)


def kube(*args):
    return command("kubectl", "--context", CONTEXT, *args)


def wait_for(check, description, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.5)
    raise AssertionError(f"timeout: {description}")


def run_case(covered, fixture, sha, output, binary):
    label = "with-fixture" if covered else "without-fixture"
    out = output / label
    out.mkdir(parents=True, exist_ok=True)
    gate = out / "release"
    trace = out / "trace.jsonl"
    env = dict(os.environ)
    for key in ("GITHUB_TOKEN", "RAPHAEL_GITHUB_TOKEN", "RAPHAEL_GITHUB_APP_ID",
                "RAPHAEL_GITHUB_INSTALLATION_ID", "RAPHAEL_GITHUB_APP_PRIVATE_KEY",
                "RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH"):
        env.pop(key, None)
    env.update({
        "RAPHAEL_SECRET_FIXTURE_SET": "payments-test" if covered else "",
        "RAPHAEL_CLUSTER_BACKEND": "kind", "RAPHAEL_KUBE_CONTEXT": CONTEXT,
        "RAPHAEL_LISTEN": "127.0.0.1:8090",
        "RAPHAEL_CONNECTOR_DISPATCH_URL": "http://127.0.0.1:8092",
        "RAPHAEL_CONNECTOR_CONTROLLER_URL": "http://127.0.0.1:8090",
        "RAPHAEL_CONNECTOR_TENANT_ID": "fixture-proof", "RAPHAEL_CONNECTOR_TOKEN": "connector",
        "RAPHAEL_CONNECTOR_POLL_INTERVAL_MS": "200",
        "RAPHAEL_CONNECTOR_HTTP_TIMEOUT_SECONDS": "240",
        "RAPHAEL_DISPATCH_TOKENS": json.dumps({
            "producer": {"tenant_id": "fixture-proof", "role": "producer"},
            "connector": {"tenant_id": "fixture-proof", "role": "connector"}}),
        "RAPHAEL_DATA_DIR": str(out / "ignis-data"),
        "RAPHAEL_AGENT_DATA_DIR": str(out / "agent-data"),
        "RAPHAEL_PARTNER_MODE": "dry_run", "RAPHAEL_PUBLISH_MODE": "dry_run",
        "RAPHAEL_LLM_DIAGNOSIS": "0", "RAPHAEL_LLM_PATCH": "0",
        "RAPHAEL_MODEL_ENABLED": "0", "RAPHAEL_LEARNING": "0",
        "E2E_TRACE_FILE": str(trace), "E2E_INSPECT_GATE": str(gate),
    })
    processes, logs = [], []
    namespace = None
    try:
        for name, argv in (
            ("dispatch", [sys.executable, str(ROOT / "e2e/fixture_dispatch_launcher.py")]),
            ("ignis", [str(binary)]),
        ):
            log = (out / f"{name}.log").open("w", encoding="utf-8")
            logs.append(log)
            processes.append(subprocess.Popen(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT))
            wait_ready("http://127.0.0.1:" + ("8092" if name == "dispatch" else "8090"), timeout=45)
        job_id = str(uuid.uuid4())
        job = {"protocol_version": "1.0", "message_id": str(uuid.uuid4()), "job_id": job_id,
               "kind": "job", "sent_at": "2026-09-27T00:00:00Z", "payload": {
                   "job_id": job_id, "repository": {"clone_url": fixture.as_uri()},
                   "commit_sha": sha, "narrowed_location": {"file_path": "deploy/manifests/app.yaml"},
                   "lease_ttl_seconds": 600}}
        status, response = http_post("http://127.0.0.1:8092/v1/tenants/fixture-proof/jobs", job, "producer")
        assert status == 202, response
        print(f"{label}: queued {job_id}", flush=True)
        def created():
            for row in trace_records(trace):
                request = json.loads(row["request"]["body"] or "{}")
                payload = request.get("payload", {})
                if payload.get("verb") == "create_sandbox" and payload.get("status") == "ok":
                    return payload["result"]
        result = wait_for(created, "real create_sandbox result")
        namespace = result["namespace"]
        assert result["cluster_backend"] != "mock"
        received = gate.with_suffix(".received.json")
        wait_for(received.exists, "real connector deploy result at inspection barrier")
        deployed = json.loads(received.read_text())["payload"]
        assert deployed["status"] == "ok", deployed
        snapshots = []
        def observed():
            pods = json.loads(kube("get", "pods", "-n", namespace, "-o", "json"))
            snapshots.append(pods)
            for pod in pods["items"]:
                statuses = pod.get("status", {}).get("containerStatuses", [])
                for container in statuses:
                    if covered and container.get("ready"):
                        return pod
                    waiting = container.get("state", {}).get("waiting", {})
                    if not covered and waiting.get("reason") == "CreateContainerConfigError":
                        message = waiting.get("message", "")
                        if "payments-db" in message and "not found" in message.lower():
                            assert not container.get("ready")
                            assert not container.get("state", {}).get("running")
                            return pod
        try:
            pod = wait_for(observed, f"{label} Kubernetes readiness/control outcome")
        finally:
            (out / "pod-observations.json").write_text(json.dumps(snapshots, indent=2))
            (out / "events.json").write_text(kube("get", "events", "-n", namespace, "-o", "json"))
        # Read only fixture metadata, never Secret payloads. The readiness probe
        # itself verifies the consumed environment value, without printing it.
        secrets = kube("get", "secrets", "-n", namespace, "-o", "name")
        assert ("secret/payments-db" in secrets.splitlines()) == covered
        (out / "proof.json").write_text(json.dumps({
            "passed": True, "case": label, "job_id": job_id, "sandbox_id": result["sandbox_id"],
            "namespace": namespace, "fixture_commit": sha, "pod": pod,
            "secret_names": secrets.splitlines(),
        }, indent=2))
        print(f"PASS {label}: " + ("Ready; synthetic value verified by readiness exec" if covered
                                   else "CreateContainerConfigError: payments-db not found"), flush=True)
    finally:
        gate.touch()
        for process in reversed(processes):
            process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for log in logs:
            log.close()
        if namespace:
            kube("delete", "namespace", namespace, "--wait=false", "--ignore-not-found=true")


def main():
    assert os.getenv("GITHUB_ACTIONS") == "true", "hosted disposable CI only"
    assert kube("config", "current-context").strip() == CONTEXT
    binary = Path(os.environ["E2E_IGNIS_BIN"]).resolve(strict=True)
    output = ROOT / "e2e/kind-fixture-out"
    output.mkdir(exist_ok=True)
    # Commit a copy of the tracked fixture locally, then let the real connector
    # clone that exact SHA. No public repo or Ignis source modifications needed.
    with tempfile.TemporaryDirectory(prefix="fixture-source-") as temp:
        fixture = Path(temp) / "repo"
        shutil.copytree(ROOT / "e2e/fixtures/secret-consumer", fixture)
        command("git", "init", cwd=fixture)
        command("git", "add", ".", cwd=fixture)
        command("git", "-c", "user.name=Fixture CI", "-c", "user.email=fixture@example.invalid",
                "commit", "-m", "Synthetic secret consumer fixture", cwd=fixture)
        sha = command("git", "rev-parse", "HEAD", cwd=fixture).strip()
        for covered in (True, False):
            run_case(covered, fixture, sha, output, binary)


if __name__ == "__main__":
    main()
