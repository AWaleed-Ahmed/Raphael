"""Typed GitHub REST client for branch + contents + draft PR (no shell git)."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from raphael_agent.publish.config import (
    committer_email,
    committer_name,
    github_api_base,
    github_token,
    pr_labels,
)


class GitHubApiError(Exception):
    def __init__(self, status_code: int, message: str, body: Any = None) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(message)


class GitHubPublisher:
    """Create agent branch, commit allowlisted files, open draft PR via REST."""

    def __init__(
        self,
        *,
        token: str | None = None,
        api_base: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.token = token if token is not None else github_token()
        self.api_base = (api_base or github_api_base()).rstrip("/")
        self._client = client

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise GitHubApiError(401, "RAPHAEL_GITHUB_TOKEN / GITHUB_TOKEN not set")
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "raphael-agent",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.api_base}{path}"
        if self._client is not None:
            response = self._client.request(
                method, url, headers=self._headers(), **kwargs
            )
        else:
            with httpx.Client(timeout=60.0) as client:
                response = client.request(
                    method, url, headers=self._headers(), **kwargs
                )
        if response.status_code >= 400:
            try:
                body = response.json()
                message = body.get("message") or response.text
            except Exception:  # noqa: BLE001
                body = response.text
                message = response.text
            raise GitHubApiError(response.status_code, str(message), body)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def get_ref_sha(self, owner: str, repo: str, branch: str) -> str:
        data = self._request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
        return data["object"]["sha"]

    def ensure_branch(
        self, owner: str, repo: str, *, branch: str, from_sha: str
    ) -> None:
        try:
            self._request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
            return  # already exists (idempotent)
        except GitHubApiError as exc:
            if exc.status_code != 404:
                raise
        self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": from_sha},
        )

    def put_file(
        self,
        owner: str,
        repo: str,
        *,
        path: str,
        content: str,
        branch: str,
        message: str,
    ) -> dict[str, Any]:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
            "committer": {
                "name": committer_name(),
                "email": committer_email(),
            },
        }
        # If file exists on branch, include sha for update.
        try:
            existing = self._request(
                "GET",
                f"/repos/{owner}/{repo}/contents/{path}",
                params={"ref": branch},
            )
            if isinstance(existing, dict) and existing.get("sha"):
                payload["sha"] = existing["sha"]
        except GitHubApiError as exc:
            if exc.status_code != 404:
                raise
        return self._request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{path}",
            json=payload,
        )

    def find_open_pr(
        self, owner: str, repo: str, *, head_branch: str
    ) -> dict[str, Any] | None:
        head = f"{owner}:{head_branch}"
        data = self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={"state": "open", "head": head, "per_page": 5},
        )
        if isinstance(data, list) and data:
            return data[0]
        return None

    def create_draft_pr(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict[str, Any]:
        existing = self.find_open_pr(owner, repo, head_branch=head)
        if existing:
            return existing
        pr = self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "draft": True,
            },
        )
        labels = pr_labels()
        if labels and pr.get("number"):
            try:
                self._request(
                    "POST",
                    f"/repos/{owner}/{repo}/issues/{pr['number']}/labels",
                    json={"labels": labels},
                )
            except GitHubApiError:
                # Labels are best-effort (may not exist in repo).
                pass
        return pr
