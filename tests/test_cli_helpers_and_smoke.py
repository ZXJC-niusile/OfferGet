"""
Unit and Smoke Tests for CLI Helpers and Command Handlers.
Validates:
1. core.cli_helpers standard I/O abstractions (read_text, load_json, load_json_or_text, write_json, write_text).
2. Auto-creation of parent directories and exception handling (FileNotFoundError, IsADirectoryError, JSONDecodeError).
3. Pure stdout output isolation with emit_json, and stderr emission with emit_stderr.
4. format_cli_error schema and exit_cli_error routines.
5. CLI smoke tests: argument parsing, --help on core subcommands (decode, match, audit, selftest).
6. Pure JSON stdout on CLI subcommands when --json is provided.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.cli_helpers import (
    read_text,
    load_json,
    load_json_or_text,
    write_json,
    write_text,
    emit_json,
    emit_stderr,
    format_cli_error,
    exit_cli_error,
)


class TestCliHelpers(unittest.TestCase):
    """Unit tests for core.cli_helpers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_read_text_existing_file(self):
        f = self.base_path / "sample.txt"
        f.write_text("Hello OfferGet\nLine 2", encoding="utf-8")
        result = read_text(str(f))
        self.assertEqual(result, "Hello OfferGet\nLine 2")

    def test_read_text_raw_string(self):
        raw = "This is an inline job description\nwith multiple lines"
        result = read_text(raw)
        self.assertEqual(result, raw)

    def test_read_text_file_not_found(self):
        missing_path = str(self.base_path / "does_not_exist.txt")
        with self.assertRaises(FileNotFoundError):
            read_text(missing_path)

    def test_read_text_must_exist(self):
        with self.assertRaises(FileNotFoundError):
            read_text("some_raw_string", must_exist=True)

    def test_read_text_directory_error(self):
        with self.assertRaises(IsADirectoryError):
            read_text(str(self.base_path))

    def test_load_json_existing_file(self):
        f = self.base_path / "data.json"
        f.write_text(json.dumps({"role": "AI Engineer", "level": "Senior"}), encoding="utf-8")
        data = load_json(str(f))
        self.assertEqual(data["role"], "AI Engineer")
        self.assertEqual(data["level"], "Senior")

    def test_load_json_raw_string(self):
        raw_json = '{"project": "OfferGet", "stars": 100}'
        data = load_json(raw_json)
        self.assertEqual(data["project"], "OfferGet")
        self.assertEqual(data["stars"], 100)

    def test_load_json_file_not_found(self):
        missing_json = str(self.base_path / "missing.json")
        with self.assertRaises(FileNotFoundError):
            load_json(missing_json)

    def test_load_json_invalid_content(self):
        with self.assertRaises((json.JSONDecodeError, ValueError)):
            load_json("{bad_json_content: True")

    def test_load_json_or_text_with_json_file(self):
        f = self.base_path / "profile.json"
        f.write_text(json.dumps({"name": "Alex", "score": 95}), encoding="utf-8")
        parsed, raw = load_json_or_text(str(f))
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["name"], "Alex")
        self.assertIn("Alex", raw)

    def test_load_json_or_text_with_text_file(self):
        f = self.base_path / "notes.txt"
        f.write_text("Simple text bullet points", encoding="utf-8")
        parsed, raw = load_json_or_text(str(f))
        self.assertIsNone(parsed)
        self.assertEqual(raw, "Simple text bullet points")

    def test_load_json_or_text_with_raw_json_str(self):
        raw = '{"target": "Baoyan", "rank": 1}'
        parsed, text = load_json_or_text(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["target"], "Baoyan")
        self.assertEqual(text, raw)

    def test_load_json_or_text_with_raw_plain_text(self):
        raw = "负责大模型分布式训练工程优化"
        parsed, text = load_json_or_text(raw)
        self.assertIsNone(parsed)
        self.assertEqual(text, raw)

    def test_write_json_creates_parent_dirs(self):
        target = self.base_path / "nested" / "dir" / "out.json"
        data = {"status": "ok", "count": 42}
        written_path = write_json(data, str(target))

        self.assertTrue(target.exists())
        self.assertEqual(written_path, str(target))
        loaded = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(loaded, data)

    def test_write_text_creates_parent_dirs(self):
        target = self.base_path / "a" / "b" / "c" / "out.txt"
        content = "Deeply nested output text"
        written_path = write_text(content, str(target))

        self.assertTrue(target.exists())
        self.assertEqual(written_path, str(target))
        self.assertEqual(target.read_text(encoding="utf-8"), content)

    def test_emit_json_isolated(self):
        test_payload = {"key": "value", "numbers": [1, 2, 3]}
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            emit_json(test_payload)

        output_str = captured.getvalue()
        self.assertTrue(output_str.endswith("\n"))
        reloaded = json.loads(output_str)
        self.assertEqual(reloaded, test_payload)

    def test_emit_stderr_isolated(self):
        captured = io.StringIO()
        with patch("sys.stderr", captured):
            emit_stderr("[!] Test warning")

        output_str = captured.getvalue()
        self.assertTrue(output_str.endswith("\n"))
        self.assertIn("[!] Test warning", output_str)

    def test_format_cli_error(self):
        err = format_cli_error("NotFound", "Item not found in database", exit_code=2)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error_type"], "NotFound")
        self.assertEqual(err["message"], "Item not found in database")
        self.assertEqual(err["exit_code"], 2)

    def test_exit_cli_error_stderr(self):
        captured_err = io.StringIO()
        with patch("sys.stderr", captured_err), patch("sys.exit") as mock_exit:
            exit_cli_error("FileNotFound", "File missing.txt missing", exit_code=1, as_json=False)
            mock_exit.assert_called_once_with(1)
        self.assertIn("File missing.txt missing", captured_err.getvalue())

    def test_exit_cli_error_json(self):
        captured_out = io.StringIO()
        with patch("sys.stdout", captured_out), patch("sys.exit") as mock_exit:
            exit_cli_error("InvalidInput", "Bad argument", exit_code=3, as_json=True)
            mock_exit.assert_called_once_with(3)
        data = json.loads(captured_out.getvalue())
        self.assertEqual(data["error_type"], "InvalidInput")
        self.assertEqual(data["exit_code"], 3)


class TestCliSmokeAndSubcommands(unittest.TestCase):
    """Smoke tests for CLI entry point and subcommands."""

    def setUp(self):
        self.cli_path = PROJECT_ROOT / "cli.py"
        self.sample_jd = PROJECT_ROOT / "examples" / "sample_ai_jd.txt"
        self.sample_profile = PROJECT_ROOT / "examples" / "candidate_profile.json"

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(self.cli_path)] + list(args)
        return subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def test_cli_main_help(self):
        proc = self.run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("OfferGet", proc.stdout)
        self.assertIn("Available subcommands", proc.stdout)

    def test_cli_subcommands_help(self):
        cases = [
            (["jd", "decode", "--help"], ["jd_file", "--json"]),
            (["jd", "match", "--help"], ["--profile", "--json"]),
            (["ats", "audit", "--help"], ["input_file"]),
            (["gap", "roi", "--help"], ["jd_files"]),
            (["offer", "evaluate", "--help"], ["offer_file"]),
            (["baoyan", "audit", "--help"], ["entry"]),
            (["review", "--help"], ["--profile"]),
        ]
        for cmd_args, expected_snippets in cases:
            with self.subTest(cmd=cmd_args):
                proc = self.run_cli(*cmd_args)
                self.assertEqual(proc.returncode, 0, f"Failed on {cmd_args}: {proc.stderr}")
                for snippet in expected_snippets:
                    self.assertIn(snippet, proc.stdout)

    def test_cli_jd_decode_json_pure_stdout(self):
        """Ensure --json produces 100% pure JSON on stdout with no extra log lines."""
        proc = self.run_cli("jd", "decode", str(self.sample_jd), "--json")
        self.assertEqual(proc.returncode, 0)
        # Attempt direct JSON parsing from stdout
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            self.fail(f"Stdout was not pure JSON: {e}\nOutput was: {proc.stdout}")

        self.assertIn("layers", data)
        self.assertIn("detected_signals", data)
        self.assertEqual(len(data["layers"]), 5)

    def test_cli_jd_match_json_pure_stdout(self):
        """Ensure match --json produces valid JSON on stdout."""
        proc = self.run_cli(
            "jd", "match",
            str(self.sample_jd),
            "--profile", str(self.sample_profile),
            "--json"
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertIn("overall_match_score", data)
        self.assertIn("interview_prob", data)

    def test_cli_missing_file_stderr_and_exit_code(self):
        proc = self.run_cli("jd", "decode", "non_existent_file_path.txt")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Error: JD file not found", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_application_review_accept_and_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db = tmp_path / "applications.db"
            review = tmp_path / "review.json"
            profile_out = tmp_path / "accepted_profile.json"
            resume_dir = tmp_path / "resume"

            add = self.run_cli("application", "add", "APP-SMOKE", "--db", str(db), "--company", "测试公司", "--role", "后端工程师", "--json")
            self.assertEqual(add.returncode, 0, add.stderr)

            review_proc = self.run_cli(
                "review", "examples/sample_ai_jd.txt",
                "--profile", "examples/candidate_profile.json",
                "--proposal-db", str(db), "--application-id", "APP-SMOKE",
                "--output", str(review), "--json",
            )
            self.assertEqual(review_proc.returncode, 0, review_proc.stderr)
            proposal_id = json.loads(review.read_text(encoding="utf-8"))["material_proposal"]["proposal_id"]

            accepted = self.run_cli(
                "proposal", "accept", proposal_id, "--db", str(db),
                "--profile", "examples/candidate_profile.json",
                "--jd", "examples/sample_ai_jd.txt",
                "--output", str(profile_out), "--build-resume",
                "--resume-output-dir", str(resume_dir), "--json",
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertTrue(profile_out.exists())

    def test_resume_version_records_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "applications.db"
            profile_out = Path(tmp) / "profile.json"
            resume_dir = Path(tmp) / "resume"
            self.run_cli("application", "add", "APP-HASH", "--db", str(db), "--company", "验收公司", "--role", "工程师")
            review = Path(tmp) / "review.json"
            self.run_cli("review", "examples/sample_ai_jd.txt", "--profile", "examples/candidate_profile.json", "--proposal-db", str(db), "--application-id", "APP-HASH", "--output", str(review), "--json")
            proposal_id = json.loads(review.read_text(encoding="utf-8"))["material_proposal"]["proposal_id"]
            accepted = self.run_cli("proposal", "accept", proposal_id, "--db", str(db), "--profile", "examples/candidate_profile.json", "--jd", "examples/sample_ai_jd.txt", "--output", str(profile_out), "--build-resume", "--resume-output-dir", str(resume_dir), "--json")
            payload = json.loads(accepted.stdout)
            self.assertEqual(payload["accept_phase"], "completed")
            self.assertEqual(set(payload["artifact_status"].values()), {"present"})


if __name__ == "__main__":
    unittest.main()

