from __future__ import annotations

import json
import unittest

from evals.run_evals import load_scenarios, score_scenario


class EvaluationHarnessTests(unittest.TestCase):
    def test_committed_manifests_validate(self) -> None:
        scenarios = load_scenarios()
        self.assertEqual(
            [scenario["scenario_id"] for scenario in scenarios],
            ["bad_image_reference", "invalid_missing_config", "probe_misconfiguration"],
        )

    def _score(self, *, diagnosis_class: str = "probe_misconfiguration", terminal: str = "fix_finalized", patched: str | None = None):
        manifest = load_scenarios({"probe_misconfiguration"})[0]
        job_id = "job-1"
        original = (
            "containers:\n"
            "        - name: app\n"
            "          readinessProbe:\n"
            "            httpGet:\n"
            "              port: 9090\n"
        )
        patched = patched or original.replace("port: 9090", "port: 8080")
        runner_result = {
            "job_id": job_id,
            "runner_exit_code": 0,
            "final_status": terminal,
            "run_state": {
                "diagnosis": {"classification": {"failure_class": diagnosis_class, "confidence": 0.95}}
            },
        }
        records = [
            {
                "request": {"body": '{"kind":"result","payload":{"job_id":"job-1","verb":"deploy_revision","result":{"rendered_files":[{"path":"deploy/manifests/app.yaml","content":"containers:\\n        - name: app\\n          readinessProbe:\\n            httpGet:\\n              port: 9090\\n"}]}}}'},
                "response": {"body": "{}"},
            },
            {
                "request": {"body": '{"kind":"result","payload":{"job_id":"job-1","verb":"observe_failure","result":{"signature":{"class":"probe_misconfiguration"}}}}'},
                "response": {"body": "{}"},
            },
            {
                "request": {"body": "{}"},
                "response": {"body": json.dumps({"messages": [{"kind": "action", "payload": {"job_id": job_id, "verb": "deploy_revision", "args": {"patch": {"files": [{"path": "deploy/manifests/app.yaml", "content": patched}]}}}}]})},
            },
            {
                "request": {"body": '{"kind":"result","payload":{"job_id":"job-1","verb":"run_validation","result":{"passed":true,"signature_cleared":true}}}'},
                "response": {"body": json.dumps({"messages": [{"kind": "terminal", "payload": {"job_id": job_id, "final_status": terminal, "instructions": "discard_local_copy"}}]})},
            },
        ]
        return score_scenario(manifest, runner_result, records)

    def test_score_uses_wire_evidence_and_runstore_diagnosis(self) -> None:
        score = self._score()
        self.assertTrue(score["passed"])
        self.assertEqual(score["asserted_confidence"], 0.95)
        self.assertTrue(score["was_diagnosis_correct"])

    def test_score_fails_wrong_classification_and_terminal_state(self) -> None:
        score = self._score(diagnosis_class="bad_image_reference", terminal="escalated")
        self.assertFalse(score["passed"])
        self.assertFalse(score["assertions"]["classification_correct"])
        self.assertFalse(score["assertions"]["terminal_state_correct"])

    def test_score_rejects_line_ending_inflated_patch(self) -> None:
        inflated = (
            "containers:\r\n"
            "        - name: app\r\n"
            "          readinessProbe:\r\n"
            "            httpGet:\r\n"
            "              port: 8080\r\n"
        )
        score = self._score(patched=inflated)
        self.assertFalse(score["passed"])
        self.assertFalse(score["assertions"]["patch_scope_correct"])
        self.assertGreater(score["actual"]["patch_changed_line_count"], 2)


if __name__ == "__main__":
    unittest.main()
