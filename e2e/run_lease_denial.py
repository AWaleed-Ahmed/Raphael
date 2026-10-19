"""Real dispatcher/connector/controller cancellation; mock Kubernetes, real child tools.

No production hooks or protocol bypasses are added. A test-only dispatcher denies
renewal after the controller starts a 30-second owned command. The action has an
94-second absolute budget, leaving 22 seconds after the connector cleanup reserve.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

from run_e2e import ROOT, E2E, TENANT, TOKEN, PRODUCER, http_post, wait_ready, make_job, trace_records


def wait_until(predicate, description, seconds=30):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(f"timeout: {description}")


def stopped(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"
    except FileNotFoundError:
        return True


def main():
    assert sys.platform == "linux", "qualification currently supports Linux"
    assert not os.getenv("GITHUB_TOKEN") and not os.getenv("RAPHAEL_GITHUB_TOKEN")
    output = E2E / "lease-denial-out"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lease-denial-") as directory:
        owned = Path(directory)
        source = owned / "source"
        (source / "deploy/manifests").mkdir(parents=True)
        # Reuse the exact deterministic wire fixture (no public GitHub clone).
        from dispatch_server import FIXTURE_YAML
        (source / "deploy/manifests/app.yaml").write_text(FIXTURE_YAML)
        for args in (["git", "init", "--template="], ["git", "add", "."],
                     ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Owned lease fixture"]):
            subprocess.run(args, cwd=source, check=True, capture_output=True)
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        started, denied, late = (owned / name for name in ("started.json", "denied", "late"))
        slow = owned / "slow.py"
        slow.write_text("import json, os, pathlib, subprocess, time\n"
                        "child = subprocess.Popen(['/bin/sleep', '30'])\n"
                        f"pathlib.Path({str(started)!r}).write_text(json.dumps([os.getpid(), child.pid]))\n"
                        "time.sleep(30)\n"
                        f"pathlib.Path({str(late)!r}).write_text('unexpected late success')\n")
        data = owned / "controller"
        agent_data = owned / "agent"
        trace = output / "trace.jsonl"
        trace.unlink(missing_ok=True)
        env = dict(os.environ)
        env.update({"RAPHAEL_DISPATCH_TOKENS": json.dumps({
                        PRODUCER: {"tenant_id": TENANT, "role": "producer"},
                        TOKEN: {"tenant_id": TENANT, "role": "connector"}}),
                    "RAPHAEL_CLUSTER_BACKEND": "mock", "RAPHAEL_LISTEN": "127.0.0.1:8090",
                    "RAPHAEL_CONNECTOR_DISPATCH_URL": "http://127.0.0.1:8092",
                    "RAPHAEL_CONNECTOR_CONTROLLER_URL": "http://127.0.0.1:8090",
                    "RAPHAEL_CONNECTOR_TENANT_ID": TENANT, "RAPHAEL_CONNECTOR_TOKEN": TOKEN,
                    "RAPHAEL_CONNECTOR_POLL_INTERVAL_MS": "100", "RAPHAEL_DATA_DIR": str(data),
                    "RAPHAEL_AGENT_DATA_DIR": str(agent_data), "E2E_TRACE_FILE": str(trace),
                    "RAPHAEL_PARTNER_MODE": "dry_run", "RAPHAEL_PUBLISH_MODE": "dry_run",
                    "E2E_SLOW_COMMAND": shlex.join(["python3", str(slow)]),
                    "E2E_SLOW_STARTED": str(started), "E2E_DENIAL_FILE": str(denied)})
        processes = []
        try:
            with (output / "dispatch.log").open("w") as dispatch_log, (output / "ignis.log").open("w") as ignis_log:
                processes.append(subprocess.Popen([sys.executable, str(E2E / "lease_denial_dispatch.py")], cwd=ROOT, env=env, stdout=dispatch_log, stderr=subprocess.STDOUT))
                wait_ready("http://127.0.0.1:8092")
                processes.append(subprocess.Popen([os.environ["E2E_IGNIS_BIN"]], cwd=ROOT, env=env, stdout=ignis_log, stderr=subprocess.STDOUT))
                wait_ready("http://127.0.0.1:8090")
                job = make_job("e2e-success")
                job["payload"].update(repository={"name": "owned-lease-fixture", "clone_url": source.as_uri()}, commit_sha=sha, lease_ttl_seconds=30)
                status, response = http_post(f"http://127.0.0.1:8092/v1/tenants/{TENANT}/jobs", job, PRODUCER)
                assert status == 202, response
                wait_until(started.exists, "real controller static command")
                pids = json.loads(started.read_text())
                journal = data / "connector-jobs" / f"{job['job_id']}.json"
                record = json.loads(journal.read_text())
                workspace = Path(record["workspace_path"])
                assert workspace.exists() and record["sandbox_id"]
                t0 = time.monotonic()
                wait_until(denied.exists, "renewal denial", seconds=15)
                # Cleanup waits for bounded controller work to release its operation lock.
                wait_until(lambda: not journal.exists(), "journal removal after successful cleanup", seconds=25)
                elapsed = time.monotonic() - t0
                assert elapsed < 27, elapsed
                assert not workspace.exists()
                namespaces = [json.loads(path.read_text()) for path in (data / "mock-namespaces").glob("*.json")]
                assert namespaces and all(row["exists"] is False for row in namespaces)
                assert all(stopped(pid) for pid in pids), pids
                time.sleep(1)
                assert not late.exists()
                records = trace_records(trace)
                requests = [json.loads(row["request"]["body"]) for row in records if row["request"]["path"] == "/v1/results"]
                assert not any(row["payload"]["verb"] in {"run_validation", "finalize_result"} for row in requests)
                receipts = [json.loads(path.read_text()) for path in (data / "controller-actions").glob("*.json")]
                assert not any("passed" in row["response"] for row in receipts), "late validation success receipt"
                state_path = agent_data / "runs" / f"{job['job_id']}.json"
                state = json.loads(state_path.read_text())
                assert not state.get("publish") and not state.get("pull_request_url")
                proof = {"passed": True, "backend": "mock", "processes": "real dispatcher, Rust connector/controller and child tools",
                         "fixture_commit": sha, "job_id": job["job_id"], "cleanup_seconds_after_work_start": elapsed,
                         "renewal_status": 409, "late_result_posts": 0, "workspace_removed": True,
                         "namespace_removed": True, "journal_removed": True, "children_stopped": True,
                         "raphael_revision": os.getenv("GITHUB_SHA"), "ignis_ref": os.getenv("IGNIS_REF")}
                (output / "proof.json").write_text(json.dumps(proof, indent=2))
                print(json.dumps(proof, indent=2))
        finally:
            for process in reversed(processes):
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
