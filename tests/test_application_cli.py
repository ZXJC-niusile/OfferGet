import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestApplicationCli(unittest.TestCase):
    def test_application_lifecycle_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "applications.db"
            base = [sys.executable, str(PROJECT_ROOT / "cli.py")]
            add = subprocess.run(
                base + ["application", "add", "APP-CLI", "--db", str(db), "--company", "测试公司", "--role", "后端工程师", "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(add.returncode, 0, add.stderr)
            self.assertEqual(json.loads(add.stdout)["status"], "pending")

            status = subprocess.run(
                base + ["application", "status", "APP-CLI", "interview", "--db", str(db), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["status"], "interview")
            self.assertEqual(len(payload["status_history"]), 2)

            listed = subprocess.run(
                base + ["application", "list", "--db", str(db), "--status", "interview", "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(len(json.loads(listed.stdout)), 1)

            outcome = subprocess.run(
                base + [
                    "application", "outcome", "APP-CLI", "--stage", "interview",
                    "--result", "rejected", "--feedback", "系统设计不足",
                    "--reflection", "容量估算不充分", "--next-action", "练习系统设计",
                    "--tags", "system_design,technical_depth", "--occurred-at", "2026-09-24 12:00",
                    "--db", str(db), "--json",
                ], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(outcome.returncode, 0, outcome.stderr)
            outcome_payload = json.loads(outcome.stdout)
            self.assertFalse(outcome_payload["replayed"])
            self.assertEqual(outcome_payload["outcome"]["feedback_tags"], ["system_design", "technical_depth"])

            insights = subprocess.run(
                base + ["application", "insights", "--db", str(db), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(insights.returncode, 0, insights.stderr)
            insight_payload = json.loads(insights.stdout)
            self.assertEqual(insight_payload["total_outcomes"], 1)
            self.assertEqual(insight_payload["by_result"]["rejected"], 1)

    def test_json_errors_use_standard_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "applications.db"
            base = [sys.executable, str(PROJECT_ROOT / "cli.py")]
            missing = subprocess.run(
                base + ["application", "show", "MISSING", "--db", str(db), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(missing.returncode, 1)
            self.assertEqual(json.loads(missing.stdout)["error_type"], "application_not_found")
            self.assertEqual(missing.stderr, "")

            invalid_tags = subprocess.run(
                base + ["application", "outcome", "MISSING", "--stage", "interview", "--result", "rejected", "--tags", "bad_tag", "--db", str(db), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(invalid_tags.returncode, 1)
            self.assertEqual(json.loads(invalid_tags.stdout)["error_type"], "invalid_outcome")


if __name__ == "__main__":
    unittest.main()
