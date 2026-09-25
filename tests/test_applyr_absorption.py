"""
Tests for applyr architectural absorption into OfferGet.
Verifies:
1. Evidence Graph finite state machine, monotonic progression, and gate checks.
2. create_evidence_snapshot immutable scoring & fingerprint generation.
3. ApplicationStore SQLite schema v2 migration, persistence, and backwards compatibility.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
import unittest

from core.application_tracker import (
    ApplicationRecord,
    ApplicationStore,
    AppStatus,
    create_evidence_snapshot,
)
from core.evidence.graph import (
    EvidenceGraph,
    EvidenceNode,
    EvidenceNodeState,
)


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

        # Add only draft nodes
        c1 = graph.add_claim("主张1")
        ready, _ = graph.can_apply()
        self.assertFalse(ready)

        # Verify and ground c1, and use in resume
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

        # Invalidate a node
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

        # Roundtrip serialization
        d = graph.to_dict()
        restored = EvidenceGraph.from_dict(d)
        self.assertIn("CLM-PERF-01", restored.nodes)
        self.assertEqual(restored.nodes["CLM-PERF-01"].state, EvidenceNodeState.GROUNDED)


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

        # Fingerprints must be deterministic and identical for same content
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


class TestApplicationStoreSchemaV2(unittest.TestCase):
    """Verifies SQLite Schema v2 upgrade, backwards compatibility, and persistent fields."""

    def test_schema_v2_migration_from_v1_legacy_db(self):
        """Simulate an existing v1 SQLite DB without v2 columns and test forward migration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "legacy_v1.db"

            # 1. Manually create v1 schema
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
            # Insert a record in v1
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

            # 2. Open via ApplicationStore (should automatically trigger v2 migration)
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

                # 3. Read legacy record: new fields should gracefully default to empty string
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

                # 4. Update with v2 fields and save
                rec.target_level = "T9"
                rec.portal_url = "https://careers.tencent.com/apply/v1"
                rec.recruiter_contact = "talent@tencent.com"
                store.save(rec)

                # 5. Reload and verify updated fields
                reloaded = store.get("v1-app-01")
                self.assertEqual(reloaded.target_level, "T9")
                self.assertEqual(reloaded.portal_url, "https://careers.tencent.com/apply/v1")
                self.assertEqual(reloaded.recruiter_contact, "talent@tencent.com")
            finally:
                store.close()

    def test_application_record_dict_roundtrip_with_v2_fields(self):
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

        # Test tolerance against unexpected extra keys
        data["extra_unknown_field"] = "some_random_value"
        restored = ApplicationRecord.from_dict(data)
        self.assertEqual(restored.id, "app-v2-test")
        self.assertEqual(restored.target_level, "P7")
        self.assertFalse(hasattr(restored, "extra_unknown_field"))


if __name__ == "__main__":
    unittest.main()
