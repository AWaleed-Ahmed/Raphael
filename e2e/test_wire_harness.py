import json
import unittest

from e2e.run_e2e import count_patch_attempts


class PatchAttemptTests(unittest.TestCase):
    def record(self, action_id, job_id="job", verb="deploy_revision", files=None):
        payload = {"job_id": job_id, "action_id": action_id, "verb": verb,
                   "args": {"patch": {"files": ["app.yaml"] if files is None else files}}}
        return {"response": {"body": json.dumps({"messages": [{"payload": payload}]})}}

    def test_replayed_delivery_counts_once(self):
        records = [self.record("first"), self.record("first"), self.record("second")]
        self.assertEqual(count_patch_attempts(records, "job"), 2)

    def test_only_identified_patch_actions_for_exact_job_count(self):
        records = [self.record("other", "job-other"), self.record(None),
                   self.record("initial", verb="deploy_initial"), self.record("empty", files=[]),
                   {"response": {"body": "invalid JSON"}}]
        self.assertEqual(count_patch_attempts(records, "job"), 0)


class EvidenceTests(unittest.TestCase):
    def test_claim_credentials_are_redacted_without_changing_action_identity(self):
        from e2e.trace_redaction import redacted_body
        original = {"claim": {"claim_id": "synthetic-private", "connector_id": "synthetic-owner", "action_id": "public-action", "renewal_sequence": 3}}
        decoded = json.loads(redacted_body(json.dumps(original).encode()))
        self.assertEqual(decoded["claim"]["claim_id"], "[redacted]")
        self.assertEqual(decoded["claim"]["connector_id"], "[redacted]")
        self.assertEqual(decoded["claim"]["action_id"], "public-action")
        self.assertEqual(decoded["claim"]["renewal_sequence"], 3)
        self.assertEqual(redacted_body(b'bad claim_id=synthetic-private'), "[non-JSON body omitted]")

    def test_combined_launcher_uses_persisted_orchestrator_claims(self):
        import os
        from pathlib import Path
        import runpy
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"RAPHAEL_AGENT_DATA_DIR": directory}):
            launcher = runpy.run_path(str(Path(__file__).parent / "combined_launcher.py"))
            self.assertIs(launcher["combined"].state.orchestrator, launcher["dispatch_app"].state.orchestrator)
