import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cluster
import run_kind_verification as proof
from run_real_job import cluster_settings


class KindProofTests(unittest.TestCase):
    def test_pending_positive_is_excluded_from_required_checks(self):
        with patch.dict("os.environ", {
            "GITHUB_EVENT_NAME": "pull_request",
            "E2E_INCLUDE_PENDING_BAD_IMAGE_POSITIVE": "false",
        }, clear=True):
            self.assertEqual(proof.selected_cases(), ("probe", "image-without-provenance"))

    def test_pending_positive_is_manual_only_and_requires_explicit_pin(self):
        with patch.dict("os.environ", {
            "GITHUB_EVENT_NAME": "push",
            "E2E_INCLUDE_PENDING_BAD_IMAGE_POSITIVE": "true",
            "E2E_MANUAL_IGNIS_REF": "contracts-v1.4.0",
        }, clear=True), self.assertRaisesRegex(RuntimeError, "manual-dispatch only"):
            proof.selected_cases()

        with patch.dict("os.environ", {
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "E2E_INCLUDE_PENDING_BAD_IMAGE_POSITIVE": "true",
            "E2E_MANUAL_IGNIS_REF": "",
        }, clear=True), self.assertRaisesRegex(RuntimeError, "immutable contracts-vX.Y.Z tag"):
            proof.selected_cases()

        with patch.dict("os.environ", {
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "E2E_INCLUDE_PENDING_BAD_IMAGE_POSITIVE": "true",
            "E2E_MANUAL_IGNIS_REF": "main",
        }, clear=True), self.assertRaisesRegex(RuntimeError, "immutable contracts-vX.Y.Z tag"):
            proof.selected_cases()

    def test_manual_dispatch_can_select_pending_positive_with_explicit_pin(self):
        with patch.dict("os.environ", {
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "E2E_INCLUDE_PENDING_BAD_IMAGE_POSITIVE": "true",
            "E2E_MANUAL_IGNIS_REF": "contracts-v1.4.0",
        }, clear=True):
            self.assertEqual(proof.selected_cases(), (
                "probe", "image-without-provenance", "image-with-verified-provenance",
            ))

    def case(self, label):
        image = label != "probe"
        original = "image: broken\n" if image else "port: 9090\nport: 8080\n"
        patched = "image: hashicorp/http-echo:1.0\n" if image else "port: 8080\nport: 8080\n"
        evidence = {"observed_signature": {"class": "bad_image_reference" if image else "probe_misconfiguration", "reproduced": True},
                    "validation": {"passed": True, "signature_cleared": True},
                    "patch_files": [{"path": "deploy/manifests/app.yaml", "content": patched}],
                    "initial_rendered_files": {"deploy/manifests/app.yaml": original}}
        state = {"sandbox_backend": "kubectl", "publish": {"dry_run": True}, "localization_result": {"approved_image_replacement": {
            "image": "hashicorp/http-echo:1.0", "source": {"healthy_trace_id": "kind-verified-baseline"}}}}
        result = {"job_id": "synthetic", "final_status": "fix_finalized", "run_state": state,
                  "terminal": {"payload": {"instructions": "discard_local_copy"}}}
        if label == "image-without-provenance":
            result["final_status"] = "escalated"
            state["terminal_reason"] = "patch_value_unavailable"
            state.pop("localization_result")
            evidence["observed_signature"]["normalized"] = {
                "resource_kind": "Deployment", "resource_name": "app", "container": "app",
                "attributes": {"image": "hashicorp/http-echo:missing", "image_pull_cause": "not_found",
                               "evidence_source": "runtime", "owner_verified": True, "container_type": "regular"},
            }
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

    def test_missing_baseline_refusal_requires_verified_runtime_evidence(self):
        for source, backend in (("mock_fixture", "mock"), ("mock_fixture", "kubectl"), ("runtime", "mock")):
            result, evidence = self.case("image-without-provenance")
            result["run_state"]["sandbox_backend"] = backend
            evidence["observed_signature"]["normalized"]["attributes"]["evidence_source"] = source
            with self.subTest(source=source, backend=backend), patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
                proof.verify_case("image-without-provenance", result, [], {}, False)

    def test_missing_baseline_refusal_rejects_invalid_owner_and_cause(self):
        for field, value in (("owner_verified", False), ("image_pull_cause", "auth")):
            result, evidence = self.case("image-without-provenance")
            evidence["observed_signature"]["normalized"]["attributes"][field] = value
            with self.subTest(field=field), patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
                proof.verify_case("image-without-provenance", result, [], {}, False)

    def test_missing_baseline_refusal_requires_exact_reason_and_no_approved_image(self):
        result, evidence = self.case("image-without-provenance")
        result["run_state"]["terminal_reason"] = "budget_exhausted"
        with patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
            proof.verify_case("image-without-provenance", result, [], {}, False)
        result["run_state"]["terminal_reason"] = "patch_value_unavailable"
        result["run_state"]["localization_result"] = {"approved_image_replacement": {"image": "synthetic"}}
        with patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
            proof.verify_case("image-without-provenance", result, [], {}, False)

    def test_extra_changed_lines_are_rejected(self):
        result, evidence = self.case("probe")
        evidence["patch_files"][0]["content"] += "privileged: true\n"
        with patch.object(proof, "trace_evidence", return_value=evidence), self.assertRaises(AssertionError):
            proof.verify_case("probe", result, [], {}, True)

    def test_probe_fixture_has_one_observed_fault(self):
        import yaml
        source = Path(__file__).resolve().parent / "fixtures/kind-remediation/probe/deploy/manifests/app.yaml"
        container = yaml.safe_load(source.read_text())["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["ports"][0]["containerPort"], 8080)
        self.assertEqual(container["readinessProbe"]["httpGet"]["port"], 9090)
        self.assertEqual(container["livenessProbe"]["httpGet"]["port"], 8080)

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

    def test_default_smoke_ignores_inherited_real_backend(self):
        with patch.dict(proof.os.environ, {"RAPHAEL_CLUSTER_BACKEND": "kubectl", "RAPHAEL_KUBE_CONTEXT": "customer"}, clear=True):
            self.assertEqual(cluster_settings(), ("mock", None))

    def test_explicit_kind_settings(self):
        with patch.dict(proof.os.environ, {"E2E_CLUSTER_BACKEND": "kind", "E2E_KUBE_CONTEXT": cluster.CONTEXT}, clear=True):
            self.assertEqual(cluster_settings(), ("kind", cluster.CONTEXT))

    def test_real_backend_requires_explicit_context(self):
        with patch.dict(proof.os.environ, {"E2E_CLUSTER_BACKEND": "kind", "RAPHAEL_KUBE_CONTEXT": "customer"}, clear=True):
            with self.assertRaises(ValueError):
                cluster_settings()

    def test_unsupported_backend_is_rejected(self):
        with patch.dict(proof.os.environ, {"E2E_CLUSTER_BACKEND": "kubectl"}, clear=True):
            with self.assertRaises(ValueError):
                cluster_settings()

    def test_hosted_guard_precedes_cluster_operations(self):
        with patch.dict(proof.os.environ, {"GITHUB_ACTIONS": "false"}), patch.object(proof, "kube") as kube:
            with self.assertRaises(AssertionError):
                proof.main()
            kube.assert_not_called()


if __name__ == "__main__":
    unittest.main()
