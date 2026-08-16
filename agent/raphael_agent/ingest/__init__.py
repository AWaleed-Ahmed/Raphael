"""Ingest package — GitHub webhooks, normalize, policy, persist."""

from __future__ import annotations

from raphael_agent.ingest.apm_webhook import normalize_alertmanager_webhook
from raphael_agent.ingest.github import (
    WebhookAuthError,
    parse_github_webhook,
    verify_github_signature,
)
from raphael_agent.ingest.normalize import normalize_failed_run_event
from raphael_agent.ingest.service import (
    accept_and_run_graph,
    accept_failed_run_event,
    accept_normalized_event,
    should_auto_run_graph,
)

__all__ = [
    "WebhookAuthError",
    "accept_and_run_graph",
    "accept_failed_run_event",
    "accept_normalized_event",
    "normalize_alertmanager_webhook",
    "normalize_failed_run_event",
    "parse_github_webhook",
    "should_auto_run_graph",
    "verify_github_signature",
]
