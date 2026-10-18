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
