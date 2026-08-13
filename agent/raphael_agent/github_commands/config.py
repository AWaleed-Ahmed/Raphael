"""GitHub-native slash-command config (GH-M1). Default off."""

from __future__ import annotations

import os


def _flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def github_commands_enabled() -> bool:
    """Master switch. Default off — parsing must not run unless this is 1."""
    return _flag("RAPHAEL_GITHUB_COMMANDS", "0")


def github_auto_comments_enabled() -> bool:
    """Terminal GitHub presentation (GH-010–014 comments, GH-021 labels, GH-041 sticky).

    ``RAPHAEL_GITHUB_AUTO_COMMENTS`` unset → inherit ``RAPHAEL_GITHUB_COMMANDS``.
    Explicit ``0`` disables comments/labels/footer even when commands are on;
    ``1`` enables them without enabling slash-command parse.
    """
    raw = os.environ.get("RAPHAEL_GITHUB_AUTO_COMMENTS")
    if raw is None or raw.strip() == "":
        return github_commands_enabled()
    return _flag("RAPHAEL_GITHUB_AUTO_COMMENTS", "0")


def command_prefix() -> str:
    raw = os.environ.get("RAPHAEL_GITHUB_COMMAND_PREFIX", "/raphael").strip()
    return raw or "/raphael"


def command_rate_limit() -> int:
    raw = os.environ.get("RAPHAEL_GITHUB_COMMAND_RATE_LIMIT", "10").strip() or "10"
    try:
        value = int(raw)
    except ValueError:
        return 10
    return max(1, value)


def command_team_logins() -> frozenset[str]:
    """Privileged actor logins for GH-M1 (no GitHub Teams API yet).

    ``RAPHAEL_GITHUB_COMMAND_TEAM_MEMBERS`` is comma-separated logins.
    ``RAPHAEL_GITHUB_COMMAND_TEAM`` is a team slug; if it contains commas (or a
    single token) it is also treated as login(s) so local tests need no API.
    """
    logins: list[str] = []
    members = os.environ.get("RAPHAEL_GITHUB_COMMAND_TEAM_MEMBERS", "").strip()
    team = os.environ.get("RAPHAEL_GITHUB_COMMAND_TEAM", "").strip()
    if members:
        logins.extend(members.split(","))
    if team:
        logins.extend(team.split(","))
    return frozenset(p.strip().lstrip("@").lower() for p in logins if p.strip())


def bot_logins() -> frozenset[str]:
    names = ["raphael-agent", "raphael-agent[bot]"]
    configured = os.environ.get("RAPHAEL_GITHUB_BOT_LOGIN", "").strip()
    if configured:
        names.append(configured)
        if not configured.lower().endswith("[bot]"):
            names.append(f"{configured}[bot]")
    committer = os.environ.get("RAPHAEL_GIT_COMMITTER_NAME", "").strip()
    if committer:
        names.append(committer)
    return frozenset(n.lower() for n in names if n)
