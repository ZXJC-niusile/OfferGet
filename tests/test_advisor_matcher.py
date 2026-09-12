"""
OfferGet Advisor Matcher Unit Tests
====================================
Tests for:
1. AdvisorProfile and CandidateProfile ingestion and surname parsing.
2. Advisor publication timeline analysis and paradigm transition detection.
3. Academic intersection matching, technical overlap, and 0-100% scoring.
4. High-EQ Chinese advisor outreach email generation with anti-hallucination.
5. Anti-Pigeon & Academic Etiquette Guidelines (verbal commitment tiers, templates).
6. End-to-end convenience function match_advisor_and_draft_email.
"""

import unittest
from core.advisor_matcher import (
    AdvisorMatcher,
    AdvisorProfile,
    CandidateProfile,
    Publication,
    match_advisor_and_draft_email
)


class TestAdvisorMatcher(unittest.TestCase):

    def setUp(self):
        self.matcher = AdvisorMatcher()

        # Realistic Advisor Data (e.g. AI Professor pivoting from traditional NLP to Embodied & Multimodal LLM)
        self.sample_advisor_data = {
            "name": "张伟",
            "title": "长聘教授",
            "institution": "清华大学",
            "department": "计算机科学与技术系",
            "research_topics": ["多模态大模型", "具身智能", "自然语言处理", "知识图谱"],
            "lab_projects": [
                "面向真实物理场景的具身移动操作大模型系统",
                "国家自然科学基金重点项目：基于因果推理的大模型可信决策"
            ],
            "recent_publications": [
                {
                    "title": "A Rule-based Expert System for Clinical Event Extraction",
                    "year": 2018,
                    "venue": "ACL 2018",
                    "keywords": ["rule-based", "crf", "clinical notes", "statistical nlp"],
                    "core_contribution": "提出基于隐马尔可夫与人工特征工程的临床实体抽取规则引擎"
                },
                {
                    "title": "Pre-trained Language Models for Structured Knowledge Injection",
                    "year": 2021,
                    "venue": "EMNLP 2021",
                    "keywords": ["transformer", "bert", "knowledge graph", "deep learning"],
                    "core_contribution": "设计了一种将实体知识嵌入Transformer注意力机制的自监督预训练方法"
                },
                {
                    "title": "Embodied-LLM: Grounded Planning and Action via Multimodal Models",
                    "year": 2024,
                    "venue": "CVPR 2024",
                    "keywords": ["multimodal", "embodied ai", "llm", "diffusion", "robotics"],
                    "core_contribution": "构建了融合视觉语言大模型与扩散策略的端到端具身机器人导航规划架构"
                }
            ],
            "email": "zhangwei@tsinghua.edu.cn"
        }

        # Realistic Candidate Profile (e.g. top CS undergraduate with CV/Robotics project)
        self.sample_candidate_data = {
            "name": "李明",
            "undergraduate_school": "华中科技大学",
            "major": "计算机科学与技术",
            "grade": "2022级本科生（大三）",
            "target_degree": "direct_phd",
            "gpa": "3.92/4.0",
            "rank": "1/180",
            "rank_percentage": 0.0055,
            "honors_awards": [
                "国家奖学金",
                "全国大学生数学建模竞赛一等奖",
                "ACM-ICPC区域赛银奖"
            ],
            "projects": [
                {
                    "name": "基于强化学习与扩散模型的机械臂灵巧抓取系统",
                    "description": "设计并复现了基于PyTorch与MuJoCo的闭环抓取策略，将复杂光照下的抓取成功率提升了18%",
                    "tech_stack": ["PyTorch", "MuJoCo", "Diffusion", "强化学习", "ROS"]
                }
            ],
            "skills": ["PyTorch", "ROS", "Diffusion", "C++", "MuJoCo", "具身智能"],
            "research_interests": ["具身智能", "多模态大模型", "机器人自主决策"],
            "coursework": ["数据结构与算法 (98)", "深度学习 (96)", "机器人学基础 (95)"],
            "read_advisor_papers": [
                "Embodied-LLM: Grounded Planning and Action via Multimodal Models"
            ],
            "email": "liming@hust.edu.cn",
            "phone": "138-0000-8888",
            "wechat": "liming_cs"
        }

    # ------------------------------------------------------------------------
    # 1. Profile Ingestion & Normalization Tests
    # ------------------------------------------------------------------------

    def test_advisor_profile_ingestion_and_surname(self):
        """Test proper ingestion and extraction of Chinese surnames."""
        prof_single = AdvisorProfile(name="张伟", title="教授")
        self.assertEqual(prof_single.surname, "张")

        prof_compound = AdvisorProfile(name="欧阳振华", title="博导")
        self.assertEqual(prof_compound.surname, "欧阳")

        prof_empty = AdvisorProfile(name="", title="副教授")
        self.assertEqual(prof_empty.surname, "老师")

    def test_candidate_profile_ingestion(self):
        """Test candidate profile normalization."""
        cand_prof = self.matcher._ensure_candidate_profile(self.sample_candidate_data)
        self.assertEqual(cand_prof.name, "李明")
        self.assertEqual(cand_prof.undergraduate_school, "华中科技大学")
        self.assertEqual(len(cand_prof.skills), 6)
        self.assertEqual(cand_prof.rank_percentage, 0.0055)

    # ------------------------------------------------------------------------
    # 2. Advisor Research Timeline Tests
    # ------------------------------------------------------------------------

    def test_advisor_timeline_analysis(self):
        """Test publication timeline grouping, phase breakdown, and paradigm shifts."""
        timeline = self.matcher.analyze_advisor_timeline(self.sample_advisor_data)

        self.assertEqual(timeline["total_publications"], 3)
        self.assertEqual(timeline["year_range"], (2018, 2024))
        self.assertIn(2018, timeline["publications_by_year"])
        self.assertIn(2024, timeline["publications_by_year"])

        # Check chronological phases
        phases = timeline["phases"]
        self.assertIn("early_phase", phases)
        self.assertIn("consolidation_phase", phases)
        self.assertIn("recent_pivot", phases)
        self.assertIn(2024, phases["recent_pivot"]["years"])

        # Check paradigm shift detection (from traditional NLP to DL and modern multimodal LLM)
        summary = timeline["technical_evolution_summary"]
        self.assertIn("张伟老师在学术生涯中", summary)
        self.assertTrue(
            "经典统计" in summary or "深度学习" in summary or "多模态" in summary or "大模型" in summary
        )

    def test_advisor_timeline_empty_fallback(self):
        """Test timeline gracefully handles advisor with zero publications."""
        advisor_no_pubs = {
            "name": "王教授",
            "research_topics": ["量子计算", "密码学"]
        }
        timeline = self.matcher.analyze_advisor_timeline(advisor_no_pubs)
        self.assertEqual(timeline["total_publications"], 0)
        self.assertEqual(timeline["year_range"], (0, 0))
        self.assertIn("王教授老师当前重点围绕", timeline["technical_evolution_summary"])

    # ------------------------------------------------------------------------
    # 3. Academic Intersection Matching Tests
    # ------------------------------------------------------------------------

    def test_match_candidate_to_advisor_high_match(self):
        """Test strong overlap between candidate's robotics/diffusion and advisor's 2024 CVPR paper."""
        match_res = self.matcher.match_candidate_to_advisor(
            self.sample_advisor_data, self.sample_candidate_data
        )

        score = match_res["intersection_score"]
        self.assertGreaterEqual(score, 75.0)
        self.assertLessEqual(score, 100.0)

        # Overlap points should catch PyTorch, ROS, Diffusion, etc.
        overlaps = [o.lower() for o in match_res["technical_overlap_points"]]
        self.assertTrue(any("diffusion" in o for o in overlaps))
        self.assertTrue(any("具身智能" in t for t in match_res["mutual_research_topics"]))

        # Advisor recent focus match should be True (2024 CVPR Embodied-LLM)
        self.assertTrue(match_res["advisor_recent_focus_match"])
        self.assertIn("先锋突击策略", match_res["strategic_angle"])

        # Scoring breakdown exists
        breakdown = match_res["scoring_breakdown"]
        self.assertIn("topic_alignment", breakdown)
        self.assertIn("tech_overlap", breakdown)
        self.assertIn("candidate_foundation", breakdown)
        self.assertIn("recency_bonus", breakdown)

    def test_match_candidate_to_advisor_low_match(self):
        """Test cross-disciplinary applicant with minimal intersection."""
        unrelated_candidate = {
            "name": "王小华",
            "undergraduate_school": "某工科院校",
            "major": "环境工程",
            "skills": ["水质监测", "CAD绘图", "环境化学分析"],
            "research_interests": ["污水处理与固废资源化"],
            "gpa": "3.2/4.0",
            "rank": "35/100"
        }
        match_res = self.matcher.match_candidate_to_advisor(
            self.sample_advisor_data, unrelated_candidate
        )
        self.assertLess(match_res["intersection_score"], 50.0)
        self.assertIn("跨领域探索", match_res["match_tier"])

    # ------------------------------------------------------------------------
    # 4. Outreach Email Generation & Anti-Hallucination Tests
    # ------------------------------------------------------------------------

    def test_generate_outreach_email_structure_and_hook(self):
        """Test outreach email conforms to 4 key sections: Hook, Reflection, Value Prop, Attachment."""
        email_data = self.matcher.generate_outreach_email(
            advisor=self.sample_advisor_data,
            candidate=self.sample_candidate_data,
            email_scenario="summer_camp",
            target_degree="direct_phd"
        )

        # 1. Subject check
        subject = email_data["subject"]
        self.assertIn("[保研夏令营]", subject)
        self.assertIn("华中科技大学-计算机科学与技术-李明", subject)
        self.assertIn("张伟老师直博生", subject)

        # 2. Salutation check
        self.assertEqual(email_data["salutation"], "尊敬的张老师：")

        # 3. Profile hook check (2 sentences, clear rank/GPA)
        hook = email_data["profile_hook"]
        self.assertIn("GPA 3.92/4.0", hook)
        self.assertIn("专业排名 1/180", hook)
        self.assertIn("国家奖学金", hook)

        # 4. Academic Reflection check (Zero empty flattery, cites verified paper)
        reflection = email_data["academic_reflection"]
        self.assertNotIn("久仰大名", reflection)
        self.assertNotIn("德高望重", reflection)
        self.assertIn("Embodied-LLM: Grounded Planning and Action via Multimodal Models", reflection)

        # 5. Value Proposition check (Lab milestone acceleration)
        val_prop = email_data["value_proposition"]
        self.assertIn("加速", val_prop)
        self.assertIn("里程碑", val_prop)

        # 6. Attachment Guide check
        attachment = email_data["attachment_guide"]
        self.assertIn("[个人简历]_华中科技大学_李明_意向直博生.pdf", attachment)
        self.assertIn("官方成绩单", attachment)

        # 7. Sending tips
        tips = email_data["sending_tips"]
        self.assertTrue(len(tips) >= 3)

    def test_strict_anti_hallucination_in_email(self):
        """Test anti-hallucination verification reports clean on genuine inputs."""
        email_data = self.matcher.generate_outreach_email(
            advisor=self.sample_advisor_data,
            candidate=self.sample_candidate_data
        )
        report = email_data["anti_hallucination_report"]
        self.assertTrue(report["is_clean"])
        self.assertEqual(len(report["hallucinated_citations"]), 0)
        self.assertIn("严谨真实", report["audit_verdict"])

    def test_anti_hallucination_catches_fake_papers(self):
        """Test the anti-hallucination guard flags an unverified paper title."""
        fake_text = "我近期拜读了您的《Fake Hallucinated Quantum Neural Network 2026》论文，受益匪浅。"
        adv_prof = self.matcher._ensure_advisor_profile(self.sample_advisor_data)
        cand_prof = self.matcher._ensure_candidate_profile(self.sample_candidate_data)
        
        report = self.matcher._verify_anti_hallucination(fake_text, adv_prof, cand_prof)
        self.assertFalse(report["is_clean"])
        self.assertIn("Fake Hallucinated Quantum Neural Network 2026", report["hallucinated_citations"])
        self.assertIn("风险警告", report["audit_verdict"])

    # ------------------------------------------------------------------------
    # 5. Anti-Pigeon & Academic Etiquette Guidelines Tests
    # ------------------------------------------------------------------------

    def test_anti_pigeon_guidelines(self):
        """Test Anti-Pigeon guidelines and template library generation."""
        guidelines = self.matcher.generate_anti_pigeon_guidelines(
            advisor=self.sample_advisor_data,
            candidate=self.sample_candidate_data
        )

        # 1. Verbal Commitment Matrix (4 Tiers)
        matrix = guidelines["verbal_commitment_matrix"]
        self.assertEqual(len(matrix), 4)
        tier_names = [item["tier"] for item in matrix]
        self.assertTrue(any("Tier 1" in t for t in tier_names))
        self.assertTrue(any("Tier 2" in t for t in tier_names))
        self.assertTrue(any("Tier 3" in t for t in tier_names))
        self.assertTrue(any("Tier 4" in t for t in tier_names))

        # 2. Timeline Framework
        timeline_fw = guidelines["timeline_framework"]
        self.assertIn("9月28日 0:00 (全国推免系统开放)", timeline_fw)

        # 3. Reputation Imperatives
        rep = guidelines["reputation_imperatives"]
        self.assertIn("华中科技大学", rep)
        self.assertIn("黑名单", rep or rep)

        # 4. Templates
        templates = guidelines["templates"]
        self.assertIn("decline_summer_camp", templates)
        self.assertIn("release_verbal_commitment", templates)
        self.assertIn("lock_offer_confirmation", templates)
        self.assertIn("follow_up_unanswered", templates)

        # Check polite rejection content
        decline_text = templates["decline_summer_camp"]
        self.assertIn("尊敬的张老师：", decline_text)
        self.assertIn("放弃参加课题组后续的面试/夏令营考核", decline_text)
        self.assertIn("李明", decline_text)

        # Check lock offer content
        lock_text = templates["lock_offer_confirmation"]
        self.assertIn("绝无任何变数", lock_text)
        self.assertIn("9月28日国家推免系统开放当日", lock_text)

    # ------------------------------------------------------------------------
    # 6. Top-Level Convenience Function Integration Test
    # ------------------------------------------------------------------------

    def test_match_advisor_and_draft_email_convenience_function(self):
        """Test top-level convenience wrapper match_advisor_and_draft_email."""
        result = match_advisor_and_draft_email(
            advisor_data=self.sample_advisor_data,
            candidate_data=self.sample_candidate_data,
            email_scenario="pre_recommendation",
            target_degree="master"
        )

        self.assertIn("advisor_timeline", result)
        self.assertIn("intersection_match", result)
        self.assertIn("outreach_email", result)
        self.assertIn("anti_pigeon_guidelines", result)
        self.assertIn("anti_hallucination_report", result)

        # Verify subject adapts to pre_recommendation & master
        subject = result["outreach_email"]["subject"]
        self.assertIn("[预推免自荐]", subject)
        self.assertIn("硕士研究生", subject)

        # Anti-hallucination clean
        self.assertTrue(result["anti_hallucination_report"]["is_clean"])


if __name__ == "__main__":
    unittest.main()
