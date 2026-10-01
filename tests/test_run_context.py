"""
Unit tests for OfferGet Run Context, Trace Desensitization, and Deterministic Cache (tests/test_run_context.py)
"""

import unittest
from dataclasses import dataclass

from core.run_context import (
    DeterministicCache,
    RunContext,
    StageTrace,
    compute_fingerprint,
    sanitize_trace_payload,
)


@dataclass
class DummyProfile:
    name: str
    phone: str
    email: str
    skills: list


class TestRunContext(unittest.TestCase):
    """Test suite for core.run_context module."""

    def test_stage_trace_creation_and_to_dict(self):
        trace = StageTrace(
            stage_name="jd_decoding",
            elapsed_ms=45.678,
            cache_hit=False,
            error_code="",
            summary="Decoded 5 layers and 3 skills",
        )
        self.assertEqual(trace.stage_name, "jd_decoding")
        self.assertEqual(trace.elapsed_ms, 45.678)
        self.assertFalse(trace.cache_hit)
        self.assertEqual(trace.error_code, "")

        d = trace.to_dict()
        self.assertEqual(d["stage_name"], "jd_decoding")
        self.assertEqual(d["elapsed_ms"], 45.68)
        self.assertEqual(d["summary"], "Decoded 5 layers and 3 skills")

    def test_run_context_lifecycle(self):
        ctx = RunContext()
        self.assertEqual(len(ctx.run_id), 8)
        self.assertEqual(ctx.engine_version, "2.0.0")
        self.assertEqual(len(ctx.traces), 0)
        self.assertEqual(ctx.get_total_elapsed_ms(), 0.0)

        # Record stage 1
        t1 = ctx.record_stage("decoder", 12.34, cache_hit=False, summary="Decoded JD")
        self.assertEqual(t1.stage_name, "decoder")
        self.assertEqual(len(ctx.traces), 1)

        # Record stage 2
        t2 = ctx.record_stage("matcher", 20.0, cache_hit=True, summary="Cache hit match")
        self.assertEqual(len(ctx.traces), 2)
        self.assertEqual(ctx.get_total_elapsed_ms(), 32.34)

        d = ctx.to_dict()
        self.assertEqual(d["run_id"], ctx.run_id)
        self.assertEqual(d["engine_version"], "2.0.0")
        self.assertEqual(len(d["traces"]), 2)
        self.assertEqual(d["total_elapsed_ms"], 32.34)

    def test_compute_fingerprint_determinism(self):
        # Different dictionary key insertion orders
        dict_a = {"b": 2, "a": 1, "c": [3, 2, 1], "sub": {"y": "test", "x": True}}
        dict_b = {"a": 1, "sub": {"x": True, "y": "test"}, "c": [3, 2, 1], "b": 2}

        fp_a = compute_fingerprint(dict_a)
        fp_b = compute_fingerprint(dict_b)

        self.assertEqual(len(fp_a), 64)
        self.assertEqual(fp_a, fp_b)

        # Changing data changes fingerprint
        dict_c = {"b": 2, "a": 1, "c": [3, 2, 99], "sub": {"y": "test", "x": True}}
        fp_c = compute_fingerprint(dict_c)
        self.assertNotEqual(fp_a, fp_c)

    def test_compute_fingerprint_with_dataclasses_and_sets(self):
        obj1 = DummyProfile(name="Alice", phone="13800000000", email="a@b.com", skills=["Python", "C++"])
        obj2 = DummyProfile(name="Alice", phone="13800000000", email="a@b.com", skills=["Python", "C++"])
        self.assertEqual(compute_fingerprint(obj1), compute_fingerprint(obj2))

        # Sets ordering determinism
        set_data_1 = {"tags": {"nlp", "cv", "rl"}}
        set_data_2 = {"tags": {"rl", "nlp", "cv"}}
        self.assertEqual(compute_fingerprint(set_data_1), compute_fingerprint(set_data_2))

    def test_sanitize_trace_payload_dict_keys(self):
        raw_payload = {
            "candidate_name": "张无忌",
            "phone": "13812345678",
            "email": "wuji.zhang@mingjiao.com",
            "score": 95,
            "profile": {
                "name": "李四",
                "mobile": "13987654321",
                "contact_email": "lisi@tech.org",
            },
        }

        clean = sanitize_trace_payload(raw_payload)

        # Ensure no raw sensitive info remains
        self.assertNotIn("13812345678", str(clean))
        self.assertNotIn("13987654321", str(clean))
        self.assertNotIn("wuji.zhang@mingjiao.com", str(clean))
        self.assertNotIn("lisi@tech.org", str(clean))
        self.assertEqual(clean["candidate_name"], "张*忌")
        self.assertEqual(clean["profile"]["name"], "李*")
        self.assertEqual(clean["score"], 95)
        self.assertEqual(clean["phone"], "138****5678")
        self.assertEqual(clean["profile"]["mobile"], "139****4321")

        # Ensure original payload was not mutated
        self.assertEqual(raw_payload["phone"], "13812345678")

    def test_sanitize_trace_payload_free_text(self):
        text = "请联系候选人电话 13812345678 或发送邮件至 recruiter@deepseek.com 确认面试时间。"
        cleaned = sanitize_trace_payload(text)
        self.assertNotIn("13812345678", cleaned)
        self.assertNotIn("recruiter@deepseek.com", cleaned)
        self.assertIn("138****5678", cleaned)
        self.assertIn("r***r@deepseek.com", cleaned)

    def test_deterministic_cache_operations(self):
        cache = DeterministicCache()
        self.assertEqual(cache.size(), 0)

        stage = "matcher"
        fp = "abcdef1234567890"
        data = {"score": 88, "verdict": "STRONG_FIT"}

        # Miss
        self.assertFalse(cache.has(stage, fp))
        self.assertIsNone(cache.get(stage, fp))

        # Set & Hit
        cache.set(stage, fp, data)
        self.assertTrue(cache.has(stage, fp))
        self.assertEqual(cache.size(), 1)
        self.assertEqual(cache.get(stage, fp), data)
        self.assertTrue((stage, fp) in cache)

        # Delete
        self.assertTrue(cache.delete(stage, fp))
        self.assertFalse(cache.has(stage, fp))
        self.assertEqual(cache.size(), 0)

        # Clear
        cache.set(stage, "fp1", 1)
        cache.set(stage, "fp2", 2)
        self.assertEqual(cache.size(), 2)
        cache.clear()
        self.assertEqual(cache.size(), 0)


class TestArtifactsAndPaths(unittest.TestCase):
    """Test suite for atomic artifact writes, path helpers, and content fingerprints."""

    def test_ensure_parent_and_atomic_writes(self):
        import json
        import tempfile
        from pathlib import Path
        from core.artifacts import write_text_atomic, write_json_atomic

        with tempfile.TemporaryDirectory() as tmp_dir:
            target_txt = Path(tmp_dir) / "sub" / "dir" / "test.txt"
            written_path = write_text_atomic("hello world", target_txt)
            self.assertEqual(Path(written_path).resolve(), target_txt.resolve())
            self.assertEqual(target_txt.read_text(encoding="utf-8"), "hello world")

            target_json = Path(tmp_dir) / "sub" / "dir2" / "data.json"
            written_json = write_json_atomic({"k": "v", "num": 42}, target_json)
            self.assertEqual(Path(written_json).resolve(), target_json.resolve())
            loaded = json.loads(target_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["k"], "v")
            self.assertEqual(loaded["num"], 42)

    def test_require_file(self):
        import tempfile
        from pathlib import Path
        from core.artifacts import require_file

        with tempfile.TemporaryDirectory() as tmp_dir:
            valid_file = Path(tmp_dir) / "valid.txt"
            valid_file.write_text("ok", encoding="utf-8")
            self.assertEqual(require_file(valid_file), valid_file.resolve())

            missing_file = Path(tmp_dir) / "missing.txt"
            with self.assertRaises(FileNotFoundError):
                require_file(missing_file, label="Profile")

    def test_paths_helpers_and_fingerprints(self):
        from core.paths import (
            get_project_root,
            get_template_path,
            get_theme_dir,
            get_theme_path,
            get_example_path,
            get_output_dir,
        )
        from core.fingerprints import (
            content_fingerprint,
            cache_key,
            profile_fingerprint,
            jd_fingerprint,
        )

        root = get_project_root()
        self.assertTrue((root / "pyproject.toml").is_file() or (root / "cli.py").is_file())
        self.assertTrue(get_template_path().is_file())
        self.assertTrue(get_theme_dir().is_dir())
        self.assertTrue(get_theme_path("modern-navy").is_file())
        self.assertTrue(get_example_path("candidate_profile.json").is_file())
        self.assertTrue(get_output_dir("resumes").is_dir())

        # Fingerprints
        data = {"b": 2, "a": 1}
        self.assertEqual(content_fingerprint(data), content_fingerprint({"a": 1, "b": 2}))
        self.assertTrue(cache_key("test_stage", data).startswith("test_stage:"))

        prof = {"candidate": {"name": "张三"}, "skills": ["Python"]}
        self.assertEqual(len(profile_fingerprint(prof)), 16)

        jd_text = "岗位名称: 资深后端研发\n职责: 架构设计"
        self.assertEqual(len(jd_fingerprint(jd_text)), 16)


if __name__ == "__main__":
    unittest.main()

