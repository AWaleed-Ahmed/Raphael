"""Failure-path checks for the owned paired qualification harness."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_lease_denial import cleanup_owned_command, stopped, wait_until


@unittest.skipUnless(sys.platform == "linux", "Linux process-group qualification")
class FailureCleanupTests(unittest.TestCase):
    def test_failed_proof_kills_owned_validator_and_descendant(self):
        with tempfile.TemporaryDirectory(prefix="denial-cleanup-") as directory:
            root = Path(directory)
            script, marker = root / "slow.py", root / "pids"
            script.write_text("import json, os, pathlib, subprocess, time\n"
                              "child = subprocess.Popen(['/bin/sleep', '30'])\n"
                              f"pathlib.Path({str(marker)!r}).write_text(json.dumps([os.getpid(),child.pid]))\n"
                              "time.sleep(30)\n")
            process = subprocess.Popen([sys.executable, str(script)], start_new_session=True)
            try:
                wait_until(marker.exists, "owned command marker", seconds=3)
                pids = json.loads(marker.read_text())
                cleanup_owned_command(marker, script)
                process.wait(timeout=3)
                self.assertTrue(all(stopped(pid) for pid in pids))
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, 9)
                    process.wait(timeout=3)

    def test_missing_marker_does_not_target_a_process(self):
        with tempfile.TemporaryDirectory() as directory:
            cleanup_owned_command(Path(directory) / "absent", Path(directory) / "absent-script")
