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
from raphael_agent.graph.nodes import node_diagnose, node_localize, node_patch, node_publish_or_escalate
from raphael_agent.graph.state import initial_run_state
from raphael_agent.store import RunStore

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

    def __post_init__(self) -> None:
        self.store = self.store or RunStore()
        self.hooks = self.hooks or AgentHooks()
        self.clock = self.clock or (lambda: datetime.now(timezone.utc))
        self.jobs: dict[str, dict[str, Any]] = {}

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
        state["updated_at"] = self._now()
        assert self.store is not None
        self.store.save_run(dict(state))

    def _state_for_job(self, job: dict[str, Any]) -> dict[str, Any]:
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
            {
                "evidence_id": f"job-context:{job_id}",
                "kind": "other",
                "summary": "narrowed_location=" + json.dumps(narrowed, sort_keys=True),
                "redacted": True,
            }
        ]
        state["dispatch"] = {
            "stage": "create_sandbox",
            "pending_action": None,
            "processed_actions": {},
            "lease_ttl_seconds": int(job.get("lease_ttl_seconds") or 0),
            "last_activity_at": self._now(),
        }
        return state

    def intake(self, job_envelope: dict[str, Any]) -> dict[str, Any]:
        get_schemas().validate_envelope(job_envelope)
        if job_envelope.get("kind") != "job":
            raise OrchestrationError("job intake requires a job envelope")
        job = job_envelope["payload"]
        job_id = job["job_id"]
        existing = self.jobs.get(job_id)
        if existing is not None:
            pending = existing.get("dispatch", {}).get("pending_action")
            messages = [pending] if pending else []
            return {"messages": messages, "idempotent_replay": True}

        state = self._state_for_job(job)
        self.jobs[job_id] = state
        action = self._issue_action(state, "create_sandbox", self._create_args(state))
        self._save(state)
        return {"messages": [action], "idempotent_replay": False}

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
        if payload["status"] != "ok":
            messages = self._handle_failed_result(state, stage, payload)
        elif stage == "create_sandbox":
            messages = self._after_create(state, payload)
        elif stage == "deploy_initial":
            messages = [self._issue_action(state, "observe_failure", {"timeout_seconds": self._capped_timeout(90)})]
        elif stage == "observe_failure":
            messages = self._after_observe(state, payload)
        elif stage == "deploy_patch":
            messages = [self._issue_action(state, "run_validation", self._validation_args(state))]
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
            dispatch = state["dispatch"]
            if not dispatch.get("pending_action") or dispatch.get("stage") == "terminal":
                continue
            ttl = int(dispatch.get("lease_ttl_seconds") or 0)
            if ttl <= 0:
                continue
            last = datetime.fromisoformat(str(dispatch["last_activity_at"]).replace("Z", "+00:00"))
            if (current - last).total_seconds() <= ttl:
                continue
            state["errors"] = list(state.get("errors") or []) + [
                {"code": "job_lease_expired", "message": "connector lease expired", "retryable": False}
            ]
            state["status"] = "failed_closed"
            state["terminal_reason"] = "job_lease_expired"
            terminals.append(self._terminal(state, "failed"))
            self._save(state)
        return terminals

    def _issue_action(self, state: dict[str, Any], verb: str, args: dict[str, Any]) -> dict[str, Any]:
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
        payload = {
            "job_id": state["run_id"],
            "final_status": final_status,
            "instructions": "discard_local_copy",
        }
        terminal = self._envelope(job_id=state["run_id"], kind="terminal", payload=payload)
        state["dispatch"]["pending_action"] = None
        state["dispatch"]["stage"] = "terminal"
        state["status"] = "success_draft_pr_ready" if final_status == "fix_finalized" else state.get("status", "failed_closed")
        if final_status != "fix_finalized" and state.get("terminal_reason") is None:
            state["terminal_reason"] = "dispatch_terminal"
        return terminal

    def _create_args(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
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
                {"type": "rollout", "resource": "deployment/target", "mandatory": True, "timeout_seconds": Orchestrator._capped_timeout(60)},
                {"type": "signature_absent", "mandatory": True, "timeout_seconds": Orchestrator._capped_timeout(60)},
            ],
        }
        if signature.get("key"):
            plan["compare_to_signature_key"] = signature["key"]
        return {"plan": plan}

    def _after_observe(self, state: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
        result = payload.get("result") or {}
        signature = result.get("signature")
        state["failure_signature"] = signature or {}
        state["reproduction_result"] = {
            "reproduced": bool(signature),
            "signature_key": (signature or {}).get("key"),
            "message": "connector observation received",
        }
        state["evidence"] = list(state.get("evidence") or []) + [
            {
                "evidence_id": f"connector-result:{payload['action_id']}",
                "kind": "artifact",
                "summary": json.dumps(result, sort_keys=True),
                "redacted": True,
            }
        ]
        self._run_node(self.hooks.diagnose, state)
        if state.get("status") in {"escalated", "failed_closed"}:
            return [self._terminal(state, "escalated" if state.get("status") == "escalated" else "failed")]
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
        self._run_node(self.hooks.patch, state)
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
            attempts = dict(state.get("attempt_count") or {})
            attempts["patch"] = int(attempts.get("patch") or 0) + 1
            state["attempt_count"] = attempts
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
        updates = node(state)
        if updates:
            state.update(updates)
