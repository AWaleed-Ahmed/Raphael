from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from raphael_agent.budgets import check_budgets, max_patch_attempts_budget, sandbox_http_timeout_seconds
from raphael_agent.evidence.redaction import redact_evidence_item, redact_text
from raphael_agent.evidence.boundary import bounded_evidence, redact_manifest, redact_value, MAX_ITEMS
from raphael_agent.graph.nodes import (
    node_diagnose,
    node_localize,
    node_patch,
    node_publish_or_escalate,
    node_secret_coverage_gate,
)
from raphael_agent.graph.state import initial_run_state
from raphael_agent.store import RunStore
from raphael_agent.sandbox_config import secret_fixture_args
from raphael_agent.validation import rollout_resource
from raphael_agent.store.patch_content import without_patch_content
from raphael_agent.escalation_validation import escalation_failure_updates

from .patch_store import EphemeralPatchStore
from .protocol import ALLOWED_VERBS, PROTOCOL_VERSION, ProtocolValidationError, get_schemas


Node = Callable[[dict[str, Any]], dict[str, Any]]


class OrchestrationError(ProtocolValidationError):
    """Raised when a connector message cannot advance its job state."""


@dataclass
class AgentHooks:
    """Agent-owned state transitions used by dispatch; tests may inject fakes."""

    diagnose: Node = node_diagnose
    localize: Node = node_localize
    patch: Node = node_patch
    publish: Node = node_publish_or_escalate


@dataclass
class Orchestrator:
    """Deterministic connector job state machine.

    Dispatch owns sequencing, budgets, idempotency, and leases. Diagnosis, localization,
    and patch generation remain in ``agent/`` and are called through ``AgentHooks``.
    """

    store: RunStore | None = None
    hooks: AgentHooks | None = None
    clock: Callable[[], datetime] | None = None
    patch_store: EphemeralPatchStore | None = None

    def __post_init__(self) -> None:
        self.store = self.store or RunStore()
        self.hooks = self.hooks or AgentHooks()
        self.clock = self.clock or (lambda: datetime.now(timezone.utc))
        self.patch_store = self.patch_store or EphemeralPatchStore()
        self.jobs: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _is_active_dispatch_state(state: dict[str, Any]) -> bool:
        dispatch = state.get("dispatch")
        return (
            isinstance(dispatch, dict)
            and dispatch.get("stage") != "terminal"
            and dispatch.get("pending_action") is not None
        )

    @staticmethod
    def _lease_is_expired(state: dict[str, Any], current: datetime) -> bool:
        """Apply the one lease-staleness rule used at startup and while running."""
        dispatch = state["dispatch"]
        ttl = int(dispatch.get("lease_ttl_seconds") or 0)
        if ttl <= 0:
            return False
        last = datetime.fromisoformat(str(dispatch["last_activity_at"]).replace("Z", "+00:00"))
        return (current - last).total_seconds() > ttl

    def _expire_lease(self, state: dict[str, Any]) -> dict[str, Any]:
        """Fail closed using the shared terminal transition for an abandoned job."""
        state["errors"] = list(state.get("errors") or []) + [
            {"code": "job_lease_expired", "message": "connector lease expired", "retryable": False}
        ]
        state["status"] = "failed_closed"
        state["terminal_reason"] = "job_lease_expired"
        terminal = self._terminal(state, "failed")
        self._save(state)
        return terminal

    def rehydrate(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        """Restore valid pending jobs, terminalizing persisted jobs whose lease already expired."""
        current = (now or self.clock()).astimezone(timezone.utc)
        terminals: list[dict[str, Any]] = []
        assert self.store is not None
        for state in self.store.iter_runs():
            if not self._is_active_dispatch_state(state):
                continue
            if self._lease_is_expired(state, current):
                terminals.append(self._expire_lease(state))
                continue
            if state["dispatch"].get("patch_payloads_omitted"):
                terminals.append(self._lost_patch_context(state))
                continue
            self.jobs.setdefault(state["run_id"], state)
        return terminals

    def _lost_patch_context(self, state: dict[str, Any]) -> dict[str, Any]:
        """Never replay metadata as though it were the original executable patch."""
        state["status"] = "failed_closed"
        state["terminal_reason"] = "patch_context_lost_on_restart"
        terminal = self._terminal(state, "failed")
        self._save(state)
        return terminal

    def _now(self) -> str:
        return self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _envelope(self, *, job_id: str | None, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        envelope = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": str(uuid.uuid4()),
            "kind": kind,
            "sent_at": self._now(),
            "payload": payload,
        }
        if job_id is not None:
            envelope["job_id"] = job_id
        get_schemas().validate_envelope(envelope)
        return envelope

    @staticmethod
    def _fingerprint(value: dict[str, Any]) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _repository(job: dict[str, Any]) -> dict[str, Any]:
        source = dict(job.get("repository") or {})
        clone_url = str(source["clone_url"])
        parsed = urlparse(clone_url)
        pieces = [piece for piece in parsed.path.strip("/").split("/") if piece]
        name = str(source.get("name") or (pieces[-1] if pieces else "repository")).removesuffix(".git")
        owner = str(source.get("owner") or (pieces[-2] if len(pieces) > 1 else "customer"))
        return {"owner": owner, "name": name, "clone_url": clone_url}

    def _save(self, state: dict[str, Any]) -> None:
        failure = escalation_failure_updates(state)
        if failure:
            state.update(failure)
            self._terminal(state, "failed")
        state["updated_at"] = self._now()
        assert self.store is not None
        durable = {k: v for k, v in state.items() if k != "rendered_files"}
        self.store.save_run(durable)

    def _state_for_job(self, job: dict[str, Any], *, initial_evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        job_id = job["job_id"]
        repository = self._repository(job)
        narrowed = dict(job["narrowed_location"])
        seed = {
            "run_id": job_id,
            "tenant_id": "connector",
            "trigger": {"kind": "connector_job", "received_at": self._now()},
            "repository": repository,
            "commit_sha": job["commit_sha"],
            "target_environment": job.get("sandbox_profile"),
            "delivery_mode": "draft_pr",
        }
        state = dict(initial_run_state(seed, sandbox_mode="connector"))
        state["narrowed_location"] = narrowed
        state["evidence"] = [
            redact_evidence_item(
                {
                    "evidence_id": f"job-context:{job_id}",
                    "kind": "other",
                    "source": {"system": "other", "ref": job_id},
                    "summary": "narrowed_location=" + json.dumps(narrowed, sort_keys=True),
                    "redacted": False,
                    "provenance": {"collector": "dispatch", "query": "connector job context"},
                    "collected_at": self._now(),
                }
            ),
            *self._sanitize_initial_evidence(initial_evidence or []),
        ]
        state["dispatch"] = {
            # Snapshot operator selection at intake so retries/restarts cannot
            # silently switch fixture sets when process configuration changes.
            **secret_fixture_args(),
            "stage": "create_sandbox",
            "pending_action": None,
            "processed_actions": {},
            "lease_ttl_seconds": int(job.get("lease_ttl_seconds") or 0),
            "last_activity_at": self._now(),
        }
        return state

    def intake(
        self,
        job_envelope: dict[str, Any],
        *,
        tenant_id: str | None = None,
        initial_evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        get_schemas().validate_envelope(job_envelope)
        if job_envelope.get("kind") != "job":
            raise OrchestrationError("job intake requires a job envelope")
        job = job_envelope["payload"]
        job_id = job["job_id"]
        existing = self.jobs.get(job_id)
        if existing is None:
            assert self.store is not None
            persisted = self.store.get_run(job_id)
            if persisted is not None and isinstance(persisted.get("dispatch"), dict):
                existing = persisted
                self.jobs[job_id] = existing
        if existing is not None:
            if tenant_id and existing.get("tenant_id") != tenant_id:
                raise OrchestrationError("job_id belongs to a different tenant")
            if existing.get("dispatch", {}).get("patch_payloads_omitted"):
                return {"messages": [self._lost_patch_context(existing)], "idempotent_replay": True}
            pending = existing.get("dispatch", {}).get("pending_action")
            messages = [pending] if pending else []
            return {"messages": messages, "idempotent_replay": True}

        state = self._state_for_job(job, initial_evidence=initial_evidence)
        if tenant_id:
            state["tenant_id"] = tenant_id
        self.jobs[job_id] = state
        action = self._issue_action(state, "create_sandbox", self._create_args(state))
        self._save(state)
        return {"messages": [action], "idempotent_replay": False}

    def tenant_jobs(self, tenant_id: str) -> list[dict[str, Any]]:
        return [
            state for state in self.jobs.values()
            if state.get("tenant_id") == tenant_id
            and state.get("dispatch", {}).get("stage") != "terminal"
            and state.get("dispatch", {}).get("pending_action") is not None
        ]

    def receive_result(self, result_envelope: dict[str, Any]) -> dict[str, Any]:
        get_schemas().validate_envelope(result_envelope)
        if result_envelope.get("kind") != "result":
            raise OrchestrationError("result handling requires a result envelope")
        payload = result_envelope["payload"]
        job_id = payload["job_id"]
        state = self.jobs.get(job_id)
        if state is None:
            raise OrchestrationError(f"unknown job_id: {job_id}")

        dispatch = state["dispatch"]
        action_id = payload["action_id"]
        fingerprint = self._fingerprint(payload)
        processed = dispatch.setdefault("processed_actions", {})
        if action_id in processed:
            if processed[action_id]["fingerprint"] != fingerprint:
                raise OrchestrationError("action_id replayed with a different result payload")
            return {"messages": [], "idempotent_replay": True}

        pending = dispatch.get("pending_action")
        if not pending or pending["payload"]["action_id"] != action_id:
            raise OrchestrationError("result does not match the currently leased action")
        if pending["payload"]["verb"] != payload["verb"]:
            raise OrchestrationError("result verb does not match the leased action")

        dispatch["last_activity_at"] = self._now()
        stage = dispatch["stage"]
        failure = escalation_failure_updates(state)
        if failure:
            state.update(failure)
            messages = [self._terminal(state, "failed")]
        elif payload["status"] != "ok":
            messages = self._handle_failed_result(state, stage, payload)
        elif stage == "create_sandbox":
            messages = self._after_create(state, payload)
        elif stage == "deploy_initial":
            self._record_rendered_files(state, payload)
            messages = [self._issue_action(state, "observe_failure", {"timeout_seconds": self._capped_timeout(90)})]
        elif stage == "refresh_patch_input":
            self._record_rendered_files(state, payload)
            if not self.patch_store.get_manifests(job_id):
                state["status"] = "escalated"
                state["terminal_reason"] = "patch_input_unavailable"
                messages = [self._terminal(state, "escalated")]
            else:
                messages = self._prepare_patch(state)
        elif stage == "observe_failure":
            messages = self._after_observe(state, payload)
        elif stage == "deploy_patch":
            self._record_rendered_files(state, payload)
            try:
                validation_args = self._validation_args(state)
            except ValueError:
                state["status"] = "failed_closed"
                state["terminal_reason"] = "validation_identity_unavailable"
                messages = [self._terminal(state, "failed")]
            else:
                messages = [self._issue_action(state, "run_validation", validation_args)]
        elif stage == "run_validation":
            result = payload.get("result") or {}
            if result.get("passed") is False or result.get("fail_closed") is True:
                messages = self._handle_failed_result(state, stage, payload, reason="validation_failed")
            else:
                state["validation_results"] = list(state.get("validation_results") or []) + [result]
                messages = [
                    self._issue_action(
                        state,
                        "finalize_result",
                        {"notes": "dispatch orchestrator finalized validated result", "require_patch": True},
                    )
                ]
        elif stage == "finalize_result":
            finalized = payload.get("result") or {}
            if finalized.get("result_id"):
                state["result_id"] = finalized["result_id"]
            if finalized.get("record"):
                state["validated_fix_record"] = finalized["record"]
            self._run_node(self.hooks.publish, state)
            final_status = "fix_finalized"
            if state.get("status") == "failed_closed":
                final_status = "failed"
            elif state.get("status") == "escalated":
                final_status = "escalated"
            messages = [self._terminal(state, final_status)]
        else:
            raise OrchestrationError(f"unsupported pending stage: {stage}")

        processed[action_id] = {"fingerprint": fingerprint, "at": self._now()}
        self._save(state)
        return {"messages": messages, "idempotent_replay": False}

    def reap_expired(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        """Terminalize silent jobs whose connector lease has expired."""
        current = (now or self.clock()).astimezone(timezone.utc)
        terminals: list[dict[str, Any]] = []
        for state in list(self.jobs.values()):
            if not self._is_active_dispatch_state(state):
                continue
            if not self._lease_is_expired(state, current):
                continue
            terminals.append(self._expire_lease(state))
        return terminals

    def _issue_action(self, state: dict[str, Any], verb: str, args: dict[str, Any]) -> dict[str, Any]:
        failure = escalation_failure_updates(state)
        if failure:
            state.update(failure)
            return self._terminal(state, "failed")
        if verb not in ALLOWED_VERBS:
            raise OrchestrationError(f"unsupported action verb: {verb}")
        halt = check_budgets(state, node=verb)
        if halt is not None:
            state["status"] = halt["terminal"]
            state["terminal_reason"] = halt["reason_code"]
            return self._terminal(state, "failed" if halt["terminal"] == "failed_closed" else "escalated")
        job_id = state["run_id"]
        payload = {"job_id": job_id, "action_id": str(uuid.uuid4()), "verb": verb, "args": args}
        action = self._envelope(job_id=job_id, kind="action", payload=payload)
        dispatch = state["dispatch"]
        dispatch["pending_action"] = action
        dispatch["stage"] = {
            "create_sandbox": "create_sandbox",
            "deploy_revision": "deploy_initial" if dispatch.get("stage") == "create_sandbox" else "deploy_patch",
            "observe_failure": "observe_failure",
            "run_validation": "run_validation",
            "finalize_result": "finalize_result",
        }.get(verb, verb)
        state["status"] = "running"
        return action

    def _terminal(self, state: dict[str, Any], final_status: str) -> dict[str, Any]:
        failure = escalation_failure_updates(state)
        if failure:
            state.update(failure)
            final_status = "failed"
        payload = {
            "job_id": state["run_id"],
            "final_status": final_status,
            "instructions": "discard_local_copy",
        }
        terminal = self._envelope(job_id=state["run_id"], kind="terminal", payload=payload)
        state["dispatch"]["pending_action"] = None
        state["dispatch"]["stage"] = "terminal"
        state["dispatch"].pop("patch_payloads_omitted", None)
        state["status"] = "success_draft_pr_ready" if final_status == "fix_finalized" else state.get("status", "failed_closed")
        if final_status != "fix_finalized" and state.get("terminal_reason") is None:
            state["terminal_reason"] = "dispatch_terminal"
        if self.patch_store is not None:
            self.patch_store.purge(state["run_id"])
        # Publication has finished (or the job has stopped). Drop raw output
        # copies too, including rejected proposals and finalized patch records.
        for key in ("candidate_patches", "validated_fix_record"):
            if key in state:
                state[key] = without_patch_content(state[key])
        return terminal

    def _create_args(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            **({"secret_fixture_set": state["dispatch"]["secret_fixture_set"]}
               if state["dispatch"].get("secret_fixture_set") else {}),
            "run_id": state["run_id"],
            "tenant_id": state["tenant_id"],
            "repository": state["repository"],
            "commit_sha": state["commit_sha"],
        }

    @staticmethod
    def _capped_timeout(requested: int) -> int:
        return max(1, min(requested, int(sandbox_http_timeout_seconds())))

    @staticmethod
    def _deploy_args(state: dict[str, Any], patch: dict[str, Any] | None = None) -> dict[str, Any]:
        manifests = state.get("manifests") or {}
        args: dict[str, Any] = {
            "repository_sha": state["commit_sha"],
            "manifests": {"type": manifests.get("type", "yaml"), "path": manifests.get("path", "deploy/manifests")},
            "wait_seconds": Orchestrator._capped_timeout(60),
        }
        if patch:
            files = [
                {"path": item["path"], "content": item["content"]}
                for item in patch.get("files") or []
                if item.get("action") != "delete" and isinstance(item.get("content"), str)
            ]
            if files:
                args["patch"] = {"files": files}
            elif isinstance(patch.get("unified_diff"), str) and patch["unified_diff"].strip():
                args["patch"] = {"unified_diff": patch["unified_diff"]}
        return args

    def _after_create(self, state: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
        result = payload.get("result") or {}
        state["sandbox_id"] = result.get("sandbox_id")
        return [self._issue_action(state, "deploy_revision", self._deploy_args(state))]

    @staticmethod
    def _validation_args(state: dict[str, Any]) -> dict[str, Any]:
        signature = state.get("failure_signature") or {}
        plan: dict[str, Any] = {
            "commands": [],
            "health_checks": [
                {"type": "rollout", "resource": rollout_resource(signature), "mandatory": True, "timeout_seconds": Orchestrator._capped_timeout(60)},
                {"type": "signature_absent", "mandatory": True, "timeout_seconds": Orchestrator._capped_timeout(60)},
            ],
        }
        if signature.get("key"):
            plan["compare_to_signature_key"] = signature["key"]
        return {"plan": plan}

    def _record_rendered_files(self, state: dict[str, Any], payload: dict[str, Any]) -> None:
        result = payload.get("result") or {}
        fidelity = result.get("fidelity") or {}
        report = fidelity.get("secret_coverage") if isinstance(fidelity, dict) else None
        if isinstance(report, dict) and state.get("dispatch", {}).get("stage") == "deploy_initial":
            state["secret_coverage"] = report
        rendered = result.get("rendered_files")
        if isinstance(rendered, list):
            assert self.patch_store is not None
            self.patch_store.save_manifests(state["run_id"], rendered)
            state["dispatch"]["requires_patch_input"] = True
            if state["dispatch"].get("stage") == "deploy_initial":
                # Save only this bounded, redacted copy before observation.
                # Restart may lose patch bytes, but must not lose safety context.
                state["evidence"] = list(state.get("evidence") or []) + self._rendered_diagnosis_evidence(state)

    @staticmethod
    def _redact_value(value: Any) -> Any:
        """Redact string leaves before connector observations reach run state."""
        if isinstance(value, str):
            return redact_text(value)[0]
        if isinstance(value, list):
            return [Orchestrator._redact_value(item) for item in value]
        if isinstance(value, dict):
            return redact_value(value)
        return value

    def _sanitize_initial_evidence(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Accept bridge-only evidence defensively; it never enters the public job envelope."""
        sanitized: list[dict[str, Any]] = []
        for index, item in enumerate(items[:MAX_ITEMS]):
            if not isinstance(item, dict):
                continue
            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
            candidate: dict[str, Any] = {
                "evidence_id": str(item.get("evidence_id") or f"bridge-evidence:{index}"),
                "kind": str(item.get("kind") or "other"),
                "source": {"system": str(source.get("system") or "other")},
                "redacted": False,
                "provenance": {
                    "collector": str(provenance.get("collector") or "ingest-bridge"),
                    "query": str(provenance.get("query") or "same-process ingest evidence"),
                },
                "collected_at": str(item.get("collected_at") or self._now()),
            }
            if isinstance(source.get("ref"), str):
                candidate["source"]["ref"] = source["ref"]
            for key in ("summary", "content_excerpt"):
                if isinstance(item.get(key), str):
                    candidate[key] = item[key]
            sanitized.append(redact_evidence_item(candidate))
        return bounded_evidence(sanitized)

    @staticmethod
    def _path_is_in_scope(path: str, narrowed_path: str) -> bool:
        narrowed = narrowed_path.strip("/") or "."
        candidate = path.strip("/")
        if ".." in path.replace("\\", "/").split("/") or path.startswith(("/", "\\")):
            return False
        return narrowed == "." or candidate == narrowed or candidate.startswith(narrowed + "/")

    def _rendered_diagnosis_evidence(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Expose only bounded, redacted manifest excerpts to diagnosis."""
        narrowed = str((state.get("narrowed_location") or {}).get("file_path") or ".")
        evidence: list[dict[str, Any]] = []
        assert self.patch_store is not None
        for index, item in enumerate(self.patch_store.get_manifests(state["run_id"])):
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            content = item.get("content")
            if not isinstance(path, str) or not isinstance(content, str) or not self._path_is_in_scope(path, narrowed):
                continue
            safe_content = redact_manifest(content)
            evidence.append(
                redact_evidence_item(
                    {
                        "evidence_id": f"rendered-file:{state['run_id']}:{index}",
                        "kind": "manifest",
                        "source": {"system": "sandbox", "ref": path},
                        "summary": f"Rendered manifest: {path}",
                        "content_excerpt": safe_content,
                        "redacted": safe_content != content,
                        "provenance": {"collector": "dispatch", "query": "deploy_revision rendered_files"},
                        "collected_at": self._now(),
                    }
                )
            )
            if len(evidence) >= MAX_ITEMS:
                break
        return bounded_evidence(evidence)

    @staticmethod
    def _observation_evidence(action_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Create connector observation evidence with an honest redaction marker."""
        evidence = redact_evidence_item(
            {
                "evidence_id": f"connector-result:{action_id}",
                "kind": "artifact",
                "summary": json.dumps(result, sort_keys=True),
                # The redaction helper changes this only when it actually redacts text.
                "redacted": redact_value(result) != result,
            }
        )
        evidence["summary"] = json.dumps(redact_value(result), sort_keys=True)
        return bounded_evidence([evidence])[0]

    def _after_observe(self, state: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
        result = payload.get("result") or {}
        signature = redact_value(result.get("signature"))
        state["failure_signature"] = self._redact_value(signature or {})
        state["reproduction_result"] = {
            "reproduced": bool(signature and signature.get("reproduced")),
            "signature_key": (signature or {}).get("key"),
            "message": "connector observation received" if signature else "failure not reproduced in sandbox",
        }
        observation_evidence = self._observation_evidence(payload["action_id"], result)
        state["evidence"] = list(state.get("evidence") or []) + [observation_evidence]
        self._run_node(self.hooks.diagnose, state)
        if state.get("status") in {"escalated", "failed_closed"}:
            return [self._terminal(state, "escalated" if state.get("status") == "escalated" else "failed")]
        state.update(node_secret_coverage_gate(state))
        if state.get("status") == "escalated":
            return [self._terminal(state, "escalated")]
        self._run_node(self.hooks.localize, state)
        if state.get("status") in {"escalated", "failed_closed"}:
            return [self._terminal(state, "escalated" if state.get("status") == "escalated" else "failed")]
        return self._prepare_patch(state)

    def _prepare_patch(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        halt = check_budgets(state, node="patch")
        if halt:
            state["status"] = halt["terminal"]
            state["terminal_reason"] = halt["reason_code"]
            return [self._terminal(state, "escalated")]
        patch_context = dict(state)
        assert self.patch_store is not None
        manifests = self.patch_store.get_manifests(state["run_id"])
        if state["dispatch"].get("requires_patch_input") and not manifests:
            # Rehydration preserves the observation action. Once it completes,
            # reacquire the original revision in the same sandbox before patching.
            action = self._issue_action(state, "deploy_revision", self._deploy_args(state))
            if action["kind"] == "action":
                state["dispatch"]["stage"] = "refresh_patch_input"
            return [action]
        if manifests:
            patch_context["rendered_files"] = manifests
        self._run_node(self.hooks.patch, patch_context)
        patch_context.pop("rendered_files", None)
        state.update(patch_context)
        if state.get("status") in {"escalated", "failed_closed"}:
            return [self._terminal(state, "escalated" if state.get("status") == "escalated" else "failed")]
        active = state.get("active_patch_id")
        patch = next((item for item in state.get("candidate_patches") or [] if item.get("patch_id") == active), None)
        if patch is None:
            state["status"] = "escalated"
            state["terminal_reason"] = "patch_unavailable"
            return [self._terminal(state, "escalated")]
        return [self._issue_action(state, "deploy_revision", self._deploy_args(state, patch))]

    def _handle_failed_result(
        self,
        state: dict[str, Any],
        stage: str,
        payload: dict[str, Any],
        *,
        reason: str | None = None,
    ) -> list[dict[str, Any]]:
        if stage == "observe_failure":
            attempts = dict(state.get("attempt_count") or {})
            attempts["diagnosis"] = int(attempts.get("diagnosis") or 0) + 1
            state["attempt_count"] = attempts
            if attempts["diagnosis"] >= int(state.get("budget_snapshot", {}).get("max_diagnosis_attempts") or 1):
                state["status"] = "escalated"
                state["terminal_reason"] = "budget_exhausted"
                return [self._terminal(state, "escalated")]
            return [self._issue_action(state, "observe_failure", {"timeout_seconds": self._capped_timeout(90)})]

        if stage in {"deploy_patch", "run_validation"}:
            # node_patch owns the increment for each generated patch proposal.
            # A connector failure must only compare that count; incrementing
            # here would charge one logical patch attempt twice.
            attempts = state.get("attempt_count") or {}
            if attempts["patch"] >= max_patch_attempts_budget():
                state["status"] = "escalated"
                state["terminal_reason"] = "budget_exhausted"
                return [self._terminal(state, "escalated")]
            state["status"] = "running"
            state["terminal_reason"] = reason
            return self._prepare_patch(state)

        state["status"] = "failed_closed"
        state["terminal_reason"] = reason or f"{stage}_failed"
        state["errors"] = list(state.get("errors") or []) + [
            {
                "code": state["terminal_reason"],
                "message": ((payload.get("error") or {}).get("message") or f"{stage} failed"),
                "retryable": False,
            }
        ]
        return [self._terminal(state, "failed")]

    @staticmethod
    def _run_node(node: Node, state: dict[str, Any]) -> None:
        failure = escalation_failure_updates(state)
        if failure:
            state.update(failure)
            return
        updates = node(state)
        if updates:
            state.update(updates)
        state.update(escalation_failure_updates(state))
