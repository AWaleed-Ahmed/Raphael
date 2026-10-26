"""Reject misleading success evidence for the company workload proof."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_google_image_proof as google
import run_kind_verification as proof
import test_kind_verification as existing_tests


class GoogleImageProofTests(unittest.TestCase):
    def test_pinned_workload_and_single_image_fault(self):
        original = google.fixture_manifest()
        healthy = list(yaml.safe_load_all(original))
        failing = list(yaml.safe_load_all(original.replace(google.HEALTHY_IMAGE, google.ABSENT_IMAGE)))
        expected = copy.deepcopy(healthy)
        deployment = next(item for item in expected if item['kind'] == 'Deployment')
        deployment['spec']['template']['spec']['containers'][0]['image'] = google.ABSENT_IMAGE
        self.assertEqual(expected, failing)
        self.assertEqual({item['kind'] for item in healthy}, {'Deployment', 'Service', 'ServiceAccount'})
        self.assertNotEqual(google.HEALTHY_IMAGE, google.ABSENT_IMAGE)
        self.assertEqual(google.HEALTHY_IMAGE.rsplit(':', 1)[0], google.ABSENT_IMAGE.rsplit(':', 1)[0])
        # Avoid the historical mock detector's sentinel strings.
        self.assertFalse(any(marker in google.ABSENT_IMAGE for marker in ('does-not-exist', ':missing', 'invalid.tag')))

    def test_fixture_tampering_is_rejected(self):
        read_text = Path.read_text
        def tampered(path, *args, **kwargs):
            text = read_text(path, *args, **kwargs)
            return text + '# changed\n' if path.name == 'app.yaml' else text
        with patch.object(Path, 'read_text', tampered), self.assertRaises(AssertionError):
            google.fixture_manifest()

    def test_catalog_binds_google_container_and_observed_release(self):
        baseline = google.google_baseline('a' * 40)
        self.assertEqual(baseline['source_commit_sha'], 'a' * 40)
        self.assertEqual(baseline['runtime_identity'], {
            'resource_kind': 'Deployment', 'resource_name': 'productcatalogservice',
            'container_images': {'server': google.HEALTHY_IMAGE}})

    def test_verifier_requires_google_replacement_and_only_image_change(self):
        result, evidence = existing_tests.KindProofTests().case('image-with-verified-provenance')
        evidence['patch_files'][0]['content'] = 'image: ' + google.HEALTHY_IMAGE + '\n'
        approved = result['run_state']['localization_result']['approved_image_replacement']
        approved['image'] = google.HEALTHY_IMAGE
        with patch.object(proof, 'trace_evidence', return_value=evidence):
            proof.verify_case('image-with-verified-provenance', result, [], {}, True, google.HEALTHY_IMAGE)
            approved['image'] = 'hashicorp/http-echo:1.0'
            with self.assertRaises(AssertionError):
                proof.verify_case('image-with-verified-provenance', result, [], {}, True, google.HEALTHY_IMAGE)
            approved['image'] = google.HEALTHY_IMAGE
            evidence['patch_files'][0]['content'] += 'privileged: true\n'
            with self.assertRaises(AssertionError):
                proof.verify_case('image-with-verified-provenance', result, [], {}, True, google.HEALTHY_IMAGE)

    def test_unverified_google_pull_evidence_stays_unknown(self):
        from raphael_agent.diagnosis import diagnose
        from raphael_agent.patch import propose_patch
        from raphael_agent.patch.templates import TemplateRefusal
        run = {"failure_signature": {"class": "bad_image_reference", "normalized": {
            "reason": "ErrImagePull", "resource_kind": "Deployment",
            "resource_name": "productcatalogservice", "container": "server",
            "attributes": {"image": google.ABSENT_IMAGE}}}, "sandbox_backend": "kubectl"}
        with patch.dict(google.os.environ, {"RAPHAEL_MODEL_ENABLED": "0", "RAPHAEL_LLM_DIAGNOSIS": "0", "RAPHAEL_LEARNING": "0"}):
            classification = diagnose(run)["classification"]
            self.assertEqual(classification["failure_class"], "unknown")
            self.assertEqual(classification["blocked_reason"], "image_pull_evidence_unverified")
            with self.assertRaises(TemplateRefusal):
                propose_patch(run)

    def test_hosted_guard_precedes_cluster_operations(self):
        with patch.dict(google.os.environ, {'GITHUB_ACTIONS': 'false'}), patch.object(google, 'kube') as kube:
            with self.assertRaises(AssertionError):
                google.main()
            kube.assert_not_called()


if __name__ == '__main__':
    unittest.main()
