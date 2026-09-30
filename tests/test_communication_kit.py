from __future__ import annotations

import pytest
from core.communication_kit import (
    CareerCommunicationKit,
    GeneratedLetter,
    LetterType,
)

CASES = [
    (
        "cold_outreach",
        {
            "candidate_name": "李明",
            "recipient_name": "张经理",
            "target_company": "某科技",
            "target_role": "后端开发工程师",
            "core_skills": ["Golang", "分布式缓存", "Kubernetes"],
            "key_achievements": ["主导订单中台重构，P99延时下降40%", "自研网关支持10万QPS"],
            "portfolio_link": "https://github.com/liming/awesome-proj",
        },
        LetterType.COLD_OUTREACH,
        "自荐-后端开发工程师",
        ["张经理", "某科技", "Golang", "P99延时下降40%", "https://github.com/liming"],
    ),
    (
        "cover_letter",
        {
            "candidate_name": "王芳",
            "company_name": "云原生未来科技",
            "role_name": "平台架构师",
            "company_mission_hook": "多云管控与服务网格领域的持续深耕",
            "matching_experiences": ["5年大型私有云微服务治理落地经验", "精通Envoy与Istio控制面性能调优"],
            "contact_info": "13800000000 / wangfang@example.com",
        },
        LetterType.COVER_LETTER,
        "平台架构师",
        ["云原生未来科技", "多云管控与服务网格", "Envoy与Istio", "13800000000"],
    ),
    (
        "reschedule",
        {
            "candidate_name": "赵强",
            "interviewer_name": "王老师",
            "role_name": "算法工程师",
            "original_datetime": "2026-09-25 14:00",
            "conflict_reason": "硕士学位论文预答辩突发提前至当日下午",
            "available_slots": ["2026-09-26 10:00 - 12:00", "2026-09-26 15:00 - 18:00"],
        },
        LetterType.RESCHEDULE,
        "面试改期申请",
        ["硕士学位论文预答辩", "2026-09-26 10:00"],
    ),
    (
        "thank_you",
        {
            "candidate_name": "孙伟",
            "interviewer_name": "刘总监",
            "role_name": "分布式存储研发",
            "round_name": "技术终面",
            "discussed_topic": "Raft共识算法在极端网络分区下的选主活锁防范",
            "candidate_insight": "可通过引入Pre-Vote机制并在心跳租约过期前做双向静默判定，进一步提升集群自愈鲁棒性",
        },
        LetterType.THANK_YOU,
        "面试感谢与技术跟进",
        ["Raft共识算法", "Pre-Vote机制"],
    ),
    (
        "follow_up",
        {
            "candidate_name": "周杰",
            "recruiter_name": "HR Lucy",
            "role_name": "前端开发专家",
            "interview_date": "2026-09-14",
            "company_name": "极速互联",
        },
        LetterType.FOLLOW_UP,
        None,
        ["极速互联", "2026-09-14", "最新评估进展"],
    ),
    (
        "salary_negotiation",
        {
            "candidate_name": "吴晨",
            "recruiter_name": "HR Director",
            "company_name": "星空科技",
            "role_name": "高级大数据开发",
            "current_offer_package": "35k * 15薪",
            "competing_offer_summary": "头部电商平台给出的 38k * 16薪 + 签字费",
            "target_adjustment": "Base 薪资浮动至 38k 或补充相应期权激励",
            "professional_rationale": "本人更认同星空科技的流批一体数据底座路线，且能立即承接实时数仓割接工作",
        },
        LetterType.SALARY_NEGOTIATION,
        "薪酬方案探讨与意向确认",
        ["35k * 15薪", "38k * 16薪", "流批一体数据底座"],
    ),
    (
        "decline_offer",
        {
            "candidate_name": "郑浩",
            "recruiter_name": "招聘负责人李女士",
            "company_name": "银河金融",
            "role_name": "量化开发工程师",
            "decline_reason": "个人最终选择了更聚焦于高频低延时内核架构的团队",
        },
        LetterType.DECLINE_OFFER,
        "录用沟通与致谢",
        ["银河金融", "高频低延时内核架构"],
    ),
    (
        "boss_intro",
        {
            "candidate_name": "王五",
            "target_role": "数据分析师",
            "experience_summary": "3年消费金融数据分析经验",
            "core_actions": ["搭建全链路风控看板", "重构核心流失漏斗"],
            "verified_outcomes": ["看板响应耗时降低60%", "核心客群留存率提升12%"],
            "target_company_interest": "团队在即时风控特征计算上的实践",
        },
        LetterType.BOSS_INTRO,
        "王五",
        ["数据分析师", "消费金融", "留存率提升12%"],
    ),
    (
        "headhunter_intro",
        {
            "candidate_name": "赵六",
            "current_or_recent_title": "高级后端架构师",
            "years_of_experience": "6年",
            "core_focus_areas": ["高并发交易中台", "分布式存储治理", "DDD领域驱动设计"],
            "representative_impact": [
                "主导双十一万级 QPS 订单结算重构，全链路 P99 降至 25ms",
                "主导万级分库分表与 TiDB 平滑迁移，零资损保障",
            ],
            "target_job_preferences": "期望base北京，关注独角兽核心中台或大厂核心研发线",
            "potential_risks_or_boundaries": "跳槽频率极低（6年2段）；统招一本学历；暂不考虑单休与大小周团队",
        },
        LetterType.HEADHUNTER_INTRO,
        "人才自荐卡",
        ["高并发交易中台", "暂不考虑单休与大小周", "TiDB"],
    ),
]


@pytest.mark.parametrize("method_name, kwargs, expected_type, expected_subject, body_snippets", CASES)
def test_career_communication_kit_writers(method_name, kwargs, expected_type, expected_subject, body_snippets):
    writer_func = getattr(CareerCommunicationKit, method_name)
    letter = writer_func(**kwargs)
    assert isinstance(letter, GeneratedLetter)
    assert letter.letter_type == expected_type
    if expected_subject:
        assert expected_subject in letter.subject
    for snippet in body_snippets:
        assert snippet in letter.body_text
    if expected_type == LetterType.BOSS_INTRO:
        assert 60 < len(letter.body_text) < 220
