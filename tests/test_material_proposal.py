import unittest

from core.job_flow import run_career_review
from core.material_proposal import (
    MaterialProposal,
    MaterialProposalStatus,
    create_material_proposal,
    apply_material_proposal,
    profile_fingerprint,
    jd_fingerprint,
)
from core.application_tracker import ApplicationStore, ApplicationRecord
from core.services import ProposalService
import tempfile
from pathlib import Path


class TestMaterialProposal(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "candidate": {"name": "张三"},
            "experience": [{"company": "公司A", "role": "工程师", "bullets": ["完成接口开发"]}],
        }
        self.jd = "职位：后端工程师\n职责：负责接口开发"

    def test_partial_acceptance_and_roundtrip(self):
        proposal = MaterialProposal(
            proposal_id="PROP-1",
            source_profile_hash=profile_fingerprint(self.profile),
            source_jd_hash=jd_fingerprint(self.jd),
            patches=[{"validation_status": "applied", "after": "A"}, {"validation_status": "applied", "after": "B"}],
        )
        accepted = proposal.accept(self.profile, self.jd, patch_ids=[1])
        self.assertEqual([p["after"] for p in accepted], ["B"])
        self.assertEqual(proposal.status, MaterialProposalStatus.ACCEPTED)
        restored = MaterialProposal.from_dict(proposal.to_dict())
        self.assertEqual(restored.accepted_patch_ids, [1])

    def test_source_drift_conflicts_before_acceptance(self):
        proposal = MaterialProposal(
            proposal_id="PROP-2",
            source_profile_hash="p",
            source_jd_hash="j",
            patches=[{"after": "A"}],
        )
        with self.assertRaises(ValueError):
            proposal.accept(self.profile, self.jd)
        self.assertEqual(proposal.status, MaterialProposalStatus.CONFLICTED)

    def test_accept_creates_new_profile_and_checks_before_text(self):
        proposal = MaterialProposal(
            proposal_id="PROP-3",
            source_profile_hash=profile_fingerprint(self.profile),
            source_jd_hash=jd_fingerprint(self.jd),
            patches=[{
                "target_path": "experience[0].bullets[0]",
                "before": "完成接口开发",
                "after": "完成接口开发并补充错误处理",
                "validation_status": "applied",
            }],
        )
        updated = apply_material_proposal(proposal, self.profile, self.jd)
        self.assertEqual(updated["experience"][0]["bullets"][0], "完成接口开发并补充错误处理")
        self.assertEqual(self.profile["experience"][0]["bullets"][0], "完成接口开发")

    def test_review_emits_human_confirmation_proposal(self):
        result = run_career_review(self.jd, self.profile)
        proposal = MaterialProposal.from_dict(result["material_proposal"])
        self.assertEqual(proposal.status, MaterialProposalStatus.DRAFT)
        self.assertEqual(proposal.source_jd_hash, proposal.source_jd_hash)
        self.assertEqual(proposal.proposal_hash, proposal.compute_hash())

    def test_persistence_filters_by_application_and_status(self):
        proposal = MaterialProposal(
            proposal_id="PROP-LIST",
            application_id="APP-1",
            source_profile_hash=profile_fingerprint(self.profile),
            source_jd_hash=jd_fingerprint(self.jd),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with ApplicationStore(Path(tmp) / "store.db") as store:
                store.save(ApplicationRecord("APP-1", "公司A", "工程师"))
                store.save_material_proposal(proposal)
                self.assertEqual(len(store.list_material_proposals("draft", "APP-1")), 1)
                self.assertEqual(len(store.list_material_proposals(company="公司A", role="工程师")), 1)
                self.assertEqual(len(store.list_material_proposals("accepted", "APP-1")), 0)

    def test_persistence_rejects_orphan_application(self):
        proposal = MaterialProposal(
            proposal_id="PROP-ORPHAN",
            application_id="MISSING",
            source_profile_hash=profile_fingerprint(self.profile),
            source_jd_hash=jd_fingerprint(self.jd),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with ApplicationStore(Path(tmp) / "store.db") as store:
                with self.assertRaises(ValueError):
                    store.save_material_proposal(proposal)


class TestProposalService(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "candidate": {"name": "张三"},
            "experience": [{"company": "公司A", "role": "工程师", "bullets": ["完成接口开发"]}],
        }
        self.jd = "职位：后端工程师\n职责：负责接口开发"

    def _proposal(self, proposal_id="PROP-SVC"):
        return MaterialProposal(
            proposal_id=proposal_id,
            source_profile_hash=profile_fingerprint(self.profile),
            source_jd_hash=jd_fingerprint(self.jd),
            application_id="APP-SVC",
            patches=[{
                "target_path": "experience[0].bullets[0]",
                "before": "完成接口开发",
                "after": "完成接口开发并补充错误处理",
                "validation_status": "applied",
            }],
        )

    def test_service_roundtrip_accept_and_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "svc.db"
            output = Path(tmp) / "nested" / "out.json"
            with ProposalService(db_path) as service:
                service.store.save(ApplicationRecord("APP-SVC", "公司A", "工程师"))
                service.save(self._proposal())
                self.assertEqual(len(service.list(application_id="APP-SVC")), 1)
                result = service.accept("PROP-SVC", self.profile, self.jd, output)
                self.assertTrue(output.exists())
                self.assertEqual(result["proposal"]["status"], "accepted")
                service.save(self._proposal("PROP-SVC2"))
                rejected = service.reject("PROP-SVC2")
                self.assertEqual(rejected.status, MaterialProposalStatus.REJECTED)
                with self.assertRaises(KeyError):
                    service.accept("MISSING", self.profile, self.jd, output)
                with self.assertRaises(KeyError):
                    service.reject("MISSING")

    def test_service_accept_failure_persists_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "svc.db"
            output = Path(tmp) / "out.json"
            with ProposalService(db_path) as service:
                service.store.save(ApplicationRecord("APP-SVC", "公司A", "工程师"))
                service.save(self._proposal())
                drifted = {
                    "candidate": {"name": "张三"},
                    "experience": [{"company": "公司A", "role": "工程师", "bullets": ["完成接口开发（已复审）"]}],
                }
                with self.assertRaises(ValueError):
                    service.accept("PROP-SVC", drifted, self.jd, output)
                stored = service.get("PROP-SVC")
                self.assertEqual(stored.status, MaterialProposalStatus.CONFLICTED)
                self.assertEqual(stored.conflict_reason, "source_profile_changed")
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
