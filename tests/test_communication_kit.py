from __future__ import annotations

import pytest
from core.communication_kit import (
    CareerCommunicationKit,
    ColdOutreachWriter,
    CoverLetterWriter,
    DeclineOfferWriter,
    FollowUpLetterWriter,
    GeneratedLetter,
    LetterType,
    RescheduleLetterWriter,
    SalaryNegotiationWriter,
    ThankYouLetterWriter,
)


def test_cold_outreach_letter():
    letter = CareerCommunicationKit.cold_outreach(
        candidate_name="李明",
        recipient_name="张经理",
        target_company="某科技",
        target_role="后端开发工程师",
        core_skills=["Golang", "分布式缓存", "Kubernetes"],
        key_achievements=["主导订单中台重构，P99延时下降40%", "自研网关支持10万QPS"],
        portfolio_link="https://github.com/liming/awesome-proj",
    )
    assert isinstance(letter, GeneratedLetter)
    assert letter.letter_type == LetterType.COLD_OUTREACH
    assert "自荐-后端开发工程师" in letter.subject
    assert "张经理" in letter.body_text
    assert "某科技" in letter.body_text
    assert "Golang" in letter.body_text
    assert "P99延时下降40%" in letter.body_text
    assert "https://github.com/liming" in letter.body_text


def test_cover_letter():
    letter = CareerCommunicationKit.cover_letter(
        candidate_name="王芳",
        company_name="云原生未来科技",
        role_name="平台架构师",
        company_mission_hook="多云管控与服务网格领域的持续深耕",
        matching_experiences=[
            "5年大型私有云微服务治理落地经验",
            "精通Envoy与Istio控制面性能调优",
        ],
        contact_info="13800000000 / wangfang@example.com",
    )
    assert letter.letter_type == LetterType.COVER_LETTER
    assert "平台架构师" in letter.subject
    assert "云原生未来科技" in letter.body_text
    assert "多云管控与服务网格" in letter.body_text
    assert "Envoy与Istio" in letter.body_text
    assert "13800000000" in letter.body_text


def test_reschedule_letter():
    letter = CareerCommunicationKit.reschedule(
        candidate_name="赵强",
        interviewer_name="王老师",
        role_name="算法工程师",
        original_datetime="2026-09-25 14:00",
        conflict_reason="硕士学位论文预答辩突发提前至当日下午",
        available_slots=[
            "2026-09-26 10:00 - 12:00",
            "2026-09-26 15:00 - 18:00",
        ],
    )
    assert letter.letter_type == LetterType.RESCHEDULE
    assert "面试改期申请" in letter.subject
    assert "硕士学位论文预答辩" in letter.body_text
    assert "2026-09-26 10:00" in letter.body_text


def test_thank_you_letter():
    letter = CareerCommunicationKit.thank_you(
        candidate_name="孙伟",
        interviewer_name="刘总监",
        role_name="分布式存储研发",
        round_name="技术终面",
        discussed_topic="Raft共识算法在极端网络分区下的选主活锁防范",
        candidate_insight="可通过引入Pre-Vote机制并在心跳租约过期前做双向静默判定，进一步提升集群自愈鲁棒性",
    )
    assert letter.letter_type == LetterType.THANK_YOU
    assert "面试感谢与技术跟进" in letter.subject
    assert "Raft共识算法" in letter.body_text
    assert "Pre-Vote机制" in letter.body_text


def test_follow_up_letter():
    letter = CareerCommunicationKit.follow_up(
        candidate_name="周杰",
        recruiter_name="HR Lucy",
        role_name="前端开发专家",
        interview_date="2026-09-14",
        company_name="极速互联",
    )
    assert letter.letter_type == LetterType.FOLLOW_UP
    assert "极速互联" in letter.body_text
    assert "2026-09-14" in letter.body_text
    assert "最新评估进展" in letter.body_text


def test_salary_negotiation_letter():
    letter = CareerCommunicationKit.salary_negotiation(
        candidate_name="吴晨",
        recruiter_name="HR Director",
        company_name="星空科技",
        role_name="高级大数据开发",
        current_offer_package="35k * 15薪",
        competing_offer_summary="头部电商平台给出的 38k * 16薪 + 签字费",
        target_adjustment="Base 薪资浮动至 38k 或补充相应期权激励",
        professional_rationale="本人更认同星空科技的流批一体数据底座路线，且能立即承接实时数仓割接工作",
    )
    assert letter.letter_type == LetterType.SALARY_NEGOTIATION
    assert "薪酬方案探讨与意向确认" in letter.subject
    assert "35k * 15薪" in letter.body_text
    assert "38k * 16薪" in letter.body_text
    assert "流批一体数据底座" in letter.body_text


def test_decline_offer_letter():
    letter = CareerCommunicationKit.decline_offer(
        candidate_name="郑浩",
        recruiter_name="招聘负责人李女士",
        company_name="银河金融",
        role_name="量化开发工程师",
        decline_reason="个人最终选择了更聚焦于高频低延时内核架构的团队",
    )
    assert letter.letter_type == LetterType.DECLINE_OFFER
    assert "录用沟通与致谢" in letter.subject
    assert "银河金融" in letter.body_text
    assert "高频低延时内核架构" in letter.body_text
