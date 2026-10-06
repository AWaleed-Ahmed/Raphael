import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cluster
import run_kind_verification as proof


class KindProofTests(unittest.TestCase):
    def case(self, label):
        image = label != "probe"
        original = "image: broken\n" if image else "port: 9090\nport: 9090\n"
        patched = "image: hashicorp/http-echo:1.0\n" if image else "port: 8080\nport: 8080\n"
        evidence = {"observed_signature": {"class": "bad_image_reference" if image else "probe_misconfiguration", "reproduced": True},
                    "validation": {"passed": True, "signature_cleared": True},
                    "patch_files": [{"path": "deploy/manifests/app.yaml", "content": patched}],
                    "initial_rendered_files": {"deploy/manifests/app.yaml": original}}
        state = {"publish": {"dry_run": True}, "localization_result": {"approved_image_replacement": {
            "image": "hashicorp/http-echo:1.0", "source": {"healthy_trace_id": "kind-verified-baseline"}}}}
        result = {"job_id": "synthetic", "final_status": "fix_finalized", "run_state": state,
                  "terminal": {"payload": {"instructions": "discard_local_copy"}}}
        if label == "image-without-provenance":
            result["final_status"] = "escalated"
            state["terminal_reason"] = "patch_value_unavailable"
            evidence.update(validation=None, patch_files=[])
        return result, evidence

    def test_all_expected_cases(self):
        for label in ("probe", "image-without-provenance", "image-with-verified-provenance"):
            result, evidence = self.case(label)
            with patch.object(proof, "trace_evidence", return_value=evidence):
                proof.verify_case(label, result, [], {}, True)

    def test_success_requires_independent_ready(self):
        result, evidence = self.case("probe")
        with patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
            proof.verify_case("probe", result, [], {}, False)

    def test_initial_ready_cannot_be_failure_proof(self):
        result, evidence = self.case("probe")
        with patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
            proof.verify_case("probe", result, [], {"status": {"containerStatuses": [{"ready": True}]}}, True)

    def test_refusal_cannot_include_patch(self):
        result, evidence = self.case("image-without-provenance")
        result["run_state"]["candidate_patches"] = [{"patch_id": "bad"}]
        with patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
            proof.verify_case("image-without-provenance", result, [], {}, False)

    def test_extra_changed_lines_are_rejected(self):
        result, evidence = self.case("probe")
        evidence["patch_files"][0]["content"] += "privileged: true\n"
        with patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
            proof.verify_case("probe", result, [], {}, True)

    def test_live_pr_url_is_rejected(self):
        result, evidence = self.case("probe")
        result["run_state"]["pull_request_url"] = "https://github.com/customer/repo/pull/99"
        with patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
            proof.verify_case("probe", result, [], {}, True)

    def test_catalog_fixture_requires_scope(self):
        from urllib.request import urlopen
        baseline = {"company_id": "proof-company", "client_id": "proof-client",
                    "service_name": "test-service", "environment": "test"}
        with proof.CatalogFixture(baseline) as catalog:
            query = "company_id=eq.proof-company&client_id=eq.proof-client&service_name=eq.test-service&environment=eq.test"
            with urlopen(catalog.url + "/rest/v1/raphael_healthy_traces?" + query) as response:
                self.assertEqual(json.load(response), [baseline])
            with urlopen(catalog.url + "/rest/v1/raphael_healthy_traces?" + query.replace("eq.test-service", "eq.other")) as response:
                self.assertEqual(json.load(response), [])

    def test_cleanup_is_exact_and_owned(self):
        with patch.object(cluster, "kube") as kube:
            with self.assertRaises(ValueError):
                cluster.cleanup_namespace("someone-elses-test", {"owned"})
            kube.assert_not_called()
            cluster.cleanup_namespace("owned", {"owned"})
            kube.assert_called_once_with("delete", "namespace", "owned", "--ignore-not-found=true", "--wait=false")

    def test_hosted_guard_precedes_cluster_operations(self):
        with patch.dict(proof.os.environ, {"GITHUB_ACTIONS": "false"}), patch.object(proof, "kube") as kube:
            with self.assertRaises(AssertionError):
                proof.main()
            kube.assert_not_called()


if __name__ == "__main__":
    unittest.main()
