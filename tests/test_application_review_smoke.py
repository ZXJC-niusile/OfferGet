import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestApplicationReviewSmoke(unittest.TestCase):
    def test_application_review_accept_and_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db = tmp_path / "applications.db"
            review = tmp_path / "review.json"
            profile_out = tmp_path / "accepted_profile.json"
            resume_dir = tmp_path / "resume"
            base = [sys.executable, str(PROJECT_ROOT / "cli.py")]

            add = subprocess.run(
                base + [
                    "application", "add", "APP-SMOKE", "--db", str(db),
                    "--company", "测试公司", "--role", "后端工程师", "--json",
                ], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(add.returncode, 0, add.stderr)

            review_proc = subprocess.run(
                base + [
                    "review", "examples/sample_ai_jd.txt",
                    "--profile", "examples/candidate_profile.json",
                    "--proposal-db", str(db), "--application-id", "APP-SMOKE",
                    "--output", str(review), "--json",
                ], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(review_proc.returncode, 0, review_proc.stderr)
            proposal_id = json.loads(review.read_text(encoding="utf-8"))["material_proposal"]["proposal_id"]

            detail = subprocess.run(
                base + ["application", "show", "APP-SMOKE", "--db", str(db), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(detail.returncode, 0, detail.stderr)
            self.assertEqual(json.loads(detail.stdout)["proposals"][0]["proposal_id"], proposal_id)

            accepted = subprocess.run(
                base + [
                    "proposal", "accept", proposal_id, "--db", str(db),
                    "--profile", "examples/candidate_profile.json",
                    "--jd", "examples/sample_ai_jd.txt",
                    "--output", str(profile_out), "--build-resume",
                    "--resume-output-dir", str(resume_dir), "--json",
                ], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            accepted_payload = json.loads(accepted.stdout)
            self.assertTrue(profile_out.exists())
            self.assertTrue(Path(accepted_payload["generated_resumes"]["pdf"]).exists())
            self.assertEqual(accepted_payload["resume_version"]["application_id"], "APP-SMOKE")

            snapshot = subprocess.run(
                base + ["application", "snapshot", "APP-SMOKE", "--db", str(db), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
            self.assertIn("profile_fingerprint", json.loads(snapshot.stdout))

            detail_after = subprocess.run(
                base + ["application", "show", "APP-SMOKE", "--db", str(db), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(detail_after.returncode, 0, detail_after.stderr)
            self.assertEqual(len(json.loads(detail_after.stdout)["resume_versions"]), 1)

            versions = subprocess.run(
                base + ["application", "versions", "APP-SMOKE", "--db", str(db), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(versions.returncode, 0, versions.stderr)
            self.assertEqual(len(json.loads(versions.stdout)), 1)


if __name__ == "__main__":
    unittest.main()
