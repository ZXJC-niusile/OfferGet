from __future__ import annotations

import pytest
from core.post_interview import (
    InterviewDialogueTurn,
    NextRoundChecklist,
    PostInterviewDebriefEngine,
    TranscriptParser,
)


def test_transcript_parser_basic():
    raw_text = """
面试官：请介绍一下你负责的订单中心高并发改造项目？
候选人：我主导了订单中心的读写分离与分库分表重构，承载峰值 10000 QPS。
面试官：在分库分表后，跨分片分页查询是怎么处理的？
候选人：我们在底层引入了 Elasticsearch 做读索引同步，核心订单通过分片键直查。
"""
    turns = TranscriptParser.parse(raw_text)
    assert len(turns) == 2
    assert turns[0].turn_id == 1
    assert "订单中心高并发改造" in turns[0].interviewer_question
    assert "10000 QPS" in turns[0].candidate_answer
    assert turns[1].turn_id == 2
    assert "跨分片分页查询" in turns[1].interviewer_question
    assert "Elasticsearch" in turns[1].candidate_answer


def test_transcript_parser_prefixes_and_multiline():
    raw_text = """
Q1: Redis 集群如果发生脑裂，会导致什么后果？
A1: 可能导致部分数据写入丢失。
因为网络分区后，老主节点可能仍接收少量写入，待网络恢复后新主节点会覆盖老节点数据。

问：你平时如何规避这一问题？
答：配置 min-replicas-to-write 与 min-replicas-max-lag 参数。
同时搭配自动化哨兵/Sentinel 集群巡检。
"""
    turns = TranscriptParser.parse(raw_text)
    assert len(turns) == 2
    assert "Redis 集群如果发生脑裂" in turns[0].interviewer_question
    assert "覆盖老节点数据" in turns[0].candidate_answer
    assert "如何规避这一问题" in turns[1].interviewer_question
    assert "min-replicas-to-write" in turns[1].candidate_answer


def test_post_interview_debrief_engine():
    transcript = """
面试官：你们系统在秒杀大促时发生过缓存击穿吗？你是怎么解决的？
候选人：发生过一次，但我完美解决了。没有任何技术挑战，我们彻底重构了代码，达到了百分之百零故障。
面试官：具体是怎么做互斥与异步更新的？
候选人：我主要负责使用分布式锁 Singleflight 防击穿，通过互斥锁拦截击穿并发，降级率降至 0.01%。
"""
    checklist = PostInterviewDebriefEngine.debrief(
        transcript_text=transcript,
        target_role="高级后端工程师",
        session_title="美团基础架构一面复盘",
    )

    assert isinstance(checklist, NextRoundChecklist)
    assert checklist.total_turns == 2
    assert checklist.session_title == "美团基础架构一面复盘"
    assert checklist.next_round_readiness_score > 0
    assert len(checklist.dialogue_turns) == 2

    # 第一轮回答存在夸大词汇（完美解决、彻底重构、零故障），应该被识别为弱回答或警告
    turn1 = checklist.dialogue_turns[0]
    assert turn1.turn_score < 90.0
    assert any("夸大" in bp or "过度断言" in bp for bp in checklist.blindspot_summary)

    # 验证下一轮追问和指标提取
    assert len(checklist.high_frequency_follow_ups) > 0
    assert any("0.01%" in m for m in checklist.mandatory_metrics_to_memorize)
    assert len(checklist.failure_contingency_scripts) > 0
    assert "# 🎯 面试全复盘战报与 (N+1) 面备战清单" in checklist.markdown_report


def test_debrief_empty_transcript():
    checklist = PostInterviewDebriefEngine.debrief("")
    assert checklist.total_turns == 0
    assert checklist.next_round_readiness_score == 0.0
    assert "未解析到有效" in checklist.markdown_report
