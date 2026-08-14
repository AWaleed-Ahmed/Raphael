"""Parse ``/raphael <verb> [args]`` from an Issue/PR comment (GH-M1)."""

from __future__ import annotations

from dataclasses import dataclass, field

IMPLEMENTED_VERBS = frozenset({"status", "help", "feedback", "retry", "escalate"})
DEFERRED_VERBS = frozenset({"cancel", "diagnose", "fix"})
ALL_VERBS = IMPLEMENTED_VERBS | DEFERRED_VERBS
WRITE_VERBS = frozenset({"status", "help", "feedback"})
PRIVILEGED_VERBS = frozenset({"retry", "escalate", "cancel", "diagnose", "fix"})
FEEDBACK_OUTCOMES = frozenset({"accepted", "rejected", "edited"})


@dataclass(frozen=True)
class ParsedCommand:
    prefix: str
    verb: str
    args: tuple[str, ...] = field(default_factory=tuple)
    raw: str = ""
    implemented: bool = False
    error: str | None = None

    @property
    def privileged(self) -> bool:
        return self.verb in PRIVILEGED_VERBS

    @property
    def outcome(self) -> str | None:
        if self.verb != "feedback" or not self.args:
            return None
        return self.args[0]


def parse_command(text: str | None, *, prefix: str = "/raphael") -> ParsedCommand | None:
    """Return a parsed command if a line starts with ``prefix``; else None.

    Does not treat ``/raphael accept`` as feedback (locked grammar).
    """
    if not text or not prefix:
        return None
    needle = prefix.strip()
    if not needle:
        return None
    command_line: str | None = None
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith(needle.lower()):
            command_line = stripped
            break
    if command_line is None:
        return None

    rest = command_line[len(needle) :].strip()
    if rest.startswith(":") or rest.startswith(","):
        rest = rest[1:].strip()
    parts = rest.split()
    if not parts:
        return ParsedCommand(
            prefix=needle,
            verb="",
            raw=command_line,
            error="missing_verb",
        )
    verb = parts[0].lower()
    args = tuple(parts[1:])
    if verb not in ALL_VERBS:
        return ParsedCommand(
            prefix=needle,
            verb=verb,
            args=args,
            raw=command_line,
            error="unknown_verb",
        )
    error: str | None = None
    if verb == "feedback":
        if not args:
            error = "feedback_missing_outcome"
        elif args[0].lower() not in FEEDBACK_OUTCOMES:
            error = "feedback_invalid_outcome"
        else:
            args = (args[0].lower(), *args[1:])
    return ParsedCommand(
        prefix=needle,
        verb=verb,
        args=args,
        raw=command_line,
        implemented=verb in IMPLEMENTED_VERBS and error is None,
        error=error,
    )
