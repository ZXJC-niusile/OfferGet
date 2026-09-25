import tempfile
import unittest
from pathlib import Path

from core.application_tracker import ApplicationRecord, ApplicationStore, ResumeVersion
from core.resume_version_diff import compare_resume_versions


class TestResumeVersions(unittest.TestCase):
    def test_version_roundtrip_and_immutable_collision_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            with ApplicationStore(Path(tmp) / "versions.db") as store:
                store.save(ApplicationRecord("APP-1", "Example Co", "Engineer"))
                version = ResumeVersion(
                    application_id="APP-1",
                    proposal_id="PROP-1",
                    profile_hash="profile-hash",
                    jd_hash="jd-hash",
                    theme="modern-navy",
                    output_paths={"profile": "profile.json", "pdf": "resume.pdf"},
                    created_at="2026-09-24 15:00:00",
                )
                store.save_resume_version(version)
                self.assertEqual(store.get_resume_version(version.version_id).to_dict(), version.to_dict())
                self.assertEqual(len(store.list_resume_versions("APP-1")), 1)
                store.save_resume_version(version)
                forged = ResumeVersion.from_dict({**version.to_dict(), "label": "changed"})
                forged.version_id = version.version_id
                with self.assertRaisesRegex(ValueError, "collision"):
                    store.save_resume_version(forged)

    def test_version_requires_existing_application_when_linked(self):
        with tempfile.TemporaryDirectory() as tmp:
            with ApplicationStore(Path(tmp) / "versions.db") as store:
                with self.assertRaisesRegex(ValueError, "application_id does not exist"):
                    store.save_resume_version(ResumeVersion(
                        application_id="MISSING",
                        proposal_id="PROP-1",
                        profile_hash="profile-hash",
                    ))

    def test_schema_v7_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "versions.db"
            with ApplicationStore(path) as store:
                with store._get_connection() as conn:
                    self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 7)
                    conn.execute("DROP TABLE resume_versions")
                    conn.execute("PRAGMA user_version = 6")
                    conn.commit()
            with ApplicationStore(path) as migrated:
                with migrated._get_connection() as conn:
                    self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 7)
                    self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE name='resume_versions'").fetchone())

    def test_metadata_diff_is_deterministic_and_does_not_claim_content_diff(self):
        before = ResumeVersion(
            application_id="APP-1", proposal_id="PROP-1", profile_hash="hash-a",
            jd_hash="jd-hash", theme="ats-plain", output_paths={"profile": "a.json", "pdf": "a.pdf"},
            created_at="2026-09-24 15:00:00",
        )
        after = ResumeVersion(
            application_id="APP-1", proposal_id="PROP-2", profile_hash="hash-b",
            jd_hash="jd-hash", theme="modern-navy", output_paths={"profile": "b.json", "html": "b.html"},
            created_at="2026-09-24 16:00:00",
        )
        diff = compare_resume_versions(before, after)
        self.assertTrue(diff["profile_content_changed"])
        self.assertFalse(diff["jd_content_changed"])
        self.assertEqual(diff["outputs"]["added"], ["html"])
        self.assertEqual(diff["outputs"]["removed"], ["pdf"])
        self.assertEqual(diff["outputs"]["changed"], ["profile"])
        self.assertFalse(diff["content_diff_available"])

    def test_artifact_metadata_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "profile.json"
            artifact.write_text("{}", encoding="utf-8")
            from core.artifact import inspect_artifacts, sha256_file
            statuses, hashes = inspect_artifacts({"profile": str(artifact), "pdf": str(Path(tmp) / "missing.pdf")})
            self.assertEqual(statuses, {"profile": "present", "pdf": "missing"})
            self.assertEqual(hashes["profile"], sha256_file(artifact))


if __name__ == "__main__":
    unittest.main()
