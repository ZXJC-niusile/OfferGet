import tempfile
import unittest
from pathlib import Path

from core.application_tracker import (
    ApplicationRecord,
    ApplicationStore,
    FEEDBACK_TAGS,
    OutcomeRecord,
    OutcomeResult,
    OutcomeStage,
)
from core.services import ApplicationOutcomeService


class TestApplicationOutcomes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "outcomes.db"

    def _seed_app(self, store, app_id="APP-1"):
        store.save(ApplicationRecord(app_id, "Example Co", "Backend Engineer"))

    def test_outcome_vocabularies_and_validation(self):
        self.assertEqual(OutcomeStage.from_string("面试"), OutcomeStage.INTERVIEW)
        self.assertEqual(OutcomeResult.from_string("未通过"), OutcomeResult.REJECTED)
        self.assertEqual(FEEDBACK_TAGS, {
            "technical_depth", "communication", "system_design", "domain_experience",
            "leadership", "collaboration", "other",
        })
        with self.assertRaises(ValueError):
            OutcomeRecord("APP-1", "unknown-stage", "rejected")
        with self.assertRaises(ValueError):
            OutcomeRecord("APP-1", "interview", "unknown-result")
        with self.assertRaises(ValueError):
            OutcomeRecord("APP-1", "interview", "rejected", feedback_tags=["unrecognized"])

    def test_record_is_idempotent_and_validates_application(self):
        with ApplicationStore(self.db_path) as store:
            self._seed_app(store)
            outcome = OutcomeRecord(
                application_id="APP-1", stage="interview", result="rejected",
                feedback_text="系统设计深度不足", reflection_text="容量估算没有量化",
                next_action_text="练习缓存与分片设计", feedback_tags=["system_design", "technical_depth"],
                occurred_at="2026-09-24 10:00",
            )
            first = store.record_outcome(outcome)
            replay = store.record_outcome(outcome)
            self.assertFalse(first["replayed"])
            self.assertTrue(replay["replayed"])
            self.assertEqual(len(store.list_outcomes("APP-1")), 1)
            self.assertEqual(store.list_outcomes("APP-1")[0].to_dict(), outcome.to_dict())
            with self.assertRaisesRegex(ValueError, "does not exist"):
                store.record_outcome(OutcomeRecord("MISSING", "applied", "no_response"))
            forged = OutcomeRecord("APP-1", "interview", "rejected", occurred_at="2026-09-24 10:00")
            forged.outcome_id = "not-the-content-hash"
            with self.assertRaisesRegex(ValueError, "canonical outcome content"):
                store.record_outcome(forged)

    def test_insights_aggregate_results_stages_and_tags(self):
        with ApplicationStore(self.db_path) as store:
            self._seed_app(store, "APP-1")
            self._seed_app(store, "APP-2")
            store.record_outcome(OutcomeRecord(
                "APP-1", "interview", "rejected", feedback_tags=["system_design", "communication"],
                occurred_at="2026-09-24 10:00",
            ))
            store.record_outcome(OutcomeRecord(
                "APP-2", "interview", "advanced", feedback_tags=["system_design"],
                occurred_at="2026-09-24 11:00",
            ))
            insights = store.outcome_insights()
            self.assertEqual(insights["total_outcomes"], 2)
            self.assertEqual(insights["applications_with_outcomes"], 2)
            self.assertEqual(insights["by_result"], {"advanced": 1, "rejected": 1})
            self.assertEqual(insights["by_stage"], {"interview": 2})
            self.assertEqual(insights["top_feedback_tags"][0], ("system_design", 2))

    def test_schema_v4_migrates_to_v6(self):
        with ApplicationStore(self.db_path) as store:
            with store._get_connection() as conn:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 6)
                columns = {row[1] for row in conn.execute("PRAGMA table_info(application_outcomes)")}
                self.assertIn("outcome_id", columns)
                self.assertIn("feedback_tags_json", columns)
                conn.execute("DROP TABLE application_outcomes")
                conn.execute("DROP TABLE resume_versions")
                conn.execute("PRAGMA user_version = 4")
                conn.commit()
        with ApplicationStore(self.db_path) as migrated:
            with migrated._get_connection() as conn:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 6)
                self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE name='application_outcomes'").fetchone())
                self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE name='resume_versions'").fetchone())

    def test_service_facade(self):
        with ApplicationOutcomeService(self.db_path) as service:
            service.store.save(ApplicationRecord("APP-SVC", "Example Co", "Engineer"))
            result = service.record(OutcomeRecord("APP-SVC", "screening", "advanced"))
            self.assertFalse(result["replayed"])
            self.assertEqual(len(service.list("APP-SVC")), 1)
            self.assertEqual(service.insights()["total_outcomes"], 1)


if __name__ == "__main__":
    unittest.main()
