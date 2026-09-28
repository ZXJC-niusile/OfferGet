"""Unit tests for core.artifacts, core.paths, and core.fingerprints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from core.artifacts import (
    ArtifactManifest,
    ensure_parent,
    require_file,
    write_json_atomic,
    write_text_atomic,
)
from core.fingerprints import (
    cache_key,
    canonical_json_bytes,
    content_fingerprint,
    jd_fingerprint,
    profile_fingerprint,
)
from core.paths import (
    get_example_path,
    get_output_dir,
    get_project_root,
    get_template_path,
    get_theme_dir,
    get_theme_path,
)


class TestArtifactsAndPaths(unittest.TestCase):
    def test_ensure_parent_and_atomic_writes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_txt = Path(tmp_dir) / "sub" / "dir" / "test.txt"
            written_path = write_text_atomic("hello world", target_txt)
            self.assertEqual(Path(written_path), target_txt)
            self.assertEqual(target_txt.read_text(encoding="utf-8"), "hello world")

            target_json = Path(tmp_dir) / "sub" / "dir2" / "data.json"
            written_json = write_json_atomic({"k": "v", "num": 42}, target_json)
            self.assertEqual(Path(written_json), target_json)
            loaded = json.loads(target_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["k"], "v")
            self.assertEqual(loaded["num"], 42)

    def test_require_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            valid_file = Path(tmp_dir) / "valid.txt"
            valid_file.write_text("ok", encoding="utf-8")
            self.assertEqual(require_file(valid_file), valid_file.resolve())

            missing_file = Path(tmp_dir) / "missing.txt"
            with self.assertRaises(FileNotFoundError):
                require_file(missing_file, label="Profile")

    def test_artifact_manifest(self):
        manifest = ArtifactManifest(
            path="output/test.pdf",
            format="pdf",
            content_hash="abc12345",
            page_count=1,
            findings=[{"issue": "none"}],
        )
        d = manifest.to_dict()
        self.assertEqual(d["path"], "output/test.pdf")
        self.assertEqual(d["format"], "pdf")
        self.assertEqual(d["page_count"], 1)
        self.assertEqual(len(d["findings"]), 1)

    def test_paths_helpers(self):
        root = get_project_root()
        self.assertTrue((root / "pyproject.toml").is_file() or (root / "cli.py").is_file())

        tmpl = get_template_path()
        self.assertTrue(tmpl.is_file())
        self.assertTrue(tmpl.name.endswith(".html"))

        theme_dir = get_theme_dir()
        self.assertTrue(theme_dir.is_dir())

        theme_path = get_theme_path("modern-navy")
        self.assertTrue(theme_path.is_file())

        example_profile = get_example_path("candidate_profile.json")
        self.assertTrue(example_profile.is_file())

        out_dir = get_output_dir("resumes")
        self.assertTrue(out_dir.is_dir())

    def test_fingerprints_deterministic(self):
        data = {"b": 2, "a": 1}
        fp1 = content_fingerprint(data)
        fp2 = content_fingerprint({"a": 1, "b": 2})
        self.assertEqual(fp1, fp2)

        ck = cache_key("test_stage", data)
        self.assertTrue(ck.startswith("test_stage:"))

        prof = {"candidate": {"name": "张三"}, "skills": ["Python"]}
        prof_fp = profile_fingerprint(prof)
        self.assertEqual(len(prof_fp), 16)

        jd_text = "岗位名称: 资深后端研发\n职责: 架构设计"
        jd_fp = jd_fingerprint(jd_text)
        self.assertEqual(len(jd_fp), 16)


if __name__ == "__main__":
    unittest.main()
