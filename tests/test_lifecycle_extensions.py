import unittest
from datetime import datetime, timedelta
from core.interview_debrief import InterviewDebriefEngine, QuestionDiagnosis
from core.academic_exporter import AcademicExporter
from core.application_tracker import ApplicationTracker, ApplicationRecord, AppStatus

class TestLifecycleExtensions(unittest.TestCase):
    def setUp(self):
        self.debrief_engine = InterviewDebriefEngine()
        self.exporter = AcademicExporter()
        self.tracker = ApplicationTracker()
        self.sample_profile = {
            "candidate": {
                "name": "张三",
                "title": "大模型算法架构师",
                "email": "zhangsan@example.com",
                "phone": "138-0000-0000",
                "school": "清华大学",
                "degree": "计算机博士"
            },
            "competencies": {
                "frameworks": ["PyTorch", "Megatron-LM", "vLLM"],
                "languages": ["Python", "C++", "CUDA"]
            },
            "projects": [
                {
                    "name": "百亿大模型高效推理优化",
                    "role": "核心架构 Owner",
                    "bullets": ["基于 vLLM 改造连续批处理", "实现 TTFT 下降 45%"]
                }
            ],
            "publications": [
                {
                    "title": "Fast-Megatron: Scalable Transformer Training",
                    "venue": "NeurIPS 2024"
                }
            ]
        }

    # 1. Test Interview Debrief
    def test_interview_debrief_diagnosis(self):
        # Test metric drift without baseline
        q1 = "你的模型推理加速了40%，具体是怎么测出来的？"
        a1 = "主要是优化了KV缓存，吞吐量提升了40%。"
        item1 = self.debrief_engine.analyze_question(q1, a1)
        self.assertEqual(item1.diagnosis, QuestionDiagnosis.METRIC_DRIFT)

        # Test well defended with baseline
        a2 = "以开源 vLLM 默认参数为 Baseline，在 2048 上下文稳态压测下，吞吐量由 1200 提升至 1680。"
        item2 = self.debrief_engine.analyze_question(q1, a2)
        self.assertEqual(item2.diagnosis, QuestionDiagnosis.WELL_DEFENDED)

        # Test full session debrief
        debrief = self.debrief_engine.generate_session_debrief(
            company="字节跳动",
            role="大模型Infra",
            round_name="技术终面",
            qa_pairs=[{"question": q1, "answer": a1}]
        )
        self.assertEqual(len(debrief.action_items), 1)
        self.assertEqual(len(debrief.defense_updates), 1)

    # 2. Test Academic Exporter (LaTeX & Typst)
    def test_academic_exporter_latex(self):
        latex_src = self.exporter.generate_latex(self.sample_profile)
        self.assertIn(r"\documentclass", latex_src)
        self.assertIn("张三", latex_src)
        self.assertIn("清华大学", latex_src)
        self.assertIn("NeurIPS 2024", latex_src)

    def test_academic_exporter_typst(self):
        typst_src = self.exporter.generate_typst(self.sample_profile)
        self.assertIn("#set page", typst_src)
        self.assertIn("张三", typst_src)
        self.assertIn("百亿大模型高效推理优化", typst_src)

    # 3. Test Application Tracker
    def test_application_tracker_conflicts_and_board(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        rec1 = ApplicationRecord(
            id="APP-01",
            target_name="阿里巴巴",
            role_or_track="大模型算法",
            status=AppStatus.INTERVIEW,
            exam_or_interview_time=f"{today_str} 14:00",
            deadline=today_str
        )
        rec2 = ApplicationRecord(
            id="APP-02",
            target_name="北京大学",
            role_or_track="直博考核",
            status=AppStatus.INTERVIEW,
            exam_or_interview_time=f"{today_str} 15:00",
            deadline=today_str
        )
        self.tracker.add_record(rec1)
        self.tracker.add_record(rec2)

        conflicts = self.tracker.detect_schedule_conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertIn("阿里巴巴", conflicts[0]["targets"][0])

        board_md = self.tracker.generate_board_markdown()
        self.assertIn("阿里巴巴", board_md)
        self.assertIn("北京大学", board_md)

if __name__ == "__main__":
    unittest.main()
