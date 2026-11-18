"""
Unit and Smoke Tests for CLI Helpers and Command Handlers.
Validates:
1. core.cli_helpers standard I/O abstractions (read_text, load_json, load_json_or_text, write_json, write_text).
2. Auto-creation of parent directories and exception handling (FileNotFoundError, IsADirectoryError, JSONDecodeError).
3. Pure stdout output isolation with emit_json, and stderr emission with emit_stderr.
4. format_cli_error schema and exit_cli_error routines.
5. CLI smoke tests: argument parsing, --help on retained subcommands (profile, resume, ats, fact, diff, anon, selftest, doctor).
6. Pure JSON stdout on CLI subcommands when --json is provided.
"""

from __future__ import annotations

import errno
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pytest

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

        long_text = "岗位要求：熟悉 Python，负责后端开发。" * 300
        raw_json = json.dumps({"description": long_text}, ensure_ascii=False)
        with patch("pathlib.Path.stat", side_effect=OSError(errno.ENAMETOOLONG, "long input")):
            self.assertEqual(read_text(long_text), long_text)
            self.assertEqual(load_json(raw_json), {"description": long_text})
            self.assertEqual(load_json_or_text(long_text), (None, long_text))
            self.assertEqual(load_json_or_text(raw_json)[0], {"description": long_text})
            with self.assertRaises(OSError):
                read_text(long_text, must_exist=True)
            for reader in (read_text, load_json, load_json_or_text):
                with self.assertRaises(OSError):
                    reader("x" * 300 + ".json")

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

    def test_read_text_with_slashes_in_natural_text(self):
        """Verifies that in-text slashes (e.g. C/C++, CI/CD, TCP/IP) are treated as natural text,
        not as missing file paths."""
        raw = "职位：后台开发\n熟悉 C/C++ 与 CI/CD 流程，精通 TCP/IP 与 A/B 测试"
        self.assertEqual(read_text(raw), raw)
        single_line = "熟悉 C/C++ 和 CI/CD 架构优化"
        self.assertEqual(read_text(single_line), single_line)

    def test_read_text_and_load_json_strict_path_errors(self):
        """Verifies that missing Path objects or missing .json files raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            read_text(Path("non_existent_file.txt"))
        with self.assertRaises(FileNotFoundError):
            read_text("missing_file.txt")
        with self.assertRaises(FileNotFoundError):
            load_json_or_text("missing_profile.json")

        # Read errors must escape unchanged for both string paths and Path inputs.
        source = self.base_path / "input.json"
        source.write_text('{"role": "Engineer"}', encoding="utf-8")
        for reader in (read_text, load_json, load_json_or_text):
            for value in (source, str(source)):
                for error in (PermissionError(errno.EACCES, "denied", str(source)),
                              OSError(errno.EIO, "read failed", str(source)),
                              FileNotFoundError(errno.ENOENT, "removed during read", str(source))):
                    with self.subTest(reader=reader.__name__, value=type(value).__name__, error=type(error).__name__):
                        with patch("pathlib.Path.read_text", side_effect=error), patch("builtins.open", side_effect=error):
                            with self.assertRaises(type(error)) as caught:
                                reader(value)
                            self.assertIs(caught.exception, error)
            with patch("pathlib.Path.stat", side_effect=PermissionError("stat denied")):
                with self.assertRaises(PermissionError):
                    reader(str(source))

    def test_load_json_or_text_raises_on_corrupted_json_file(self):
        """Verifies that an explicit .json file with invalid syntax raises ValueError,
        and does not silently degrade to raw text."""
        bad_json = self.base_path / "corrupted.json"
        bad_json.write_text("{invalid json: [1, 2", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_json_or_text(bad_json)

    def test_write_json_creates_parent_dirs(self):
        target = self.base_path / "nested" / "dir" / "out.json"
        data = {"status": "ok", "count": 42}
        written_path = write_json(data, str(target))

        self.assertTrue(target.exists())
        self.assertEqual(Path(written_path).resolve(), target.resolve())
        loaded = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(loaded, data)

    def test_write_text_creates_parent_dirs(self):
        target = self.base_path / "a" / "b" / "c" / "out.txt"
        content = "Deeply nested output text"
        written_path = write_text(content, str(target))

        self.assertTrue(target.exists())
        self.assertEqual(Path(written_path).resolve(), target.resolve())
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
        # Export integrations use this existing reviewed synthetic public fixture.
        self.public_profile = PROJECT_ROOT / "examples" / "candidate_profile_minimal.json"

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
        import cli
        cases = [
            (["profile", "parse", "--help"], ["input_file", "--json"]),
            (["profile", "refs", "--help"], ["--docs", "--query", "--json"]),
            (["resume", "build", "--help"], ["profile", "--theme", "--pages"]),
            (["ats", "audit", "--help"], ["input_file", "--jd", "--json"]),
            (["ats", "ledger", "--help"], ["profile", "--jd", "--json"]),
            (["ats", "filter", "--help"], ["profile", "--tag"]),
            (["fact", "verify", "--help"], ["target", "--profile", "--json"]),
            (["diff", "audit", "--help"], ["baseline_file", "tailored_file", "--json"]),
            (["anon", "mask", "--help"], ["input_file", "--level", "--json"]),
        ]
        for cmd_args, expected_snippets in cases:
            with self.subTest(cmd=cmd_args):
                with patch("sys.argv", ["offerget", *cmd_args]), patch("sys.stdout", io.StringIO()) as output:
                    with self.assertRaises(SystemExit) as stopped:
                        cli.main()
                self.assertEqual(stopped.exception.code, 0)
                for snippet in expected_snippets:
                    self.assertIn(snippet, output.getvalue())

    def test_cli_ats_audit_and_ledger_json_pure_stdout(self):
        """Ensure ats audit and ats ledger --json produce 100% pure JSON on stdout."""
        audited = self.run_cli("ats", "audit", str(self.sample_profile), "--jd", str(self.sample_jd), "--json")
        self.assertEqual(audited.returncode, 0, audited.stderr)
        audit_payload = json.loads(audited.stdout)
        self.assertTrue({"overall_score", "skill_ledger"}.issubset(audit_payload))

        ledger = self.run_cli("ats", "ledger", str(self.sample_profile), "--jd", str(self.sample_jd), "--json")
        self.assertEqual(ledger.returncode, 0, ledger.stderr)
        ledger_payload = json.loads(ledger.stdout)
        self.assertIsInstance(ledger_payload, dict)

    def test_cli_missing_file_stderr_and_exit_code(self):
        proc = self.run_cli("ats", "audit", "non_existent_file_path.txt")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Error:", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def assert_json_failure(self, args, error_type):
        proc = self.run_cli(*args, "--json")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stderr, "")
        payload = json.loads(proc.stdout)
        self.assertEqual(set(payload), {"status", "error_type", "message", "exit_code"})
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], error_type)
        self.assertEqual(payload["exit_code"], 1)
        self.assertTrue(payload["message"])

    def test_cli_missing_input_json_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "missing.json")
            cases = [
                ["profile", "parse", missing],
                ["ats", "audit", missing],
                ["ats", "ledger", missing, "--jd", str(self.sample_jd)],
                ["fact", "verify", "bullet", "--profile", missing],
                ["diff", "audit", missing, str(self.sample_profile)],
            ]
            for args in cases:
                with self.subTest(args=args):
                    self.assert_json_failure(args, "input_not_found")

    def test_cli_malformed_profile_json_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "profile.json"
            bad.write_text("{invalid json", encoding="utf-8")
            commands = [
                ["ats", "audit", str(bad)],
                ["ats", "ledger", str(bad), "--jd", str(self.sample_jd)],
                ["fact", "verify", "bullet", "--profile", str(bad)],
                ["diff", "audit", str(bad), str(self.sample_profile)],
            ]
            for command in commands:
                with self.subTest(command=command):
                    self.assert_json_failure(command, "invalid_json")
            proc = self.run_cli("ats", "audit", str(bad))
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(proc.stdout, "")
            self.assertIn("Error:", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_profile_parse_json_input_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            self.assert_json_failure(["profile", "parse", str(path)], "input_not_found")
            path.write_text("{invalid json", encoding="utf-8")
            output = Path(tmp) / "parsed.json"
            self.assert_json_failure(["profile", "parse", str(path), "--output", str(output)], "invalid_json")
            self.assertFalse(output.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "{invalid json")
            path.write_text("[]", encoding="utf-8")
            self.assert_json_failure(["diff", "audit", str(path), str(self.sample_profile)], "invalid_input")
            self.assert_json_failure(["profile", "refs", "--docs", str(tmp), "--query", "cache", "--limit", "0"], "invalid_input")

    def test_cli_expected_error_boundary(self):
        import cli

        for error, kind in ((FileNotFoundError("input vanished"), "input_not_found"),
                            (PermissionError("unreadable input"), "io_error"),
                            (ValueError("invalid value"), "invalid_input")):
            with self.subTest(error=kind), patch("sys.argv", ["offerget", "ats", "audit", "input", "--json"]):
                with patch.object(cli, "cmd_ats_audit", side_effect=error), patch("sys.stdout", io.StringIO()) as out:
                    with self.assertRaises(SystemExit) as stopped:
                        cli.main()
                    self.assertEqual(stopped.exception.code, 1)
                    self.assertEqual(json.loads(out.getvalue())["error_type"], kind)
        with patch("sys.argv", ["offerget", "ats", "audit", "input", "--json"]):
            with patch.object(cli, "cmd_ats_audit", side_effect=RuntimeError("unexpected defect")):
                with self.assertRaisesRegex(RuntimeError, "unexpected defect"):
                    cli.main()

    @pytest.mark.browser
    def test_resume_build_renders_updated_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            resume_dir = tmp_path / "resume"
            source = tmp_path / "source.json"
            source.write_bytes(self.public_profile.read_bytes())

            build1 = self.run_cli("resume", "build", str(source), "--theme", "modern-navy", "--output-dir", str(resume_dir))
            self.assertEqual(build1.returncode, 0, build1.stderr)
            pdfs = list(resume_dir.glob("resume_modern_navy*.pdf"))
            self.assertEqual(len(pdfs), 1)
            old_pdf = pdfs[0]
            self.assertGreater(old_pdf.stat().st_size, 0)
            old_hash = hashlib.sha256(old_pdf.read_bytes()).hexdigest()

            import fitz
            updated = json.loads(source.read_text(encoding="utf-8"))
            updated["projects"] = [{"name": "UpdatedResumeMarker", "bullets": ["使用 Python 开发新版报表工具，交付团队使用。"]}]
            source.write_text(json.dumps(updated, ensure_ascii=False), encoding="utf-8")

            build2 = self.run_cli("resume", "build", str(source), "--theme", "modern-navy", "--output-dir", str(resume_dir))
            self.assertEqual(build2.returncode, 0, build2.stderr)
            self.assertNotEqual(hashlib.sha256(old_pdf.read_bytes()).hexdigest(), old_hash)
            with fitz.open(old_pdf) as document:
                self.assertIn("UpdatedResumeMarker", "".join(page.get_text() for page in document))
            self.assertEqual(len(list(resume_dir.glob("resume_modern_navy*.pdf"))), 1)

    def test_runtime_contract_exports_and_annotations(self):
        """Verifies core exports, submodule attributes, and typing annotations have zero runtime contract breakages."""
        import typing
        from core import FORBIDDEN_BUZZWORDS, AI_BUZZWORDS_LEXICON
        self.assertIsInstance(FORBIDDEN_BUZZWORDS, list)
        self.assertIsInstance(AI_BUZZWORDS_LEXICON, list)

        import core
        self.assertTrue(hasattr(core, "fact_guard"))
        self.assertTrue(hasattr(core, "resume_builder"))
        self.assertTrue(hasattr(core, "ats_checker"))

        from core.profile_adapter import ProfileContext
        hints = typing.get_type_hints(ProfileContext.to_view_model)
        self.assertIn("photo_path", hints)

        import cli
        self.assertTrue(callable(cli.main))


if __name__ == "__main__":
    unittest.main()


