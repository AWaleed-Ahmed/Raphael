"""Test-only bootstrap, enabled explicitly for persistence audit runs."""
import os
from importlib.util import find_spec

if os.getenv("RAPHAEL_REPORT_AUDIT_FILE") and find_spec("raphael_agent") is not None:
    from escalation_report_audit import install
    install()
