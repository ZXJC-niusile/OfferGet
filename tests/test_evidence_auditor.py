"""
Tests for OfferGet Evidence Auditor and FactVerificationGuard integration.
Verifies claim extraction, role boundary audits, inflation patterns,
and ASu-compliant report synthesis.
"""

import pytest

from core.evidence.auditor import EvidenceAuditor
from core.evidence.extractor import ClaimExtractor
from core.evidence.schema import validate_report_data
from core.fact_guard import FactVerificationGuard, audit_resume_evidence


@pytest.fixture
def sample_profile():
    return {
        "candidate": {
            "name": "李小华",
            "years_of_experience": 3,
            "github": "xiaohua-lee",
        },
        "experience": [
            {
                "company": "字节跳动",
                "role": "算法工程师",
                "dates": "2024.03 - 2026.06",
                "highlights": [
                    {
                        "claim_id": "EXP-0",
                        "claim_zh": "基于 Ray 优化分布式训练调度，集群规模 1024 卡，MFU 达到 54.2%",
                        "verified_metrics": {
                            "cluster_size": 1024,
                            "mfu_after": "54.2%",
                        },
                    }
                ],
                "bullets": [
                    "参与分布式数据管线清洗与性能测试。",
                ],
            }
        ],
        "projects": [
            {
                "name": "FastInfer",
                "role": "主要开发者",
                "dates": "2023.09 - 2024.02",
                "stars": 1200,
                "description": "开源推理加速库，在 GSM8K 上达到 85% 准确率。",
            }
        ],
    }


class TestClaimExtractor:
    def test_extract_from_bullet_with_role_and_superlative(self):
        bullet = "作为核心作者主导开源项目，打造了业内最先进的分布式推理引擎，将首字延迟从 500ms 降至 200ms。"
        claims = ClaimExtractor.extract_claims_from_bullet(bullet, "C-001")
        assert len(claims) >= 3

        cat_set = {c.category for c in claims}
        assert "role_boundary" in cat_set
        assert "superlative" in cat_set

    def test_extract_from_resume_dict(self, sample_profile):
        resume_dict = {
            "experience": [
                {
                    "company": "字节跳动",
                    "role": "算法工程师",
                    "bullets": [
                        "负责集群调度优化，提升 MFU 至 54.2%。",
                        "主导全系统架构从0到1研发。",
                    ],
                }
            ],
            "projects": [
                {
                    "name": "FastInfer",
                    "bullets": ["作为核心作者开源该项目。"],
                }
            ],
        }
        claims = ClaimExtractor.extract_from_resume_dict(resume_dict)
        assert len(claims) >= 3
        ids = [c.id for c in claims]
        assert "C-001" in ids


class TestEvidenceAuditor:
    def test_role_escalation_detection(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        bullet = "作为核心作者与 Owner，全面负责字节跳动万卡集群大模型底座架构从0到1研发。"
        report = auditor.audit([bullet], subject_name="李小华")

        assert report.metadata["subject"] == "李小华"
        assert len(report.claims) >= 2

        role_claims = [c for c in report.claims if c.category == "role_boundary"]
        assert len(role_claims) > 0
        rc = role_claims[0]
        assert rc.status == "partially_corroborated"
        assert rc.risk == "high"
        assert "角色升格" in [p.name for p in report.patterns]

    def test_superlative_detection(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        bullet = "研发了全球最先进的自适应算子调度器。"
        report = auditor.audit([bullet])

        sup_claims = [c for c in report.claims if c.category == "superlative"]
        assert len(sup_claims) > 0
        sc = sup_claims[0]
        assert sc.status == "unsupported"
        assert sc.risk == "high"
        assert "没有比较全集的最高级" in [p.name for p in report.patterns]

    def test_corroborated_grounded_bullet(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        bullet = "基于 Ray 优化分布式训练调度，在 1024 卡集群上 MFU 达到 54.2%。"
        report = auditor.audit([bullet])

        main_claim = report.claims[0]
        assert main_claim.status == "corroborated"
        assert main_claim.risk == "low"
        assert main_claim.confidence == "high"

    def test_metric_contradiction_detection(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        # 200 / 2000 is 10%, but claimed 38%
        bullet = "对 200 / 2000 项任务进行了优化，实现了 38% 的完成率。"
        report = auditor.audit([bullet])

        metric_claims = [c for c in report.claims if c.category == "metric"]
        assert len(metric_claims) > 0
        mc = metric_claims[0]
        assert mc.status == "contradicted"
        assert mc.risk == "critical"
        assert "伪精确" in [p.name for p in report.patterns]

    def test_full_report_schema_validity(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        bullets = [
            "基于 Ray 优化分布式训练调度，在 1024 卡集群上 MFU 达到 54.2%。",
            "作为核心作者主导开源项目 FastInfer，获得 1200 stars。",
            "研发业内首个自适应通信算子。",
        ]
        report = auditor.audit(bullets)
        report_dict = report.to_dict()

        # Validate against strict ASu report schema
        errors = validate_report_data(report_dict)
        assert errors == [], f"Report schema validation failed: {errors}"


class TestFactVerificationGuardIntegration:
    def test_guard_audit_claims_and_generate_report(self, sample_profile):
        guard = FactVerificationGuard(sample_profile)

        bullets = [
            "基于 Ray 优化分布式训练调度，在 1024 卡集群上 MFU 达到 54.2%。",
            "作为架构师主导全链路系统重构。",
        ]
        report = guard.audit_claims(bullets)
        assert hasattr(report, "metadata")
        assert len(report.claims) >= 2

        report_dict = guard.generate_audit_report(bullets)
        assert isinstance(report_dict, dict)
        errors = validate_report_data(report_dict)
        assert errors == []

    def test_top_level_audit_resume_evidence(self, sample_profile):
        report_dict = audit_resume_evidence(
            "基于 Ray 优化分布式训练调度，在 1024 卡集群上 MFU 达到 54.2%。",
            sample_profile,
            subject_name="李小华",
        )
        assert report_dict["metadata"]["subject"] == "李小华"
        errors = validate_report_data(report_dict)
        assert errors == []
