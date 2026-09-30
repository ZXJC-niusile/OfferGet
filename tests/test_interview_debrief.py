"""
Unit tests for OfferGet Interview Debrief Engine (interview_debrief.py)
Covering fixes for ISSUE-02 ~ ISSUE-08:
- ISSUE-02: No fabricated "进行结构化优化" in conservative revision.
- ISSUE-03: verification_status defaults to "unverified", not "verified".
- ISSUE-04: Separation of coaching_advice and revised_answer/refined_answer.
- ISSUE-05: Multi-claim check: boundary statements do not exempt other quantified claims from Fact Guard.
- ISSUE-06: Relevance check against core question terms, not arbitrary technical words.
- ISSUE-07: Irrelevant answers >= 80 chars must not bypass relevance check (UNCERTAIN diagnosis).
- ISSUE-08: Unit regex matching without single 's' false positive, strict baseline regex without isolated '从'.
"""

import unittest
from core.interview_debrief import (
    InterviewDebriefEngine,
    DebriefQuestionItem,
    QuestionDiagnosis,
)
from core.fact_guard import FactVerificationGuard


class TestInterviewDebriefFixes(unittest.TestCase):

    def setUp(self):
        self.engine = InterviewDebriefEngine()
        self.sample_profile = {
            "candidate": {"name": "测试候选人", "years_of_experience": 3},
            "skills": ["Python", "SQLite"],
            "experience": [
                {
                    "company": "测试科技",
                    "role": "后端工程师",
                    "highlights": [
                        {
                            "claim_id": "EXP-01",
                            "claim_zh": "负责查询接口开发，访问速度基线为 200ms，优化后达到 100ms。",
                            "verified_metrics": {
                                "latency": "100ms",
                                "baseline": "200ms"
                            }
                        }
                    ]
                }
            ]
        }
        self.fact_guard = FactVerificationGuard(self.sample_profile)

    # ----------------------------------------------------------------------
    # ISSUE-02: No fabricated "进行结构化优化"
    # ----------------------------------------------------------------------
    def test_issue_02_no_fabricated_structured_optimization(self):
        """Unverified numbers must not inject fabricated '进行结构化优化'."""
        unverified = [{"claimed_metric": "50%"}]
        drifts = []
        answer = "我负责查询接口，访问速度提升了 50%。"
        revised = self.engine._create_conservative_revision(answer, drifts, unverified)

        self.assertNotIn("进行结构化优化", revised)
        self.assertNotIn("50%", revised)
        self.assertIn("查询接口", revised)
        self.assertIn("未提供基线数据", revised)
        self.assertNotIn("缺乏基线压测数据", revised)
        self.assertNotIn("没有压测数据", revised)

    def test_issue_02_conservative_revision_preserves_supported_baseline(self):
        """Drifts with verified baseline are properly qualified."""
        drifts = [{"claimed_metric": "50%", "verified_baseline": "20%"}]
        unverified = []
        answer = "模型推理吞吐提升 50%。"
        revised = self.engine._create_conservative_revision(answer, drifts, unverified)

        self.assertNotIn("进行结构化优化", revised)
        self.assertIn("20%（已核验基线）", revised)

    # ----------------------------------------------------------------------
    # ISSUE-03: verification_status defaults to "unverified"
    # ----------------------------------------------------------------------
    def test_issue_03_default_verification_status_is_unverified(self):
        """DebriefQuestionItem and analyze_question must default to 'unverified'."""
        item = DebriefQuestionItem(
            question="测试问题",
            candidate_answer="测试回答"
        )
        self.assertEqual(item.verification_status, "unverified")

        # Without fact_guard, status remains unverified
        res = self.engine.analyze_question(
            question="请介绍你的项目经验",
            answer="我负责项目核心模块开发。"
        )
        self.assertEqual(res.verification_status, "unverified")

    def test_issue_03_verified_only_when_fact_guard_passes(self):
        """verification_status is 'verified' only after passing Fact Guard."""
        # Answer with unverified metric -> unverified / revision verified
        res_fail = self.engine.analyze_question(
            question="请谈谈接口优化",
            answer="我负责接口优化，性能提升了 80%。",
            fact_guard=self.fact_guard
        )
        # The revision should have passed incremental check -> verified, but original had drift
        self.assertIn(res_fail.verification_status, ["verified", "unverified"])

        # When revision fails fact check
        class StrictFailingGuard:
            def verify_facts(self, text):
                return {"passed": False, "drifts": [], "unverified_claims": [{"claimed_metric": "80%"}]}

        res_strict = self.engine.analyze_question(
            question="请谈谈接口优化",
            answer="我负责接口优化，性能提升了 80%。",
            fact_guard=StrictFailingGuard()
        )
        self.assertEqual(res_strict.verification_status, "revision_failed_fact_check")

    # ----------------------------------------------------------------------
    # ISSUE-04: Separation of coaching_advice and revised_answer/refined_answer
    # ----------------------------------------------------------------------
    def test_issue_04_coaching_advice_not_stuffed_into_revised_answer(self):
        """When can_revise is False, revised_answer and refined_answer must be empty."""
        # Experience boundary
        res_boundary = self.engine.analyze_question(
            question="请谈谈 Redis 缓存击穿的解决方案",
            answer="这块技术我之前没做过，不太了解底层细节。"
        )
        self.assertEqual(res_boundary.diagnosis, QuestionDiagnosis.EXPERIENCE_BOUNDARY)
        self.assertFalse(res_boundary.can_revise)
        self.assertEqual(res_boundary.revised_answer, "")
        self.assertEqual(res_boundary.refined_answer, "")
        self.assertTrue(len(res_boundary.coaching_advice) > 0)
        self.assertIn("坦诚说明未在实际项目中主导过", res_boundary.coaching_advice)

        # Fatal gap (empty answer)
        res_empty = self.engine.analyze_question(
            question="请介绍项目",
            answer=""
        )
        self.assertEqual(res_empty.diagnosis, QuestionDiagnosis.FATAL_GAP)
        self.assertFalse(res_empty.can_revise)
        self.assertEqual(res_empty.revised_answer, "")
        self.assertEqual(res_empty.refined_answer, "")
        self.assertTrue(len(res_empty.coaching_advice) > 0)

        # DebriefQuestionItem __post_init__ should never copy coaching_advice into refined_answer
        item = DebriefQuestionItem(
            question="Q",
            candidate_answer="A",
            coaching_advice="指导建议",
            can_revise=False
        )
        self.assertEqual(item.revised_answer, "")
        self.assertEqual(item.refined_answer, "")

    # ----------------------------------------------------------------------
    # ISSUE-05: Multi-claim boundary does not exempt other quantified claims
    # ----------------------------------------------------------------------
    def test_issue_05_boundary_statement_does_not_exempt_quantified_claims(self):
        """Answer with '没做过' but claiming unverified '提升 50%' must trigger METRIC_DRIFT."""
        answer = "没做过 Redis，但我主导另一项目提升 50%。"
        res = self.engine.analyze_question(
            question="请谈谈你在 Redis 方面的实战经验",
            answer=answer,
            fact_guard=self.fact_guard
        )
        # Must be diagnosed as METRIC_DRIFT, not EXPERIENCE_BOUNDARY
        self.assertEqual(res.diagnosis, QuestionDiagnosis.METRIC_DRIFT)
        self.assertTrue(res.can_revise)
        self.assertNotIn("50%", res.refined_answer)
        self.assertIn("没做过 Redis", res.refined_answer)
        self.assertIn("未提供基线数据", res.refined_answer)
        self.assertNotIn("缺乏基线压测数据", res.refined_answer)

    def test_issue_05_pure_boundary_remains_experience_boundary(self):
        """Pure boundary answer without metrics remains EXPERIENCE_BOUNDARY."""
        answer = "这块技术我之前没做过，不太了解底层细节。"
        res = self.engine.analyze_question(
            question="请谈谈你在 Redis 方面的实战经验",
            answer=answer,
            fact_guard=self.fact_guard
        )
        self.assertEqual(res.diagnosis, QuestionDiagnosis.EXPERIENCE_BOUNDARY)
        self.assertFalse(res.can_revise)
        self.assertEqual(res.refined_answer, "")

    # ----------------------------------------------------------------------
    # ISSUE-06: Relevance check against question core terms, not arbitrary tech words
    # ----------------------------------------------------------------------
    def test_issue_06_arbitrary_tech_words_do_not_satisfy_relevance(self):
        """Answer containing unrelated tech words to a specific question is UNCERTAIN."""
        question = "请问如何解决 Redis 缓存击穿？"
        # Answer contains tech words (代码, 测试, 项目, 开发) but unrelated to Redis/缓存/击穿
        answer = "我之前做前端开发，写过很多代码和测试，项目很成功。"
        res = self.engine.analyze_question(question, answer)
        self.assertEqual(res.diagnosis, QuestionDiagnosis.UNCERTAIN)
        self.assertFalse(res.can_revise)
        self.assertEqual(res.refined_answer, "")

    def test_issue_06_relevant_answer_matches_question_core_terms(self):
        """Answer matching question core terms is recognized as relevant."""
        question = "请问如何解决 Redis 缓存击穿？"
        answer = "针对 Redis 缓存击穿问题，我们通常采用互斥锁防止并发穿透。"
        res = self.engine.analyze_question(question, answer)
        self.assertNotEqual(res.diagnosis, QuestionDiagnosis.UNCERTAIN)

    # ----------------------------------------------------------------------
    # ISSUE-07: Irrelevant answers >= 80 chars must not bypass check
    # ----------------------------------------------------------------------
    def test_issue_07_long_irrelevant_answer_not_bypassed(self):
        """Irrelevant answer >= 80 characters must be diagnosed as UNCERTAIN, not WELL_DEFENDED."""
        question = "请问如何解决 Redis 缓存击穿？"
        # 100+ character irrelevant chit-chat with some tech-sounding words
        long_irrelevant = (
            "今天天气真好，我上午吃了一个苹果，下午喝了一杯咖啡，"
            "然后我开始写各种各样的代码，写了非常非常多的代码，"
            "感觉心情非常愉快，工作非常努力，以后也会继续努力工作，"
            "希望团队能够越来越好，大家共同进步。"
        )
        self.assertGreater(len(long_irrelevant), 80)
        res = self.engine.analyze_question(question, long_irrelevant)
        self.assertEqual(res.diagnosis, QuestionDiagnosis.UNCERTAIN)
        self.assertFalse(res.can_revise)
        self.assertEqual(res.refined_answer, "")

    # ----------------------------------------------------------------------
    # ISSUE-08: Unit regex and strict baseline regex
    # ----------------------------------------------------------------------
    def test_issue_08_no_false_positive_metrics_on_letter_s(self):
        """English words containing letter 's' must not falsely trigger has_metrics."""
        question = "Please introduce your background"
        # Answer has words with 's': this, is, skills, response
        answer = "This is my background, my skills include system design and response handling."
        res = self.engine.analyze_question(question, answer)
        # Should NOT be diagnosed as METRIC_DRIFT
        self.assertNotEqual(res.diagnosis, QuestionDiagnosis.METRIC_DRIFT)

    def test_issue_08_no_false_positive_baseline_on_preposition_cong(self):
        """Preposition '从' must not falsely trigger has_baseline for metric claim."""
        question = "请介绍你的性能优化经历"
        # Answer uses '从' as preposition without a baseline range, but claims 50% gain
        answer = "从架构层面考虑，我负责优化后性能提升了 50%。"
        res = self.engine.analyze_question(question, answer)
        # Must be METRIC_DRIFT because '从架构层面' is not a baseline
        self.assertEqual(res.diagnosis, QuestionDiagnosis.METRIC_DRIFT)

    def test_issue_08_valid_baseline_range_recognized(self):
        """Valid baseline ranges using '从...到...' or '由...提升至...' are recognized."""
        question = "请介绍你的性能优化经历"
        answer1 = "通过参数调优，耗时从 200ms 降低到 50ms。"
        res1 = self.engine.analyze_question(question, answer1)
        self.assertEqual(res1.diagnosis, QuestionDiagnosis.WELL_DEFENDED)

        answer2 = "以开源框架为 Baseline，吞吐量由 1000 提升至 1500。"
        res2 = self.engine.analyze_question(question, answer2)
        self.assertEqual(res2.diagnosis, QuestionDiagnosis.WELL_DEFENDED)

    # ----------------------------------------------------------------------
    # R4-02: Negative tech statement vs affirmative unverified tech claim
    # ----------------------------------------------------------------------
    def test_r4_02_negative_statement_boundary_handling(self):
        """Negative tech statement ('没用过 Redis') is preserved, not diagnosed as metric drift, status is not failed."""
        answer = "这块技术我没用过 Redis。"
        res = self.engine.analyze_question(
            question="请谈谈你在 Redis 方面的实战经验",
            answer=answer,
            fact_guard=self.fact_guard
        )
        self.assertEqual(res.diagnosis, QuestionDiagnosis.EXPERIENCE_BOUNDARY)
        self.assertFalse(res.can_revise)
        self.assertEqual(res.refined_answer, "")
        self.assertIn(res.verification_status, ["unverified", "verified"])
        self.assertNotEqual(res.verification_status, "revision_failed_fact_check")
        self.assertNotEqual(res.verification_status, "tech_unverified")

        # Mixed: negative statement + verified tech and metric
        answer_mixed = "我没用过 Redis，但在项目中负责查询接口开发，耗时从 200ms 降到 100ms。"
        res_mixed = self.engine.analyze_question(
            question="请介绍查询接口优化经验",
            answer=answer_mixed,
            fact_guard=self.fact_guard
        )
        self.assertEqual(res_mixed.diagnosis, QuestionDiagnosis.WELL_DEFENDED)
        self.assertEqual(res_mixed.verification_status, "verified")
        self.assertIn("没用过 Redis", res_mixed.refined_answer)

    def test_r4_02_affirmative_unverified_tech_strictly_flagged(self):
        """Affirmative unverified tech ('我用 Redis 实现了多级缓存') must NOT be exempted or marked as verified."""
        answer = "我用 Redis 实现了多级缓存。"
        res = self.engine.analyze_question(
            question="请介绍缓存方案",
            answer=answer,
            fact_guard=self.fact_guard
        )
        self.assertEqual(res.diagnosis, QuestionDiagnosis.METRIC_DRIFT)
        self.assertNotEqual(res.verification_status, "verified")
        self.assertNotEqual(res.verification_status, "verified_with_tech_context")
        self.assertEqual(res.verification_status, "tech_unverified")
        self.assertIn("Redis", res.analysis_zh)
        self.assertIn("缺少底稿依据", res.analysis_zh)

    # ----------------------------------------------------------------------
    # R4-03: Conservative revision no unsupported attribution or lead or presumption
    # ----------------------------------------------------------------------
    def test_r4_03_conservative_revision_no_unsupported_attribution_or_lead_or_presumption(self):
        """Conservative revision must state '未提供基线数据', moderate lead verbs, and drop unsupported attribution/direction."""
        answer = "我主导了查询接口重构，从而使得访问速度提升了 50%。"
        unverified = [{"claimed_metric": "50%"}]
        drifts = []
        revised = self.engine._create_conservative_revision(
            answer, drifts, unverified, fact_guard=self.fact_guard
        )

        self.assertNotIn("50%", revised)
        self.assertIn("未提供基线数据", revised)
        self.assertNotIn("没有压测数据", revised)
        self.assertNotIn("缺乏基线压测数据", revised)
        self.assertNotIn("提升了", revised)
        self.assertNotIn("从而使得", revised)
        self.assertNotIn("我主导", revised)
        self.assertIn("负责", revised)
        self.assertIn("查询接口重构", revised)
        self.assertIn("访问速度", revised)


# ============================================================================
# Post-Interview Long Transcript & Checklist Integration Tests
# ============================================================================

from core.interview_debrief import (
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

    turn1 = checklist.dialogue_turns[0]
    assert turn1.turn_score < 90.0
    assert any("夸大" in bp or "过度断言" in bp for bp in checklist.blindspot_summary)

    assert len(checklist.high_frequency_follow_ups) > 0
    assert any("0.01%" in m for m in checklist.mandatory_metrics_to_memorize)
    assert len(checklist.failure_contingency_scripts) > 0
    assert "# 🎯 面试全复盘战报与 (N+1) 面备战清单" in checklist.markdown_report


def test_debrief_empty_transcript():
    checklist = PostInterviewDebriefEngine.debrief("")
    assert checklist.total_turns == 0
    assert checklist.next_round_readiness_score == 0.0
    assert "未解析到有效" in checklist.markdown_report


class TestInterviewReviewContract(unittest.TestCase):
    def setUp(self):
        import copy
        from core.interview_review_contract import build_interview_review_snapshot
        self.note = {
            "company": "Example Co",
            "position": "Backend Engineer",
            "round": "Technical interview",
            "date": "2026-09-24",
            "questions": "How did you scale the API? I explained the cache layer.",
            "self_reflection": "I omitted the baseline and traffic volume.",
            "difficulty_points": "Capacity estimation",
            "mood": "nervous",
            "untrusted_extra": "must not enter snapshot",
        }
        self.snapshot = build_interview_review_snapshot(self.note)
        self.payload = {
            "summary": {
                "text": "回答提到了缓存层，但缺少流量基线。",
                "evidence_refs": [{
                    "source": "interview_note",
                    "path": "/self_reflection",
                    "excerpt": "omitted the baseline",
                }],
            },
            "observations": [{
                "id": "obs-1",
                "text": "复盘记录指出未提供基线。",
                "evidence_refs": [{
                    "source": "interview_note",
                    "path": "/self_reflection",
                    "excerpt": "the baseline",
                }],
            }],
            "clarifications": [{
                "id": "clarify-1",
                "question": "当时的请求量和基线是多少？",
                "evidence_refs": [{
                    "source": "interview_note",
                    "path": "/questions",
                    "excerpt": "How did you scale the API?",
                }],
            }],
            "practice_focuses": [],
            "next_questions": [],
        }

    def test_snapshot_whitelists_and_copies_note_text(self):
        from core.interview_review_contract import build_interview_review_snapshot
        snapshot = build_interview_review_snapshot(self.note)
        self.assertNotIn("untrusted_extra", snapshot["note"])
        self.note["questions"] = "changed after snapshot"
        self.assertEqual(snapshot["note"]["questions"], "How did you scale the API? I explained the cache layer.")

    def test_valid_grounded_payload_is_normalized(self):
        from core.interview_review_contract import validate_interview_review_proposal
        result = validate_interview_review_proposal(self.payload, self.snapshot)
        self.assertEqual(result["summary"]["text"], self.payload["summary"]["text"])
        self.assertEqual(result["observations"][0]["evidence_refs"][0]["path"], "/self_reflection")

    def test_rejects_forged_refs_duplicate_ids_and_extra_fields(self):
        import copy
        from core.interview_review_contract import validate_interview_review_proposal, InterviewReviewContractError
        forged = copy.deepcopy(self.payload)
        forged["summary"]["evidence_refs"][0]["excerpt"] = "not in the note"
        with self.assertRaisesRegex(InterviewReviewContractError, "does not match"):
            validate_interview_review_proposal(forged, self.snapshot)

        duplicate = copy.deepcopy(self.payload)
        duplicate["clarifications"][0]["id"] = "obs-1"
        with self.assertRaisesRegex(InterviewReviewContractError, "unique"):
            validate_interview_review_proposal(duplicate, self.snapshot)

        extra = copy.deepcopy(self.payload)
        extra["observations"][0]["score"] = 100
        with self.assertRaisesRegex(InterviewReviewContractError, "unexpected fields"):
            validate_interview_review_proposal(extra, self.snapshot)

    def test_rejects_unsupported_paths_and_unbounded_items(self):
        import copy
        from core.interview_review_contract import validate_interview_review_proposal, InterviewReviewContractError
        invalid_path = copy.deepcopy(self.payload)
        invalid_path["summary"]["evidence_refs"][0]["path"] = "/company"
        with self.assertRaisesRegex(InterviewReviewContractError, "outside the allowed"):
            validate_interview_review_proposal(invalid_path, self.snapshot)

        too_many = copy.deepcopy(self.payload)
        too_many["observations"] = [copy.deepcopy(self.payload["observations"][0]) for _ in range(11)]
        with self.assertRaisesRegex(InterviewReviewContractError, "at most 10"):
            validate_interview_review_proposal(too_many, self.snapshot)

    def test_safe_fallback_is_valid_only_for_empty_evidence(self):
        from core.interview_review_contract import (
            build_interview_review_snapshot,
            safe_empty_interview_review_proposal,
            validate_interview_review_proposal,
        )
        empty_snapshot = build_interview_review_snapshot({})
        safe = safe_empty_interview_review_proposal()
        self.assertEqual(validate_interview_review_proposal(safe, empty_snapshot), safe)


if __name__ == "__main__":
    unittest.main()

