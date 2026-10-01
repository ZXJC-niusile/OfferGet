"""
Unit tests for OfferGet Baoyan Pipeline & Academic Schema Engine.
"""

import json
import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.baoyan_pipeline import (
    BaoyanPipeline,
    BaoyanStatus,
    GOLDEN_PATH,
    ALLOWED_TRANSITIONS,
    validate_academic_profile,
    generate_camp_checklist,
)


class TestBaoyanPipeline(unittest.TestCase):

    def setUp(self):
        self.academic_profile_path = PROJECT_ROOT / "examples" / "academic_profile.json"
        self.sample_advisor_path = PROJECT_ROOT / "examples" / "sample_advisor.json"

        with open(self.academic_profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

        with open(self.sample_advisor_path, "r", encoding="utf-8") as f:
            self.advisor_data = json.load(f)

    # =========================================================================
    # 1. Academic Profile Schema & Sample Profile Verification
    # =========================================================================

    def test_01_sample_academic_profile_validity(self):
        """Verify the sample academic profile adheres to all schema rules."""
        res = validate_academic_profile(self.academic_profile_path)
        self.assertTrue(res["valid"], f"Validation failed with errors: {res.get('errors')}")
        self.assertEqual(len(res["errors"]), 0)
        self.assertGreaterEqual(res["competitiveness_score"], 90.0)

        # Check candidate metrics
        metrics = res["metrics"]
        self.assertEqual(metrics["candidate_name"], "林书扬")
        self.assertEqual(metrics["university"], "南京大学 (Nanjing University)")
        self.assertEqual(metrics["gpa"], 3.92)
        self.assertEqual(metrics["rank"], "2/150")
        self.assertEqual(metrics["rank_percent"], "Top 1.5%")
        self.assertEqual(metrics["cet6"], 618)
        self.assertEqual(metrics["ccf_a_count"], 1)
        self.assertEqual(metrics["ccf_b_count"], 1)
        self.assertEqual(metrics["under_review_count"], 1)
        self.assertTrue(metrics["has_national_scholarship"])
        self.assertTrue(metrics["has_tier1_competition"])
        self.assertGreaterEqual(metrics["target_schools_count"], 4)

    def test_02_sample_academic_profile_data_content(self):
        """Verify explicit data points in academic_profile.json."""
        # GPA, Rank, English
        standing = self.profile_data["academic_standing"]
        self.assertEqual(standing["gpa"], 3.92)
        self.assertEqual(standing["max_gpa"], 4.0)
        self.assertEqual(standing["rank"], "2/150")
        self.assertEqual(standing["rank_percent"], "Top 1.5%")
        self.assertEqual(standing["english"]["cet6"], 618)

        # Papers: 1 CCF-A (NeurIPS 2024 Co-first), 1 CCF-B under_review
        pubs = self.profile_data["publications"]
        self.assertEqual(len(pubs), 2)

        p1 = pubs[0]
        self.assertEqual(p1["ccf_rank"], "CCF-A")
        self.assertIn("NeurIPS 2024", p1["venue"])
        self.assertEqual(p1["author_role"], "co_first_author")
        self.assertIn(p1["status"], ["accepted", "published"])

        p2 = pubs[1]
        self.assertEqual(p2["ccf_rank"], "CCF-B")
        self.assertEqual(p2["status"], "under_review")
        self.assertEqual(p2["author_role"], "first_author")

        # Graduation Thesis & Projects with simulation vs real experiment tags
        thesis = self.profile_data["graduation_thesis"]
        self.assertEqual(thesis["experiment_type"], "real_experiment")
        self.assertIn("real_experiment", thesis["tags"])
        self.assertTrue(len(thesis["individual_contribution"]) > 20)

        projects = self.profile_data["projects"]
        self.assertGreaterEqual(len(projects), 2)
        has_real = any(p.get("experiment_type") == "real_experiment" or "real_experiment" in p.get("tags", []) for p in projects)
        has_sim = any(p.get("experiment_type") == "simulation" or "simulation" in p.get("tags", []) for p in projects)
        self.assertTrue(has_real, "Expected at least one project with real experiment tag")
        self.assertTrue(has_sim, "Expected at least one project with simulation tag")

        # Competitions
        comps = self.profile_data["competitions"]
        comp_names = [c["name"] for c in comps]
        awards = [c["award"] for c in comps]
        self.assertTrue(any("MCM" in name or "ICM" in name for name in comp_names))
        self.assertTrue(any("Finalist" in award for award in awards))
        self.assertTrue(any("电子设计" in name or "NUEDC" in name for name in comp_names))
        self.assertTrue(any("一等奖" in award or "First Prize" in award for award in awards))

        # Honors
        honors = self.profile_data["honors"]
        self.assertTrue(any("国家奖学金" in h["name"] for h in honors))

        # Target Schools & Advisors
        targets = self.profile_data["target_schools"]
        self.assertGreaterEqual(len(targets), 4)
        school_names = " ".join([t["school_name"] for t in targets])
        self.assertIn("清华", school_names)
        self.assertIn("北京大学", school_names)
        self.assertIn("浙江大学", school_names)

    def test_03_profile_validation_errors(self):
        """Test validator catches schema violations and missing required fields."""
        # Missing candidate
        bad_profile_1 = {"academic_standing": {"gpa": 3.9, "rank": "1/100"}}
        res1 = validate_academic_profile(bad_profile_1)
        self.assertFalse(res1["valid"])
        self.assertTrue(any("candidate" in e for e in res1["errors"]))

        # Invalid GPA
        bad_profile_2 = {
            "candidate": {"name": "Test", "university": "PKU", "major": "CS", "email": "a@pku.edu.cn", "phone": "123"},
            "academic_standing": {"gpa": 9.9, "rank": "1/100"}
        }
        res2 = validate_academic_profile(bad_profile_2)
        self.assertFalse(res2["valid"])
        self.assertTrue(any("GPA" in e for e in res2["errors"]))

        # Invalid CCF rank and invalid publication status
        bad_profile_3 = {
            "candidate": {"name": "Test", "university": "PKU", "major": "CS", "email": "a@pku.edu.cn", "phone": "123"},
            "academic_standing": {"gpa": 3.8, "rank": "5/100", "cet6": 550},
            "publications": [
                {
                    "title": "Bad Paper",
                    "venue": "Fake Conf",
                    "ccf_rank": "CCF-SSS",  # Invalid
                    "author_role": "first_author",
                    "status": "pending_mystery"  # Invalid
                }
            ]
        }
        res3 = validate_academic_profile(bad_profile_3)
        self.assertFalse(res3["valid"])
        self.assertTrue(any("CCF rank" in e for e in res3["errors"]))
        self.assertTrue(any("status" in e for e in res3["errors"]))

        # Project missing experiment_type / simulation vs real experiment indicator
        bad_profile_4 = {
            "candidate": {"name": "Test", "university": "PKU", "major": "CS", "email": "a@pku.edu.cn", "phone": "123"},
            "academic_standing": {"gpa": 3.8, "rank": "5/100", "cet6": 550},
            "projects": [
                {
                    "name": "Project without experiment indicator",
                    "role": "Lead",
                    "individual_contribution": "Did lots of work",
                    "tags": ["machine_learning"]  # Missing real_experiment / simulation
                }
            ]
        }
        res4 = validate_academic_profile(bad_profile_4)
        self.assertFalse(res4["valid"])
        self.assertTrue(any("simulation vs real experiment" in e for e in res4["errors"]))

    # =========================================================================
    # 2. Sample Advisor Dataset Verification
    # =========================================================================

    def test_04_sample_advisor_dataset(self):
        """Verify sample_advisor.json satisfies all professor profile specifications."""
        adv = self.advisor_data
        self.assertEqual(adv["name"], "陈建平")
        self.assertIn("清华大学", adv["institution"])
        self.assertIn("教授", adv["title"])
        self.assertTrue(len(adv["lab_name"]) > 5)

        # Research directions
        self.assertGreaterEqual(len(adv["research_directions"]), 4)

        # 4 recent representative papers
        papers = adv["representative_papers"]
        self.assertEqual(len(papers), 4)
        venues = " ".join([p["venue"] for p in papers])
        self.assertIn("OSDI", venues)
        self.assertIn("SOSP", venues)
        self.assertIn("NeurIPS", venues)
        self.assertIn("ASPLOS", venues)
        for p in papers:
            self.assertEqual(p["ccf_rank"], "CCF-A")

        # Lab compute resources
        resources = adv["lab_compute_resources"]
        self.assertIn("dedicated_gpu_cluster", resources)
        self.assertIn("network_interconnect", resources)
        self.assertIn("storage_system", resources)
        self.assertIn("per_student_quota", resources)
        self.assertIn("H800", resources["dedicated_gpu_cluster"])
        self.assertIn("A100", resources["dedicated_gpu_cluster"])

        # Prospective student expectations
        expectations = adv["prospective_student_expectations"]
        self.assertIn("enrollment_quotas_2025", expectations)
        self.assertEqual(expectations["enrollment_quotas_2025"]["phd_direct"], 2)
        self.assertGreaterEqual(len(expectations["preferred_background"]), 2)
        self.assertGreaterEqual(len(expectations["technical_skills"]), 2)
        self.assertTrue(len(expectations["advising_style_and_culture"]) > 20)
        self.assertTrue(len(expectations["financial_support_and_stipend"]) > 20)

    # =========================================================================
    # 3. Application State Machine & Golden Path
    # =========================================================================

    def test_05_canonical_golden_path_stepping(self):
        """Test the canonical 6-stage golden path progresses sequentially."""
        pipeline = BaoyanPipeline(self.profile_data)

        # Add target application at stage COLLECTING_NOTICES
        app_id = pipeline.add_target_application(
            school_name="清华大学",
            college="计算机系",
            major="计算机科学与技术",
            track="直博",
            target_advisor="陈建平 教授",
            initial_status=BaoyanStatus.COLLECTING_NOTICES
        )

        app = pipeline.get_application(app_id)
        self.assertEqual(app["status"], BaoyanStatus.COLLECTING_NOTICES.value)

        # Step through golden path:
        # COLLECTING_NOTICES -> CONTACTING_ADVISOR
        pipeline.step_golden_path(app_id, "套磁信已发出，等待回复")
        self.assertEqual(pipeline.get_application(app_id)["status"], BaoyanStatus.CONTACTING_ADVISOR.value)

        # CONTACTING_ADVISOR -> CAMP_APPLIED
        pipeline.step_golden_path(app_id, "网申系统已填报完成并提交材料")
        self.assertEqual(pipeline.get_application(app_id)["status"], BaoyanStatus.CAMP_APPLIED.value)

        # CAMP_APPLIED -> CAMP_ACCEPTED
        pipeline.step_golden_path(app_id, "初审通过，入选夏令营")
        self.assertEqual(pipeline.get_application(app_id)["status"], BaoyanStatus.CAMP_ACCEPTED.value)

        # CAMP_ACCEPTED -> PRE_RECOMMENDED
        pipeline.step_golden_path(app_id, "夏令营考核优秀，获得优秀营员拟录取资格")
        self.assertEqual(pipeline.get_application(app_id)["status"], BaoyanStatus.PRE_RECOMMENDED.value)

        # PRE_RECOMMENDED -> FINAL_OFFER_LOCKED
        pipeline.step_golden_path(app_id, "研招网推免系统确认待录取通知，最终锁定Offer")
        self.assertEqual(pipeline.get_application(app_id)["status"], BaoyanStatus.FINAL_OFFER_LOCKED.value)

        # Attempt to step past final terminal state should fail
        with self.assertRaises(ValueError):
            pipeline.step_golden_path(app_id)

        # Verify full timeline length
        timeline = pipeline.get_timeline(app_id)
        self.assertEqual(len(timeline), 6)
        self.assertEqual(timeline[-1]["to_status"], BaoyanStatus.FINAL_OFFER_LOCKED.value)

    def test_06_invalid_and_branching_transitions(self):
        """Test illegal status jumps raise ValueError, while branching transitions succeed."""
        pipeline = BaoyanPipeline(self.profile_data)
        app_id = pipeline.add_target_application(
            school_name="北京大学",
            college="计算机学院",
            major="计算机系统结构",
            track="直博",
            initial_status=BaoyanStatus.COLLECTING_NOTICES
        )

        # Illegal jump: COLLECTING_NOTICES -> FINAL_OFFER_LOCKED
        with self.assertRaises(ValueError):
            pipeline.transition_application(app_id, BaoyanStatus.FINAL_OFFER_LOCKED)

        # Illegal jump: COLLECTING_NOTICES -> PRE_RECOMMENDED
        with self.assertRaises(ValueError):
            pipeline.transition_application(app_id, BaoyanStatus.PRE_RECOMMENDED)

        # Valid branch: COLLECTING_NOTICES -> CAMP_APPLIED
        pipeline.transition_application(app_id, BaoyanStatus.CAMP_APPLIED)
        self.assertEqual(pipeline.get_application(app_id)["status"], BaoyanStatus.CAMP_APPLIED.value)

        # Valid branch: CAMP_APPLIED -> CAMP_WAITLISTED (候补)
        pipeline.transition_application(app_id, BaoyanStatus.CAMP_WAITLISTED, "夏令营入营候补第 3 名")
        self.assertEqual(pipeline.get_application(app_id)["status"], BaoyanStatus.CAMP_WAITLISTED.value)

        # Valid branch: CAMP_WAITLISTED -> CAMP_ACCEPTED (候补补录入营)
        pipeline.transition_application(app_id, BaoyanStatus.CAMP_ACCEPTED, "前面同学放弃，成功补录入营")
        self.assertEqual(pipeline.get_application(app_id)["status"], BaoyanStatus.CAMP_ACCEPTED.value)

        # Valid branch: CAMP_ACCEPTED -> EXCELLENT_CAMP_ABANDONED (鸽了/放弃录取)
        pipeline.transition_application(app_id, BaoyanStatus.EXCELLENT_CAMP_ABANDONED, "选择清华，放弃北大拟录取")
        self.assertEqual(pipeline.get_application(app_id)["status"], BaoyanStatus.EXCELLENT_CAMP_ABANDONED.value)

    def test_07_funnel_summary_and_all_applications(self):
        """Verify pipeline funnel summary statistics and multiple application tracking."""
        pipeline = BaoyanPipeline(self.profile_data)
        apps = pipeline.get_all_applications()
        self.assertGreaterEqual(len(apps), 4)

        summary = pipeline.get_funnel_summary()
        self.assertEqual(summary["total_applications"], len(apps))
        self.assertIn("funnel_counts", summary)
        self.assertIn("active_applications", summary)
        self.assertGreaterEqual(summary["active_applications"], 1)

    # =========================================================================
    # 4. Summer Camp & Postgraduate Re-examination Checklist Generator
    # =========================================================================

    def test_08_summer_camp_checklist_generation(self):
        """Verify generation of Summer Camp checklist for direct PhD candidate."""
        checklist = generate_camp_checklist(self.profile_data, stage="夏令营", track="直博")

        self.assertEqual(checklist["stage"], "夏令营")
        self.assertEqual(checklist["track"], "直博")
        self.assertEqual(checklist["candidate_name"], "林书扬")
        self.assertGreaterEqual(checklist["readiness_percentage"], 90.0)

        categories = checklist["categories"]
        self.assertIn("mandatory_materials", categories)
        self.assertIn("academic_proofs", categories)
        self.assertIn("expert_recommendations", categories)
        self.assertIn("presentation_and_interview", categories)
        self.assertIn("administrative_and_logistics", categories)

        # Check mandatory materials
        mand_names = [it["name"] for it in categories["mandatory_materials"]]
        mand_str = " ".join(mand_names)
        self.assertIn("身份证", mand_str)
        self.assertIn("成绩单", mand_str)
        self.assertIn("排名", mand_str)
        self.assertIn("六级", mand_str)
        self.assertIn("简历", mand_str)
        self.assertIn("个人陈述", mand_str)

        # Check expert recommendations for 直博
        recs = categories["expert_recommendations"]
        self.assertEqual(len(recs), 2)
        for r in recs:
            self.assertEqual(r["importance"], "CRITICAL")
            self.assertIn("直博刚性必备", r["name"])

        # Check presentation items
        pres = categories["presentation_and_interview"]
        pres_str = " ".join([p["name"] for p in pres])
        self.assertIn("PPT", pres_str)
        self.assertIn("英文", pres_str)
        self.assertIn("推导", pres_str)

        # Check logistics
        logistics = categories["administrative_and_logistics"]
        log_str = " ".join([l["name"] for l in logistics])
        self.assertIn("网申系统", log_str)
        self.assertIn("套磁", log_str)

    def test_09_postgrad_reexam_and_different_stages(self):
        """Verify checklist adapts across stages (统考复试, 九推, 预推免) and tracks (专硕)."""
        # 统考复试
        fushi_checklist = generate_camp_checklist(self.profile_data, stage="统考复试", track="专硕")
        self.assertEqual(fushi_checklist["stage"], "统考复试")
        fushi_logistics = fushi_checklist["categories"]["administrative_and_logistics"]
        fushi_log_str = " ".join([l["name"] for l in fushi_logistics])
        self.assertIn("准考证", fushi_log_str)
        self.assertIn("政审", fushi_log_str)

        # 九推
        jiutui_checklist = generate_camp_checklist(self.profile_data, stage="九推", track="学硕")
        self.assertEqual(jiutui_checklist["stage"], "九推")
        jiutui_logistics = jiutui_checklist["categories"]["administrative_and_logistics"]
        jiutui_log_str = " ".join([l["name"] for l in jiutui_logistics])
        self.assertIn("全国推免服务系统", jiutui_log_str)

        # Invalid stage / track checks
        with self.assertRaises(ValueError):
            generate_camp_checklist(self.profile_data, stage="高考志愿填报")
        with self.assertRaises(ValueError):
            generate_camp_checklist(self.profile_data, track="本科生")


class TestAcademicSync(unittest.TestCase):
    """Tests for academic publication sync and camp presentation planning."""

    def test_bibtex_parser_conference_and_ccf(self):
        from core.academic_sync import BibTexPublicationParser
        bib = """
@inproceedings{li2025fast,
  title = {{Fast distributed consensus via adaptive speculation}},
  author = {Li, Ming and Zhang, Wei and Wang, Gang},
  booktitle = {Proceedings of the 2025 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year = {2025},
  doi = {10.1109/CVPR.2025.0001},
  presentation = {Oral}
}
@article{zhang2024scaling,
  title = {Scaling large language models efficiently},
  author = {Wei Zhang and Ming Li},
  journal = {ACM Transactions on Computer Systems (TOCS)},
  year = {2024},
  doi = {10.1145/3600000}
}
"""
        pubs = BibTexPublicationParser.parse_string(bib, candidate_name="Ming Li")
        self.assertEqual(len(pubs), 2)
        p1 = pubs[0]
        self.assertEqual(p1.cite_key, "li2025fast")
        self.assertEqual(p1.title, "Fast distributed consensus via adaptive speculation")
        self.assertEqual(p1.entry_type, "inproceedings")
        self.assertEqual(p1.year, 2025)
        self.assertEqual(p1.ccf_rank, "CCF-A")
        self.assertEqual(p1.presentation_type, "Oral")
        self.assertTrue(p1.is_first_or_corresponding)
        self.assertEqual(p1.doi, "10.1109/CVPR.2025.0001")

        p2 = pubs[1]
        self.assertEqual(p2.cite_key, "zhang2024scaling")
        self.assertEqual(p2.entry_type, "article")
        self.assertEqual(p2.year, 2024)
        self.assertFalse(p2.is_first_or_corresponding)

    def test_camp_presentation_planner(self):
        from core.academic_sync import AcademicPublication, CampPresentationPlanner, CampPresentationPlan
        pub = AcademicPublication(
            cite_key="li2025fast",
            entry_type="inproceedings",
            title="Adaptive Speculative Execution for Distributed Systems",
            authors=["Ming Li", "Wei Zhang"],
            venue="USENIX ATC",
            year=2025,
            ccf_rank="CCF-A",
        )
        plan = CampPresentationPlanner.plan(
            candidate_name="李明",
            target_lab_or_institution="清华大学计算机系网络技术研究所",
            target_direction="分布式系统与云原生底座",
            publications=[pub],
            key_projects=["高并发分布式KV引擎", "自研内核级旁路网关"],
        )
        self.assertIsInstance(plan, CampPresentationPlan)
        self.assertEqual(plan.candidate_name, "李明")
        self.assertEqual(plan.target_lab_or_institution, "清华大学计算机系网络技术研究所")
        self.assertEqual(len(plan.slides), 4)
        self.assertEqual(sum(s.allocated_seconds for s in plan.slides), 210)
        self.assertIn("学术画像", plan.slides[0].slide_title)
        self.assertIn("# 🎓 李明 - 夏令营/保研面试 4 页自述 PPT 规范方案", plan.markdown_outline)


class TestBaoyanPackageBuilder(unittest.TestCase):
    """Tests for Baoyan package manifest, personal statement, and outreach builders."""

    def test_validate_config_and_manifest(self):
        from core.baoyan_pipeline import BaoyanPackageBuilder, PackageManifest
        builder = BaoyanPackageBuilder()
        valid, errors = builder.validate_config({})
        self.assertFalse(valid)
        self.assertTrue(any("school.name" in e for e in errors))

        config = {
            "school": {
                "name": "清华大学", "english": "Tsinghua University",
                "primary_color": "#660874", "package_title": "夏令营申请材料",
                "application_label": "申请学院", "application_value": "计算机系",
            },
            "applicant": {
                "name": "李华", "undergraduate_school": "北航",
                "major": "软件工程", "date_label": "2026年6月",
                "gpa": "3.92/4.0", "rank": "1/120",
            },
            "sections": [
                {
                    "number": "01", "title": "个人材料",
                    "documents": [
                        {"label": "中英文简历", "group": "个人简历", "page_count": 2},
                        {"label": "个人陈述", "group": "个人陈述", "page_count": 2},
                    ],
                },
                {
                    "number": "02", "title": "学业证明",
                    "documents": [
                        {"label": "本科成绩单", "group": "学业成绩", "page_count": 1},
                        {"label": "专业排名证明", "group": "学业成绩", "page_count": 1},
                        {"label": "四六级成绩单", "group": "英语水平", "page_count": 1},
                    ],
                },
            ],
        }
        manifest = builder.build_manifest(config)
        self.assertIsInstance(manifest, PackageManifest)
        self.assertEqual(manifest.school.name, "清华大学")
        self.assertEqual(manifest.total_pages, 9)
        self.assertEqual(len(manifest.toc_entries), 4)

    def test_personal_statement_builder(self):
        from core.baoyan_pipeline import PersonalStatementBuilder
        builder = PersonalStatementBuilder()
        profile_data = {
            "name": "王五",
            "education": {"school": "浙江大学", "major": "计算机", "gpa": "3.88", "rank": "3/150"},
            "experience": [{"title": "大模型平台", "bullets": ["开发微调流水线，吞吐提升 40%"]}],
            "awards": ["国家奖学金"],
        }
        draft = builder.build_statement(
            profile_data=profile_data,
            target_school="上海交通大学",
            target_major="计算机科学与技术",
            research_interests=["高效机器学习"],
        )
        self.assertEqual(draft.applicant_name, "王五")
        self.assertEqual(draft.target_school, "上海交通大学")
        self.assertIn("浙江大学", draft.academic_background)
        self.assertGreater(draft.word_count, 150)

    def test_taocixin_outreach_builder(self):
        from core.baoyan_pipeline import TaocixinOutreachBuilder
        builder = TaocixinOutreachBuilder()
        letter = builder.build_email(
            applicant_name="赵六",
            applicant_school="华中科技大学",
            applicant_major="软件工程",
            professor_name="张",
            target_school="北京大学",
            target_lab="系统软件实验室",
            paper_title="Fast Distributed Graph Neural Network Training",
            applicant_strengths=["图计算优化", "C++ 高并发"],
            gpa_rank="前 2%",
        )
        self.assertIn("【保研自荐】", letter.email_subject)
        self.assertIn("华中科技大学赵六", letter.email_subject)
        self.assertIn("张老师", letter.greeting)
        self.assertEqual(letter.ledger_row["status"], "DRAFTED")


if __name__ == "__main__":
    unittest.main()


