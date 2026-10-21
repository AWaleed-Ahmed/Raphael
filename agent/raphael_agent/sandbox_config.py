"""Trusted operator configuration shared by direct and connector execution."""
import os
import re


def secret_fixture_args() -> dict[str, str]:
    """Select an Ignis-local synthetic fixture set; never infer it from evidence."""
    name = os.getenv("RAPHAEL_SECRET_FIXTURE_SET", "").strip()
    if not name:
        return {}
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", name):
        raise ValueError("RAPHAEL_SECRET_FIXTURE_SET must be a fixture name, not a path")
    return {"secret_fixture_set": name}
