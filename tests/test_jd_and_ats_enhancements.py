"""
Unit test suite for JD & ATS Enhancements (tests/test_jd_and_ats_enhancements.py)
================================================================================
Verifies additions ported from ats-optimized-resume-agent-skill & resume-jd-optimizer-cn:
1. Five new enterprise role taxonomies in TaxonomyRegistry (data_analyst, ai_product, qa_test_engineer, ui_ux_design, growth_strategy)
2. Role-specific KPI metrics lexicon in QualityRuleRegistry / core.lexicon
3. Expanded ADJACENT_SKILLS mapping in JDMatcher for non-AI stacks (Kafka/RocketMQ, React/Vue, Flink/Spark, etc.)
4. BossIntroWriter & HeadhunterIntroWriter in CareerCommunicationKit
"""

import unittest
from core.communication_kit import CareerCommunicationKit, LetterType
from core.jd_compat import classify_role_taxonomy
from core.lexicon import ROLE_KPI_LEXICON
from core.registry import QualityRuleRegistry, TaxonomyRegistry
from modules.jd_analyst.matcher import JDMatcher
from modules.jd_analyst.models import (
    CandidateProfile,
    CoreSkill,
    DecodedJD,
    HardThreshold,
    SkillImportance,
)


class TestJdAndAtsEnhancements(unittest.TestCase):

    def test_01_new_role_taxonomies_classification(self):
        """Test classification of the 5 newly added enterprise taxonomies."""
        # 1. Data Analyst
        jd_da = "诚聘资深数据分析师，熟练使用 SQL 取数、Tableau 看板设计，主导业务漏斗分析与 A/B 测试归因。"
        res_da = classify_role_taxonomy(jd_da)
        self.assertEqual(res_da["role_key"], "data_analyst")
        self.assertIn("数据分析与商业智能", res_da["taxonomy"]["title"])

        # 2. AI Product Manager
        jd_aipm = "AI 产品经理，负责大模型落地场景探索，精通 Prompt 调优与 Agent 智能体架构，推进模型评测与 RAG 落地。"
        res_aipm = classify_role_taxonomy(jd_aipm)
        self.assertEqual(res_aipm["role_key"], "ai_product")
        self.assertIn("AI 产品经理", res_aipm["taxonomy"]["title"])

        # 3. QA / Test Engineer
        jd_qa = "测试开发工程师，负责自动化测试体系建设，掌握 Selenium、Pytest 框架及 JMeter 接口性能压测，降低线上漏测率。"
        res_qa = classify_role_taxonomy(jd_qa)
        self.assertEqual(res_qa["role_key"], "qa_test_engineer")
        self.assertIn("测试开发与质量保障", res_qa["taxonomy"]["title"])

        # 4. UI/UX Design
        jd_ui = "资深 UI/UX 设计师，负责移动端与 Web 端的视觉设计与交互设计，主导 Figma 设计系统组件库规范。"
        res_ui = classify_role_taxonomy(jd_ui)
        self.assertEqual(res_ui["role_key"], "ui_ux_design")
        self.assertIn("UI/UX 设计", res_ui["taxonomy"]["title"])

        # 5. User Growth Strategy
        jd_growth = "用户增长策略专家，通过转化漏斗与裂变活动设计推动用户留存，利用 A/B 实验持续压降 CAC 并提升 LTV。"
        res_growth = classify_role_taxonomy(jd_growth)
        self.assertEqual(res_growth["role_key"], "growth_strategy")
        self.assertIn("用户增长", res_growth["taxonomy"]["title"])

    def test_02_role_kpi_lexicon(self):
        """Test availability and structure of ROLE_KPI_LEXICON."""
        self.assertIn("product", ROLE_KPI_LEXICON)
        self.assertIn("ai_product", ROLE_KPI_LEXICON)
        self.assertIn("technical", ROLE_KPI_LEXICON)
        self.assertIn("data_analyst", ROLE_KPI_LEXICON)

        # Check KPI contents
        self.assertIn("DAU", ROLE_KPI_LEXICON["product"])
        self.assertIn("QPS", ROLE_KPI_LEXICON["technical"])
        self.assertIn("看板数量", ROLE_KPI_LEXICON["data_analyst"])
        self.assertIn("任务成功率", ROLE_KPI_LEXICON["ai_product"])

        # Registry getter
        lex_copy = QualityRuleRegistry.get_role_kpi_lexicon()
        self.assertEqual(lex_copy["technical"], ROLE_KPI_LEXICON["technical"])

    def test_03_expanded_adjacent_skills_matching(self):
        """Test that non-AI adjacent stacks provide partial match credit."""
        matcher = JDMatcher()

        # Check adjacent definitions exist
        self.assertIn("rocketmq", matcher.ADJACENT_SKILLS["kafka"])
        self.assertIn("vue", matcher.ADJACENT_SKILLS["react"])
        self.assertIn("spark streaming", matcher.ADJACENT_SKILLS["flink"])
        self.assertIn("powerbi", matcher.ADJACENT_SKILLS["tableau"])

        # Test matching: JD requires Kafka, candidate only has RocketMQ
        jd = DecodedJD(
            raw_text="需要精通 Kafka 消息队列",
            job_title="后端工程师",
            company_or_dept="基础架构部",
            hard_thresholds=[],
            core_skills=[
                CoreSkill(name="Kafka", category="middleware", importance="must_have", domain="后端开发")
            ],
            implicit_signals=[],
        )
        cand = CandidateProfile(
            name="李四",
            education_level="本科",
            years_of_experience=3.0,
            skills=["RocketMQ", "Java", "MySQL"],
            project_descriptions=["基于 RocketMQ 实现异步解耦与流量削峰"],
            raw_resume_text="熟练掌握 RocketMQ 消息队列中间件",
        )

        res = matcher.match(jd, cand)
        # Should achieve partial adjacent score (0.5) instead of 0.0
        self.assertGreater(res.must_have_score, 0.4)
        self.assertLess(res.must_have_score, 0.9)

    def test_04_boss_intro_writer(self):
        """Test BossIntroWriter produces concise high-conversion greeting."""
        letter = CareerCommunicationKit.boss_intro(
            candidate_name="王五",
            target_role="数据分析师",
            experience_summary="3年消费金融数据分析经验",
            core_actions=["搭建全链路风控看板", "重构核心流失漏斗"],
            verified_outcomes=["看板响应耗时降低60%", "核心客群留存率提升12%"],
            target_company_interest="团队在即时风控特征计算上的实践",
        )
        self.assertEqual(letter.letter_type, LetterType.BOSS_INTRO)
        self.assertIn("王五", letter.subject)
        self.assertIn("数据分析师", letter.body_text)
        self.assertIn("消费金融", letter.body_text)
        self.assertIn("留存率提升12%", letter.body_text)
        # Verify concise length suitable for mobile app greeting
        self.assertLess(len(letter.body_text), 220)
        self.assertGreater(len(letter.body_text), 60)

    def test_05_headhunter_intro_writer(self):
        """Test HeadhunterIntroWriter produces structured candidate talent card."""
        letter = CareerCommunicationKit.headhunter_intro(
            candidate_name="赵六",
            current_or_recent_title="高级后端架构师",
            years_of_experience="6年",
            core_focus_areas=["高并发交易中台", "分布式存储治理", "DDD领域驱动设计"],
            representative_impact=[
                "主导双十一万级 QPS 订单结算重构，全链路 P99 降至 25ms",
                "主导万级分库分表与 TiDB 平滑迁移，零资损保障",
            ],
            target_job_preferences="期望base北京，关注独角兽核心中台或大厂核心研发线",
            potential_risks_or_boundaries="跳槽频率极低（6年2段）；统招一本学历；暂不考虑单休与大小周团队",
        )
        self.assertEqual(letter.letter_type, LetterType.HEADHUNTER_INTRO)
        self.assertIn("人才自荐卡", letter.subject)
        self.assertIn("高并发交易中台", letter.body_text)
        self.assertIn("暂不考虑单休与大小周", letter.body_text)
        self.assertIn("TiDB", letter.body_text)


if __name__ == "__main__":
    unittest.main()
