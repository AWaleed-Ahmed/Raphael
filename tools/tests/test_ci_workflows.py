from pathlib import Path
import tempfile
import unittest

import yaml

from tools.resolve_ignis_ref import resolve_ignis_ref

ROOT = Path(__file__).resolve().parents[2]


class IgnisReferenceTests(unittest.TestCase):
    def test_default_reads_committed_contract_version(self):
        self.assertEqual(resolve_ignis_ref("", ROOT / "CONTRACTS_VERSION"), (ROOT / "CONTRACTS_VERSION").read_text().strip())

    def test_immutable_overrides_do_not_depend_on_default_file(self):
        for reference in ("contracts-v1.4.0", "a" * 40):
            with self.subTest(reference=reference):
                self.assertEqual(resolve_ignis_ref(reference, Path("missing")), reference)

    def test_rejects_branches_short_shas_and_output_injection(self):
        for reference in ("main", "f1f3b2c", "x\nref=main", "contracts-v1.4.0\nother"):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                resolve_ignis_ref(reference, Path("missing"))

    def test_default_requires_exactly_one_contract_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            version = Path(directory) / "CONTRACTS_VERSION"
            for value in ("", "contracts-v1.4.0\ncontracts-v1.3.0", "main", "a" * 40):
                version.write_text(value)
                with self.subTest(value=value), self.assertRaises(ValueError):
                    resolve_ignis_ref("", version)

    def test_all_paired_jobs_use_the_shared_resolver(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/cross-repo-e2e.yml").read_text())
        for name in ("secret-fixture-kind", "kind-remediation", "e2e"):
            job = workflow["jobs"][name]
            self.assertIn("resolve-ignis", job["needs"])
            self.assertEqual(job["env"]["IGNIS_REF"], "${{ needs.resolve-ignis.outputs.ref }}")
        resolver = workflow["jobs"]["resolve-ignis"]
        self.assertEqual(resolver["steps"][-1]["env"]["IGNIS_REF_REQUESTED"], "${{ inputs.ignis_ref || github.event.client_payload.ignis_ref }}")

    def test_wire_control_exceeds_its_lease(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/cross-repo-e2e.yml").read_text())
        step = next(s for s in workflow["jobs"]["e2e"]["steps"] if s.get("name") == "Run three-scenario wire-protocol harness")
        self.assertGreater(int(step["env"]["E2E_DIAGNOSE_DELAY_SECONDS"]), int(step["env"]["E2E_LEASE_TTL_SECONDS"]))

    def test_core_ci_runs_workflow_and_evaluation_assertions(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        for module in ("tools.tests.test_ci_workflows", "evals.test_run_evals", "e2e.test_wire_harness", "e2e.test_kind_verification"):
            self.assertIn(module, workflow)
