"""Measure an installed runtime with source-linked inputs and bounded local load.

This tool never trains, publishes, runs application code or claims model accuracy.
Long-duration runs are explicit and retain wall-clock resource samples.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import platform
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    """Hash finite structured values without retaining source text in reports."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def quantiles(values: list[float]) -> dict[str, float | None]:
    """Use explicit nearest-rank tails; empty observations are unmeasured."""
    ordered = sorted(values)
    return {
        name: (ordered[max(0, math.ceil(len(ordered) * q) - 1)] if ordered else None)
        for name, q in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99), ("max", 1.0))
    }


def memory_sample() -> dict[str, Any]:
    """Read this process's cgroup, accounting for its entire descendant tree."""
    relative = Path("/proc/self/cgroup").read_text().split("0::", 1)[1].strip()
    root = Path("/sys/fs/cgroup") / relative.lstrip("/")
    result: dict[str, Any] = {"monotonic": time.monotonic(), "cgroup": relative}
    for name in (
        "memory.current",
        "memory.peak",
        "memory.max",
        "memory.swap.max",
        "cpu.max",
        "cpu.stat",
        "memory.events",
        "pids.current",
    ):
        path = root / name
        result[name] = path.read_text().strip() if path.is_file() else None
    result["affinity"] = sorted(os.sched_getaffinity(0))
    return result


def configure(enabled: bool) -> None:
    """Freeze one test scope per process; never mutate scope in worker threads."""
    os.environ.update(
        RAPHAEL_MODEL_ENABLED="1" if enabled else "0",
        RAPHAEL_AGENT_TENANT_ID="fixture-tenant-a",
        RAPHAEL_COMPANY_ID="fixture-company-a",
        RAPHAEL_CLIENT_ID="fixture-client-a1",
        RAPHAEL_LEARNING="0",
        RAPHAEL_LLM_DIAGNOSIS="0",
        RAPHAEL_LLM_PATCH="0",
        RAPHAEL_PUBLISH_MODE="dry_run",
        RAPHAEL_PARTNER_MODE="dry_run",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )


def execute(job: dict[str, Any], model_root: Path) -> dict[str, Any]:
    """Call real gateway methods with request-local diagnostics and untouched data."""
    from raphael_agent.model_gateway import ModelGateway, model_error

    gateway = ModelGateway(model_root)
    name, state = job["capability"], job["state"]
    start = time.perf_counter()
    if name == "failure_classifier":
        result = gateway.classify_failure(state)
    elif name == "candidate_ranker":
        result = gateway.rank_candidates(state, job["candidates"], [])
    elif name == "incident_similarity":
        result = gateway.similar_incidents(state, top_k=3)
    elif name == "trace_anomaly":
        result = gateway.trace_anomaly(state, baseline=None)
    elif name == "patch_selector":
        result = gateway.select_patch(state)
    else:
        raise ValueError("unknown_capability")
    elapsed = (time.perf_counter() - start) * 1000
    error = model_error(gateway)
    return {
        "job_id": job["id"],
        "capability": name,
        "elapsed_ms": elapsed,
        "output_sha256": digest(result),
        "unavailable_reason": error,
        "learned_execution": bool(
            (result or {}).get("learned_execution")
            or (result or {}).get("model", {}).get("learned_execution")
        ),
        "execution_source": (result or {}).get("execution_source"),
        "abstained": bool((result or {}).get("abstained")),
        "policy_allowed": (result or {}).get("policy_allowed"),
    }


def mixed_job(
    index: int, groups: list[list[dict[str, Any]]], model_root: Path
) -> list[dict[str, Any]]:
    """A mixed job runs one original/projection input per capability, sequentially."""
    return [execute(group[index % len(group)], model_root) for group in groups]


def load(
    jobs: list[dict[str, Any]],
    model_root: Path,
    output: Path,
    *,
    concurrency: int,
    warmup: float,
    duration: float,
    period: float,
) -> dict[str, Any]:
    """Run bounded concurrent batches; no unbounded queue or silent request loss.

    Each tick offers `concurrency` mixed jobs. A tick waits for its accepted
    batch before another tick can be accepted, so this is closed-loop load;
    missed scheduled ticks are counted, never silently enqueued.
    """
    if concurrency < 1 or duration <= 0 or warmup < 0 or period <= 0:
        raise ValueError("invalid_load_profile")
    names = sorted({job["capability"] for job in jobs})
    groups = [[j for j in jobs if j["capability"] == name] for name in names]
    baseline = {job["id"]: execute(job, model_root)["output_sha256"] for job in jobs}
    begin = time.monotonic()
    steady = begin + warmup
    end = steady + duration
    latencies: dict[str, list[float]] = {name: [] for name in names}
    counts: Counter[str] = Counter()
    sample_path = output / "resource-series.jsonl"
    cases_path = output / "calls.jsonl"
    output.mkdir(parents=True, exist_ok=True)
    with sample_path.open("x") as resources, cases_path.open(
        "x"
    ) as calls, concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        tick = begin
        batch_index = 0
        while time.monotonic() < end:
            phase = "steady" if time.monotonic() >= steady else "warmup"
            submitted = time.monotonic()
            futures = [
                pool.submit(
                    mixed_job, batch_index * concurrency + n, groups, model_root
                )
                for n in range(concurrency)
            ]
            counts[phase + "_accepted_jobs"] += len(futures)
            for future in futures:
                # Exceptions propagate as a failed experiment, never a success.
                rows = future.result(timeout=60)
                counts[phase + "_completed_jobs"] += 1
                for row in rows:
                    row.update(phase=phase, batch=batch_index)
                    row["serial_match"] = (
                        baseline[row["job_id"]] == row["output_sha256"]
                    )
                    counts[phase + "_output_mismatches"] += not row["serial_match"]
                    reason = row["unavailable_reason"]
                    counts[phase + "_runtime_errors"] += reason not in (
                        None,
                        "disabled_by_environment",
                    )
                    calls.write(json.dumps(row, sort_keys=True) + "\n")
            sample = {
                **memory_sample(),
                "elapsed_seconds": time.monotonic() - begin,
                "phase": phase,
                "batch_seconds": time.monotonic() - submitted,
                "completed_jobs": counts[phase + "_completed_jobs"],
            }
            resources.write(json.dumps(sample, sort_keys=True) + "\n")
            calls.flush()
            resources.flush()
            batch_index += 1
            tick += period
            now = time.monotonic()
            if tick < now:
                missed = math.floor((now - tick) / period) + 1
                counts[phase + "_missed_schedule_ticks"] += missed
                tick += missed * period
            time.sleep(max(0.0, min(tick, end) - time.monotonic()))
    # Quantiles are calculated after steady sampling, so instrumentation does
    # not retain a growing latency list during the memory-stability window.
    with cases_path.open() as source:
        for line in source:
            row = json.loads(line)
            if row["phase"] == "steady":
                latencies[row["capability"]].append(row["elapsed_ms"])
    report = {
        "status": "measured_not_qualified",
        "concurrency": concurrency,
        "warmup_seconds": warmup,
        "steady_seconds": duration,
        "actual_wall_seconds": time.monotonic() - begin,
        "batch_period_seconds": period,
        "traffic": "closed_loop_bounded_batches; one call/capability per mixed job",
        "counts": dict(counts),
        "gateway_latency_ms": {
            name: quantiles(values) for name, values in latencies.items()
        },
        "completed_jobs_per_second": counts["steady_completed_jobs"] / duration,
        "input_bundle_sha256": digest(jobs),
        "python": platform.python_version(),
        "runtime_path": str(__import__("raphael_agent").__file__),
    }
    (output / "load-summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


def warm(jobs: list[dict[str, Any]], root: Path, repeats: int) -> dict[str, Any]:
    """Measure warm real gateway calls, including adaptation/validation."""
    results = {}
    for name in sorted({j["capability"] for j in jobs}):
        group = [j for j in jobs if j["capability"] == name]
        for job in group:
            execute(job, root)
        samples = [execute(group[i % len(group)], root) for i in range(repeats)]
        results[name] = {
            "calls": len(samples),
            "latency_ms": quantiles([s["elapsed_ms"] for s in samples]),
            "learned_calls": sum(s["learned_execution"] for s in samples),
            "unavailable": dict(Counter(s["unavailable_reason"] for s in samples)),
        }
    return results


def main() -> None:
    """Run inside a disposable cgroup with an installed non-editable wheel."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("probe", "warm", "load", "oom", "hold"))
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enabled", action="store_true")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--warmup", type=float, default=600)
    parser.add_argument("--duration", type=float, default=7200)
    parser.add_argument("--period", type=float, default=1)
    parser.add_argument("--repeats", type=int, default=1000)
    args = parser.parse_args()
    configure(args.enabled)

    # Enforce offline inference even if a dependency attempts outbound I/O.
    def offline(event: str, arguments: Any) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
            raise RuntimeError("runtime_network_attempt_denied")

    sys.addaudithook(offline)
    jobs = json.loads(args.jobs.read_text())["jobs"]
    if args.mode == "load":
        report = load(
            jobs,
            args.model_root,
            args.output,
            concurrency=args.concurrency,
            warmup=args.warmup,
            duration=args.duration,
            period=args.period,
        )
    elif args.mode == "warm":
        report = {
            "capabilities": warm(jobs, args.model_root, args.repeats),
            "resources": memory_sample(),
        }
    else:
        report = {
            "calls": [execute(job, args.model_root) for job in jobs],
            "resources": memory_sample(),
            "runtime_path": str(__import__("raphael_agent").__file__),
        }
        if args.mode in {"oom", "hold"}:
            args.output.write_text(
                json.dumps(
                    {"status": "started_not_completed", **report}, sort_keys=True
                )
                + "\n"
            )
            if args.mode == "hold":
                while True:
                    mixed_job(0, [jobs], args.model_root)
            memory = []
            while True:
                memory.append(bytearray(1024 * 1024))
    if args.mode != "load":
        with args.output.open("x") as target:
            target.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "measurement_complete", "mode": args.mode}), flush=True)


if __name__ == "__main__":
    main()
