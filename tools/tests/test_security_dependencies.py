"""Regression checks for the October 2026 HTTPS dependency fixes."""
from pathlib import Path
import json
import ssl
import tomllib
import unittest

import certifi
from pip._vendor import certifi as pip_certifi
import yaml


ROOT = Path(__file__).resolve().parents[2]


class SecurityDependencyTests(unittest.TestCase):
    def test_both_backend_packages_require_the_patched_ca_bundle(self):
        for package in ("agent", "dispatch"):
            with self.subTest(package=package):
                manifest = tomllib.loads((ROOT / package / "pyproject.toml").read_text())
                self.assertIn("certifi>=2026.10.19", manifest["project"]["dependencies"])

    def test_application_and_installer_do_not_trust_the_compromised_root(self):
        for bundle in (certifi, pip_certifi):
            with self.subTest(bundle=bundle.__name__):
                context = ssl.create_default_context(cafile=bundle.where())
                common_names = {
                    value
                    for certificate in context.get_ca_certs()
                    for rdn in certificate["subject"]
                    for key, value in rdn
                    if key == "commonName"
                }
                self.assertNotIn("emSign ECC Root CA - G3", common_names)
                self.assertTrue(context.check_hostname)
                self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_ci_bootstraps_pip_before_installing_backend_packages(self):
        bootstrap = "python -m pip install --require-hashes -r requirements-bootstrap.txt"
        requirements = (ROOT / "requirements-bootstrap.txt").read_text()
        self.assertIn("pip==26.2.2 --hash=sha256:", requirements)
        for filename in ("ci.yml", "cross-repo-e2e.yml"):
            workflow = yaml.safe_load((ROOT / ".github/workflows" / filename).read_text())
            for job_name, job in workflow["jobs"].items():
                commands = "\n".join(step.get("run", "") for step in job["steps"])
                if "python -m pip install -e" in commands:
                    with self.subTest(workflow=filename, job=job_name):
                        self.assertIn(bootstrap, commands)
                        self.assertLess(commands.index(bootstrap), commands.index("python -m pip install -e"))

    def test_frontend_enforces_and_ci_uses_the_patched_runtime(self):
        frontend = ROOT / "frontend"
        manifest = json.loads((frontend / "package.json").read_text())
        lock = json.loads((frontend / "package-lock.json").read_text())
        self.assertEqual(manifest["engines"]["node"], ">=24.22.1 <25")
        self.assertEqual(lock["packages"][""]["engines"], manifest["engines"])
        self.assertEqual((frontend / ".nvmrc").read_text().strip(), "24.22.1")
        self.assertIn("engine-strict=true", (frontend / ".npmrc").read_text())
        workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
        setup = next(step for step in workflow["jobs"]["frontend"]["steps"] if step.get("uses", "").startswith("actions/setup-node@"))
        self.assertEqual(setup["with"]["node-version-file"], "frontend/.nvmrc")
