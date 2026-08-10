"""Typed HTTP client for the Raphael sandbox controller."""

from __future__ import annotations

import os
from typing import Any

import httpx

from raphael_agent.schema_util import validate_sandbox

DEFAULT_BASE_URL = os.environ.get("RAPHAEL_SANDBOX_URL", "http://127.0.0.1:8090")


class SandboxApiError(Exception):
    """Controller returned an error envelope or non-success status."""

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self.body = body
        message = body.get("error", {}).get("message") if isinstance(body, dict) else None
        super().__init__(message or f"sandbox API error HTTP {status_code}")


class SandboxClient:
    """Agent-facing client for the six sandbox verbs (+ health / GET result).

    Base URL from ``RAPHAEL_SANDBOX_URL`` (default ``http://127.0.0.1:8090``).
    Request/response bodies are validated against ``contracts/sandbox/`` when
    ``validate=True`` (default).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        *,
        validate: bool = True,
    ) -> None:
        from raphael_agent.budgets import sandbox_http_timeout_seconds

        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = float(
            timeout if timeout is not None else sandbox_http_timeout_seconds()
        )
        self.validate = validate

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def _maybe_validate(self, schema_name: str, payload: dict[str, Any]) -> None:
        if self.validate:
            validate_sandbox(schema_name, payload)

    def _raise_for_error(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except Exception:
            body = {"error": {"code": "internal", "message": response.text, "retryable": False}}
        if response.status_code >= 400:
            raise SandboxApiError(
                response.status_code, body if isinstance(body, dict) else {}
            )
        if not isinstance(body, dict):
            raise SandboxApiError(
                response.status_code,
                {
                    "error": {
                        "code": "internal",
                        "message": "non-object body",
                        "retryable": False,
                    }
                },
            )
        return body

    def is_reachable(self) -> bool:
        try:
            self.health()
            return True
        except (httpx.HTTPError, SandboxApiError, OSError):
            return False

    def health(self) -> dict[str, Any]:
        with self._client() as client:
            response = client.get("/health")
            response.raise_for_status()
            return response.json()

    def create_sandbox(self, body: dict[str, Any]) -> dict[str, Any]:
        self._maybe_validate("create_sandbox.request.json", body)
        with self._client() as client:
            response = client.post("/v1/sandboxes", json=body)
            data = self._raise_for_error(response)
        self._maybe_validate("create_sandbox.response.json", data)
        return data

    def deploy_revision(self, sandbox_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._maybe_validate("deploy_revision.request.json", body)
        with self._client() as client:
            response = client.post(f"/v1/sandboxes/{sandbox_id}/deploy", json=body)
            data = self._raise_for_error(response)
        self._maybe_validate("deploy_revision.response.json", data)
        return data

    def observe_failure(
        self, sandbox_id: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = body or {}
        self._maybe_validate("observe_failure.request.json", payload)
        with self._client() as client:
            response = client.post(f"/v1/sandboxes/{sandbox_id}/observe", json=payload)
            data = self._raise_for_error(response)
        self._maybe_validate("observe_failure.response.json", data)
        return data

    def run_validation(self, sandbox_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._maybe_validate("run_validation.request.json", body)
        with self._client() as client:
            response = client.post(f"/v1/sandboxes/{sandbox_id}/validate", json=body)
            data = self._raise_for_error(response)
        self._maybe_validate("validation_results.json", data)
        return data

    def finalize_result(
        self, sandbox_id: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = body or {}
        self._maybe_validate("finalize_result.request.json", payload)
        with self._client() as client:
            response = client.post(f"/v1/sandboxes/{sandbox_id}/finalize", json=payload)
            data = self._raise_for_error(response)
        self._maybe_validate("finalize_result.response.json", data)
        return data

    def get_result(self, sandbox_id: str) -> dict[str, Any]:
        with self._client() as client:
            response = client.get(f"/v1/sandboxes/{sandbox_id}/result")
            data = self._raise_for_error(response)
        self._maybe_validate("validated_fix_record.json", data)
        return data

    def destroy_sandbox(
        self, sandbox_id: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = body or {}
        self._maybe_validate("destroy_sandbox.request.json", payload)
        with self._client() as client:
            response = client.post(f"/v1/sandboxes/{sandbox_id}/destroy", json=payload)
            data = self._raise_for_error(response)
        self._maybe_validate("destroy_sandbox.response.json", data)
        return data
