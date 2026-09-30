"""
Comprehensive Test Suite for OfferGet Application Tracker & Resume Versioning.
Consolidates:
1. Evidence Graph monotonic state machine and application gate checks.
2. Evidence snapshot creation, immutable fingerprinting, and ATS score anchoring.
3. SQLite ApplicationStore schema migrations (v1 -> v7) and persistent storage.
4. Application outcome logging, feedback tags, and conversion insights.
5. Application tracker CLI workflows and standard error handling contracts.
6. Resume versioning, immutable collision guards, and version diff analysis.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from core.application_tracker import (
    ApplicationRecord,
    ApplicationStore,
    AppStatus,
    FEEDBACK_TAGS,
    OutcomeRecord,
    OutcomeResult,
    OutcomeStage,
    ResumeVersion,
    create_evidence_snapshot,
)
from core.artifacts import inspect_artifacts, sha256_file
from core.evidence.graph import (
    EvidenceGraph,
    EvidenceNode,
    EvidenceNodeState,
)
from core.resume_version_diff import compare_resume_versions
from core.services import ApplicationOutcomeService


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
# 1. Evidence Graph State Machine & Readiness Gate
# ============================================================================

class TestEvidenceGraphStateMachine(unittest.TestCase):
    """Verifies the Evidence Graph finite state machine and application gate checks."""

    def test_linear_monotonic_progression(self):
        graph = EvidenceGraph()
        node = graph.add_claim("主导基于 Raft 协议的高可用元数据集群设计与实现")
        self.assertEqual(node.state, EvidenceNodeState.DRAFT)
        self.assertEqual(len(node.history), 0)

        # 1. Advance to VERIFIED
        v_node = graph.verify_claim(node.claim_id, source_ids=["SRC-GIT-01"], note="代码提交已核对")
        self.assertEqual(v_node.state, EvidenceNodeState.VERIFIED)
        self.assertIn("SRC-GIT-01", v_node.source_ids)
        self.assertEqual(len(v_node.history), 1)
        self.assertEqual(v_node.history[0]["to_state"], "verified")

        # 2. Advance to GROUNDED
        g_node = graph.ground_claim(node.claim_id, scope="分布式存储系统研发", note="经历范围绑定")
        self.assertEqual(g_node.state, EvidenceNodeState.GROUNDED)
        self.assertEqual(g_node.scope, "分布式存储系统研发")
        self.assertEqual(len(g_node.history), 2)

        # 3. Advance to USED_IN_RESUME
        u_node = graph.use_in_resume(node.claim_id, note="选入代表作第一条")
        self.assertEqual(u_node.state, EvidenceNodeState.USED_IN_RESUME)
        self.assertEqual(len(u_node.history), 3)

        # 4. Advance to INTERVIEW_DEFENDED
        d_node = graph.defend_claim(node.claim_id, rounds=2, note="攻防模拟追问2轮通过")
        self.assertEqual(d_node.state, EvidenceNodeState.INTERVIEW_DEFENDED)
        self.assertEqual(d_node.defended_rounds, 2)
        self.assertEqual(len(d_node.history), 4)

    def test_illegal_state_transitions_rejected(self):
        graph = EvidenceGraph()
        node = graph.add_claim("未经任何核验的高并发优化主张")

        # Cannot skip directly from DRAFT to USED_IN_RESUME
        with self.assertRaises(ValueError):
            node.advance(EvidenceNodeState.USED_IN_RESUME)

        # Cannot skip from DRAFT to INTERVIEW_DEFENDED
        with self.assertRaises(ValueError):
            node.advance(EvidenceNodeState.INTERVIEW_DEFENDED)

        # Verify it
        graph.verify_claim(node.claim_id)
        # Cannot jump backwards from VERIFIED to DRAFT
        with self.assertRaises(ValueError):
            graph.get_node(node.claim_id).advance(EvidenceNodeState.DRAFT)

        # Invalidate it
        graph.invalidate_claim(node.claim_id, reason="发现基线数据造假")
        self.assertEqual(graph.get_node(node.claim_id).state, EvidenceNodeState.INVALIDATED)

        # Terminal state: cannot advance from INVALIDATED to VERIFIED or GROUNDED
        with self.assertRaises(ValueError):
            graph.get_node(node.claim_id).advance(EvidenceNodeState.VERIFIED)

    def test_grounding_requires_explicit_scope(self):
        graph = EvidenceGraph()
        node = graph.add_claim("微服务服务治理")
        graph.verify_claim(node.claim_id)

        with self.assertRaises(ValueError):
            graph.ground_claim(node.claim_id, scope="")

        with self.assertRaises(ValueError):
            graph.ground_claim(node.claim_id, scope="   ")

    def test_empty_claims_and_invalid_defense_rounds_are_rejected(self):
        graph = EvidenceGraph()
        with self.assertRaises(ValueError):
            graph.add_claim("   ")
        node = graph.add_claim("有效主张")
        graph.verify_claim(node.claim_id)
        graph.ground_claim(node.claim_id, scope="项目A")
        graph.use_in_resume(node.claim_id)
        with self.assertRaises(ValueError):
            graph.defend_claim(node.claim_id, rounds=0)

    def test_can_apply_gate_and_readiness_report(self):
        graph = EvidenceGraph()

        # Empty graph cannot apply
        ready, reasons = graph.can_apply()
        self.assertFalse(ready)
        self.assertTrue(any("没有经过核验" in r for r in reasons))

        c1 = graph.add_claim("主张1")
        ready, _ = graph.can_apply()
        self.assertFalse(ready)

        graph.verify_claim(c1.claim_id)
        verified_only_ready, verified_only_reasons = graph.can_apply()
        self.assertFalse(verified_only_ready)
        self.assertTrue(any("经历级锚定" in reason for reason in verified_only_reasons))
        graph.ground_claim(c1.claim_id, scope="项目A")
        graph.use_in_resume(c1.claim_id)

        ready, reasons = graph.can_apply()
        self.assertTrue(ready)
        self.assertEqual(len(reasons), 0)

        report = graph.get_readiness_report()
        self.assertEqual(report["verdict"], "READY_TO_APPLY")
        self.assertTrue(report["is_ready_to_apply"])

        c2 = graph.add_claim("存疑主张2")
        graph.invalidate_claim(c2.claim_id, reason="被背景调查质疑")

        ready2, blockers2 = graph.can_apply()
        self.assertFalse(ready2)
        self.assertTrue(any("存疑废弃" in b for b in blockers2))

        report2 = graph.get_readiness_report()
        self.assertEqual(report2["verdict"], "UNVERIFIED_BLOCK")

    def test_graph_read_is_defensive_and_duplicate_ids_are_rejected(self):
        graph = EvidenceGraph()
        node = graph.add_claim("可审计主张", claim_id="CLM-IMMUTABLE")
        exposed = graph.get_node(node.claim_id)
        exposed.state = EvidenceNodeState.USED_IN_RESUME
        self.assertEqual(graph.get_node(node.claim_id).state, EvidenceNodeState.DRAFT)
        with self.assertRaises(ValueError):
            graph.add_claim("重复主张", claim_id="CLM-IMMUTABLE")

    def test_failed_transition_does_not_mutate_scope_or_defense_count(self):
        graph = EvidenceGraph()
        node = graph.add_claim("未核验主张")
        with self.assertRaises(ValueError):
            graph.ground_claim(node.claim_id, scope="项目A")
        with self.assertRaises(ValueError):
            graph.defend_claim(node.claim_id, rounds=3)
        current = graph.get_node(node.claim_id)
        self.assertEqual(current.scope, "")
        self.assertEqual(current.defended_rounds, 0)

    def test_audit_snapshot_and_serialization(self):
        graph = EvidenceGraph()
        c = graph.add_claim("全链路性能监控", claim_id="CLM-PERF-01")
        graph.verify_claim(c.claim_id)
        graph.ground_claim(c.claim_id, scope="基础架构组")

        snap = graph.audit_snapshot()
        self.assertEqual(snap["snapshot_type"], "evidence_graph_audit")
        self.assertEqual(snap["total_nodes"], 1)
        self.assertEqual(snap["verified_count"], 1)
        self.assertTrue(len(snap["graph_hash"]) > 0)

        d = graph.to_dict()
        restored = EvidenceGraph.from_dict(d)
        self.assertIn("CLM-PERF-01", restored.nodes)
        self.assertEqual(restored.nodes["CLM-PERF-01"].state, EvidenceNodeState.GROUNDED)


# ============================================================================
# 2. Evidence Snapshot Creation
# ============================================================================

class TestEvidenceSnapshotCreation(unittest.TestCase):
    """Verifies immutable scoring & evidence snapshot creation."""

    def test_create_evidence_snapshot_idempotency_and_fingerprinting(self):
        sample_profile = {
            "name": "李四",
            "skills": ["Python", "Go", "Kubernetes"],
            "projects": [
                {
                    "name": "分布式任务调度系统",
                    "role": "核心研发",
                    "highlights": ["使用 Go 实现分布式 Cron 调度", "支持百万级任务并行执行"],
                }
            ],
        }
        sample_jd = {
            "job_title": "云原生开发工程师",
            "company_name": "星河科技",
            "required_skills": ["Go", "Kubernetes", "Docker"],
            "raw_text": "招聘云原生开发工程师，精通 Go 与 Kubernetes 调度机制。",
        }

        snap1 = create_evidence_snapshot(
            profile=sample_profile,
            jd=sample_jd,
            ats_score=88.5,
            notes="第一轮投递初评",
        )
        snap2 = create_evidence_snapshot(
            profile=sample_profile,
            jd=sample_jd,
            ats_score=92.0,
            notes="更新评估",
        )

        self.assertEqual(snap1["profile_fingerprint"], snap2["profile_fingerprint"])
        self.assertEqual(snap1["jd_fingerprint"], snap2["jd_fingerprint"])
        self.assertEqual(snap1["job_title"], "云原生开发工程师")
        self.assertEqual(snap1["candidate_name"], "李四")
        self.assertEqual(snap1["verified_skills_count"], 3)
        self.assertEqual(snap1["ats_score"], 88.5)
        self.assertEqual(snap2["ats_score"], 92.0)

    def test_create_evidence_snapshot_with_evidence_graph(self):
        profile = {"name": "张三", "skills": ["Python"]}
        jd = "Python 后端研发工程师"

        graph = EvidenceGraph()
        c = graph.add_claim("完成高并发重构")
        graph.verify_claim(c.claim_id)
        graph.ground_claim(c.claim_id, scope="支付中台")
        graph.use_in_resume(c.claim_id)

        snap = create_evidence_snapshot(
            profile=profile,
            jd=jd,
            evidence_graph=graph,
        )
        self.assertIsNotNone(snap["evidence_graph"])
        self.assertEqual(snap["evidence_graph"]["total_nodes"], 1)
        self.assertTrue(snap["evidence_graph"]["readiness"]["is_ready_to_apply"])

    def test_matcher_snapshot_keeps_canonical_score_and_gap_matrix(self):
        snapshot = create_evidence_snapshot(
            profile={"name": "张三", "skills": ["Python"]},
            jd="Python 后端研发工程师",
            matcher_result={
                "final_match_score": 0.72,
                "gap_matrix": [{"requirement_name": "Python", "state": "MATCHED", "score": 1.0}],
            },
        )
        self.assertEqual(snapshot["match_score"], 0.72)
        self.assertEqual(snapshot["gap_matrix"][0]["requirement"], "Python")

        legacy_snapshot = create_evidence_snapshot(
            profile={"name": "张三", "skills": ["Python"]},
            jd="Python 后端研发工程师",
            matcher_result={
                "overall_match_score": 72,
                "gap_matrix": [{"requirement_name": "Python", "state": "MATCHED", "score": 100}],
            },
        )
        self.assertEqual(legacy_snapshot["match_score"], 0.72)
        self.assertEqual(legacy_snapshot["gap_matrix"][0]["score"], 100)


# ============================================================================
# 3. Application Store Persistence & Schema Migrations
# ============================================================================

class TestApplicationStorePersistence(unittest.TestCase):
    """Verifies SQLite Schema upgrade, backwards compatibility, and persistent fields."""

    def test_schema_migration_from_v1_legacy_db(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "legacy_v1.db"

            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE applications (
                    id TEXT PRIMARY KEY,
                    target_name TEXT NOT NULL,
                    role_or_track TEXT NOT NULL,
                    status TEXT NOT NULL,
                    deadline TEXT,
                    exam_or_interview_time TEXT,
                    channel TEXT,
                    cooling_days_left INTEGER DEFAULT 0,
                    notes TEXT,
                    applied_date TEXT,
                    updated_at TEXT,
                    collision_risk TEXT,
                    status_history_json TEXT,
                    evidence_snapshot_json TEXT,
                    offer_details_json TEXT
                )
                """
            )
            conn.execute("PRAGMA user_version = 1")
            conn.execute(
                """
                INSERT INTO applications (
                    id, target_name, role_or_track, status, deadline,
                    channel, cooling_days_left, notes, applied_date, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("v1-app-01", "腾讯", "后台开发", "applied", "2026-09-30", "官网", 0, "旧记录", "2026-09-20", "2026-09-20 10:00"),
            )
            conn.commit()
            conn.close()

            store = ApplicationStore(db_path)
            try:
                with store._get_connection() as c:
                    ver = c.execute("PRAGMA user_version").fetchone()[0]
                    self.assertEqual(ver, 7)
                    cols = [r[1] for r in c.execute("PRAGMA table_info(applications)").fetchall()]
                    self.assertIn("target_level", cols)
                    self.assertIn("portal_url", cols)
                    self.assertIn("recruiter_contact", cols)
                    self.assertIsNotNone(c.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='material_proposals'"
                    ).fetchone())

                rec = store.get("v1-app-01")
                self.assertIsNotNone(rec)
                self.assertEqual(rec.id, "v1-app-01")
                self.assertEqual(rec.target_name, "腾讯")
                self.assertEqual(rec.target_level, "")
                self.assertEqual(rec.portal_url, "")
                self.assertEqual(rec.recruiter_contact, "")

                evidence_snapshot = {
                    "snapshot_id": "SNAP-TEST-001",
                    "profile_fingerprint": "profile-hash",
                    "jd_fingerprint": "jd-hash",
                    "evidence_graph": {"readiness": {"is_ready_to_apply": True}},
                }
                self.assertTrue(store.attach_evidence_snapshot("v1-app-01", evidence_snapshot))
                attached = store.get("v1-app-01")
                self.assertEqual(attached.evidence_snapshot["snapshot_id"], "SNAP-TEST-001")

                rec.target_level = "T9"
                rec.portal_url = "https://careers.tencent.com/apply/v1"
                rec.recruiter_contact = "talent@tencent.com"
                store.save(rec)

                reloaded = store.get("v1-app-01")
                self.assertEqual(reloaded.target_level, "T9")
                self.assertEqual(reloaded.portal_url, "https://careers.tencent.com/apply/v1")
                self.assertEqual(reloaded.recruiter_contact, "talent@tencent.com")
            finally:
                store.close()

    def test_application_record_dict_roundtrip(self):
        rec = ApplicationRecord(
            id="app-v2-test",
            target_name="阿里",
            role_or_track="Java专家",
            status=AppStatus.INTERVIEW,
            target_level="P7",
            portal_url="https://job.alibaba.com/position/123",
            recruiter_contact="hr_ali@alibaba-inc.com",
            notes="二面准备中",
        )
        data = rec.to_dict()
        self.assertEqual(data["target_level"], "P7")
        self.assertEqual(data["portal_url"], "https://job.alibaba.com/position/123")
        self.assertEqual(data["recruiter_contact"], "hr_ali@alibaba-inc.com")

        data["extra_unknown_field"] = "some_random_value"
        restored = ApplicationRecord.from_dict(data)
        self.assertEqual(restored.id, "app-v2-test")
        self.assertEqual(restored.target_level, "P7")
        self.assertFalse(hasattr(restored, "extra_unknown_field"))


# ============================================================================
# 4. Application Outcomes & Insights
# ============================================================================

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
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 7)
                columns = {row[1] for row in conn.execute("PRAGMA table_info(application_outcomes)")}
                self.assertIn("outcome_id", columns)
                self.assertIn("feedback_tags_json", columns)
                conn.execute("DROP TABLE application_outcomes")
                conn.execute("DROP TABLE resume_versions")
                conn.execute("PRAGMA user_version = 4")
                conn.commit()
        with ApplicationStore(self.db_path) as migrated:
            with migrated._get_connection() as conn:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 7)
                self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE name='application_outcomes'").fetchone())
                self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE name='resume_versions'").fetchone())

    def test_service_facade(self):
        with ApplicationOutcomeService(self.db_path) as service:
            service.store.save(ApplicationRecord("APP-SVC", "Example Co", "Engineer"))
            result = service.record(OutcomeRecord("APP-SVC", "screening", "advanced"))
            self.assertFalse(result["replayed"])
            self.assertEqual(len(service.list("APP-SVC")), 1)
            self.assertEqual(service.insights()["total_outcomes"], 1)


# ============================================================================
# 5. Application CLI Lifecycle Commands
# ============================================================================

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


# ============================================================================
# 6. Resume Versions & Metadata Diff
# ============================================================================

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
            statuses, hashes = inspect_artifacts({"profile": str(artifact), "pdf": str(Path(tmp) / "missing.pdf")})
            self.assertEqual(statuses, {"profile": "present", "pdf": "missing"})
            self.assertEqual(hashes["profile"], sha256_file(artifact))


if __name__ == "__main__":
    unittest.main()
