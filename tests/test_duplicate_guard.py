from __future__ import annotations

import pytest
from core.duplicate_guard import (
    ApplicationChannel,
    ApplicationRecord,
    CollisionCheckResult,
    CompanyEntityNormalizer,
    DuplicateApplicationGuard,
    JobFingerprint,
)


def test_company_normalizer():
    assert CompanyEntityNormalizer.normalize("北京字跳网络技术有限公司") == "bytedance"
    assert CompanyEntityNormalizer.normalize("抖音-商业化技术部") == "bytedance"
    assert CompanyEntityNormalizer.normalize("飞书 Lark") == "bytedance"
    assert CompanyEntityNormalizer.normalize("淘宝天猫商业集团") == "alibaba"
    assert CompanyEntityNormalizer.normalize("腾讯科技（深圳）有限公司") == "tencent"
    assert CompanyEntityNormalizer.normalize("美团快驴事业部") == "meituan"


def test_job_fingerprint():
    jd1 = "负责后端高并发架构设计，熟悉 Golang 与 Redis，具有分布式锁实战经验。"
    jd2 = "参与后端架构设计，负责高并发微服务开发，深入使用 Golang 和 Redis 分布式锁。"
    jd3 = "主要负责前端 Vue3 移动端 H5 页面交互与 CSS 动画优化。"

    sim12 = JobFingerprint.jaccard_similarity(jd1, jd2)
    sim13 = JobFingerprint.jaccard_similarity(jd1, jd3)

    assert sim12 > 0.35
    assert sim13 < 0.1


def test_duplicate_guard_headhunter_channel_collision():
    history = [
        ApplicationRecord(
            record_id="rec_001",
            company_name="字节跳动",
            role_title="高级后端工程师",
            channel=ApplicationChannel.HEADHUNTER,
            applied_date="2026-09-01",
            status="interviewing",
            recruiter_info="猎头 Alex",
        )
    ]

    # 尝试用官网直投，同一个实体
    res = DuplicateApplicationGuard.check_application(
        new_company="抖音",
        new_role="后端研发",
        new_channel=ApplicationChannel.DIRECT_CAREERS_SITE,
        applied_date="2026-09-15",
        history=history,
    )

    assert res.has_collision is True
    assert res.risk_level == "HIGH_RISK_BLOCK"
    assert res.normalized_company == "bytedance"
    assert any("渠道撞单风险" in r for r in res.reasons)
    assert "严禁此时投递" in res.recommendation


def test_duplicate_guard_rejection_cooldown():
    history = [
        ApplicationRecord(
            record_id="rec_002",
            company_name="美团",
            role_title="分布式存储专家",
            channel=ApplicationChannel.DIRECT_CAREERS_SITE,
            applied_date="2026-08-01",
            status="rejected",
        )
    ]

    # 45天后再次投递美团
    res = DuplicateApplicationGuard.check_application(
        new_company="北京三快科技有限公司",
        new_role="基础设施存储专家",
        new_channel=ApplicationChannel.INTERNAL_REFERRAL,
        applied_date="2026-09-15",
        history=history,
        cooldown_days=180,
    )

    assert res.has_collision is True
    assert res.risk_level == "LOW_WARNING"
    assert res.cooldown_days_remaining > 100
    assert any("冷冻期拦截" in r for r in res.reasons)


def test_duplicate_guard_safe_case():
    history = [
        ApplicationRecord(
            record_id="rec_003",
            company_name="腾讯",
            role_title="云原生架构师",
            channel=ApplicationChannel.INTERNAL_REFERRAL,
            applied_date="2025-01-01",
            status="offered",
        )
    ]

    # 投递完全不同企业
    res = DuplicateApplicationGuard.check_application(
        new_company="微软",
        new_role="Software Engineer",
        new_channel=ApplicationChannel.DIRECT_CAREERS_SITE,
        applied_date="2026-09-15",
        history=history,
    )

    assert res.has_collision is False
    assert res.risk_level == "NONE"
    assert "未发现渠道冲突" in res.recommendation
