"""GitHub-native slash commands hosted in the agent (GH-M1–M4)."""

from raphael_agent.github_commands.config import (
    github_auto_comments_enabled,
    github_check_runs_enabled,
    github_commands_enabled,
)
from raphael_agent.github_commands.handler import handle_issue_comment_event
from raphael_agent.github_commands.parse import parse_command

__all__ = [
    "github_auto_comments_enabled",
    "github_check_runs_enabled",
    "github_commands_enabled",
    "handle_issue_comment_event",
    "parse_command",
]
