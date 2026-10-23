"""
Standard CLI Helpers & I/O Abstraction for OfferGet.
Provides clean I/O separation, directory creation, and structured JSON output.
"""

from __future__ import annotations

import errno
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from core.artifacts import require_file

# Common extensions that indicate path_or_str is expected to be a file
COMMON_FILE_EXTENSIONS = {
    ".txt", ".json", ".md", ".html", ".htm", ".yaml", ".yml",
    ".csv", ".tsv", ".pdf", ".py", ".sh", ".doc", ".docx", ".xml", ".log"
}



def _input_exists(value: Union[str, os.PathLike[str]], *, must_exist: bool = False) -> bool:
    """Probe paths without swallowing read failures or treating long prose as a path."""
    raw = str(value)
    path = Path(value)
    explicit = (not isinstance(value, str) or must_exist or (
        "\n" not in raw and "\r" not in raw and (
            path.suffix.lower() in COMMON_FILE_EXTENSIONS
            or raw.startswith((".", "~", "/", "\\"))
            or (len(raw) > 2 and raw[1] == ":" and raw[2] in ("\\", "/"))
        )
    ))
    try:
        path.stat()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        invalid_name = exc.errno in {errno.EINVAL, errno.ENAMETOOLONG} or getattr(exc, "winerror", None) in {123, 206}
        if invalid_name and not explicit:
            return False
        raise

def read_text(path_or_str: Union[str, Path], must_exist: bool = False) -> str:
    """
    Read text content from a file path or return the raw string.

    - If path_or_str is a Path, it is treated as a file path; FileNotFoundError if missing.
    - If path_or_str matches an existing file, its UTF-8 content is returned.
    - If path_or_str is a directory, IsADirectoryError is raised.
    - If must_exist is True and file does not exist, FileNotFoundError is raised.
    - If path_or_str has a known file extension or explicit path prefixes (./, ../, /, \\, C:\\),
      and does not contain newlines, FileNotFoundError is raised when not found.
    - Otherwise, path_or_str itself is returned as raw text (e.g. "熟悉 C/C++ 和 CI/CD").
    """
    if isinstance(path_or_str, Path):
        if not path_or_str.exists():
            raise FileNotFoundError(f"File not found: {path_or_str}")
        if path_or_str.is_dir():
            raise IsADirectoryError(f"Target path is a directory, not a file: {path_or_str}")
        return path_or_str.read_text(encoding="utf-8")

    if not isinstance(path_or_str, str):
        raise TypeError(f"Expected str or Path, got {type(path_or_str).__name__}")

    p = Path(path_or_str)
    if _input_exists(path_or_str, must_exist=must_exist):
        if p.is_dir():
            raise IsADirectoryError(f"Target path is a directory, not a file: {path_or_str}")
        return p.read_text(encoding="utf-8")

    if must_exist:
        raise FileNotFoundError(f"File not found: {path_or_str}")

    has_newline = "\n" in path_or_str or "\r" in path_or_str
    is_path_syntax = (
        path_or_str.startswith((".", "~", "/", "\\"))
        or (len(path_or_str) > 2 and path_or_str[1] == ":" and path_or_str[2] in ("\\", "/"))
    )
    looks_like_file = p.suffix.lower() in COMMON_FILE_EXTENSIONS or is_path_syntax

    if looks_like_file and not has_newline:
        raise FileNotFoundError(f"File not found: {path_or_str}")

    return path_or_str


def load_json(path_or_str: Union[str, Path, os.PathLike[str]]) -> Dict[str, Any]:
    """
    Load and parse JSON from a file path or raw JSON string.

    Raises:
        FileNotFoundError: If path_or_str is a path that does not exist.
        json.JSONDecodeError / ValueError: If content cannot be parsed as valid JSON.
    """
    if not isinstance(path_or_str, (str, Path, os.PathLike)):
        raise TypeError(f"Expected str or Path, got {type(path_or_str).__name__}")

    raw_str = str(path_or_str)
    p = Path(path_or_str)
    if _input_exists(path_or_str):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    s = raw_str.strip()
    if s.startswith(("{", "[")):
        return json.loads(s)

    # If it has path separators, .json extension, or is a single-line missing token
    has_newline = "\n" in raw_str or "\r" in raw_str
    if "/" in raw_str or "\\" in raw_str or p.suffix.lower() == ".json" or not has_newline:
        raise FileNotFoundError(f"JSON file not found: {path_or_str}")

    return json.loads(s)


def load_json_or_text(path_or_str: Union[str, Path, os.PathLike[str]]) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Read input which may be a file or raw string, and attempt to parse as JSON.

    Returns:
        Tuple of (parsed_json_dict_or_none, raw_text_content).
        If JSON parsing succeeds and result is a dict (or list), parsed_json is returned.
        Otherwise, parsed_json is None and raw_text contains the UTF-8 text.

    Raises:
        FileNotFoundError: If given an explicit Path that does not exist, or a missing .json file.
        ValueError / json.JSONDecodeError: If an explicit .json file contains invalid JSON.
    """
    if not isinstance(path_or_str, (str, Path, os.PathLike)):
        raise TypeError(f"Expected str or Path, got {type(path_or_str).__name__}")

    raw_str = str(path_or_str)
    p = Path(path_or_str)
    is_file = _input_exists(path_or_str)
    if is_file:
        if p.is_dir():
            raise IsADirectoryError(f"Target path is a directory, not a file: {path_or_str}")
        text = p.read_text(encoding="utf-8")
    else:
        is_path_syntax = (
            isinstance(path_or_str, os.PathLike)
            or raw_str.startswith((".", "~", "/", "\\"))
            or (len(raw_str) > 2 and raw_str[1] == ":" and raw_str[2] in ("\\", "/"))
        )
        has_newline = "\n" in raw_str or "\r" in raw_str
        if p.suffix.lower() == ".json":
            raise FileNotFoundError(f"JSON file not found: {path_or_str}")
        if is_path_syntax and not has_newline:
            raise FileNotFoundError(f"File not found: {path_or_str}")
        text = raw_str

    stripped = text.strip()
    parsed_json = None
    if is_file and p.suffix.lower() == ".json":
        try:
            data = json.loads(stripped)
            if isinstance(data, (dict, list)):
                return data, text
            raise ValueError(f"JSON file must contain object or array, got {type(data).__name__}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON syntax in {path_or_str}: {exc}") from exc
    elif stripped.startswith(("{", "[")):
        try:
            data = json.loads(stripped)
            if isinstance(data, (dict, list)):
                parsed_json = data
        except Exception:
            parsed_json = None

    return parsed_json, text


def write_json(data: Any, path: Union[str, Path]) -> str:
    """
    Write data as formatted JSON to path atomically, automatically creating parent directories recursively.

    Returns:
        Normalized string path of the written file.
    """
    from core.artifacts import write_json_atomic

    return write_json_atomic(data, path)


def write_text(content: str, path: Union[str, Path]) -> str:
    """
    Write text content to path atomically, automatically creating parent directories recursively.

    Returns:
        Normalized string path of the written file.
    """
    from core.artifacts import write_text_atomic

    return write_text_atomic(content, path)


def emit_json(data: Any) -> None:
    """
    Emit pure formatted JSON only to sys.stdout with a trailing newline.
    Flushes stdout to prevent buffering issues.
    """
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    sys.stdout.write(payload + "\n")
    sys.stdout.flush()


def emit_stderr(msg: str) -> None:
    """
    Emit message, log, or alert only to sys.stderr with a trailing newline.
    Flushes stderr to ensure prompt output delivery.
    """
    if not msg.endswith("\n"):
        msg += "\n"
    sys.stderr.write(msg)
    sys.stderr.flush()


def format_cli_error(error_type: str, message: str, exit_code: int = 1) -> Dict[str, Any]:
    """
    Return a standardized dictionary representation of a CLI error.
    """
    return {
        "status": "error",
        "error_type": error_type,
        "message": message,
        "exit_code": exit_code,
    }


def exit_cli_error(
    error_type: str,
    message: str,
    exit_code: int = 1,
    as_json: bool = False,
) -> None:
    """
    Terminate CLI with formatted error output.
    If as_json is True, emits formatted JSON error to sys.stdout.
    Otherwise, writes error message to sys.stderr.
    Exits with exit_code.
    """
    if as_json:
        emit_json(format_cli_error(error_type=error_type, message=message, exit_code=exit_code))
    else:
        emit_stderr(f"[-] Error: {message}")
    sys.exit(exit_code)


def fail_cli(args: Any, error_type: str, message: str, exit_code: int = 1) -> None:
    """Exit a command with the repository-wide JSON/text error contract."""
    exit_cli_error(error_type, message, exit_code=exit_code, as_json=bool(getattr(args, "json", False)))


def load_profile(path_or_str: Union[str, Path]) -> Dict[str, Any]:
    """
    Load candidate profile from a JSON file, Markdown (.md), plain text (.txt), or raw text string.
    Automatically parses non-JSON files or markdown text using core.resume_parser.ResumeTextParser.
    """
    if not isinstance(path_or_str, (str, Path)):
        raise TypeError(f"Expected str or Path, got {type(path_or_str).__name__}")

    p = Path(path_or_str)
    if p.exists() and p.is_file():
        if p.suffix.lower() == ".json":
            return load_json(str(p))
        from core.resume_parser import parse_resume_to_profile
        return parse_resume_to_profile(p)

    has_newline = "\n" in str(path_or_str) or "\r" in str(path_or_str)
    if not has_newline and (
        p.suffix.lower() in COMMON_FILE_EXTENSIONS
        or "/" in str(path_or_str)
        or "\\" in str(path_or_str)
    ):
        raise FileNotFoundError(f"Profile file not found: {path_or_str}")

    from core.resume_parser import parse_resume_to_profile
    return parse_resume_to_profile(str(path_or_str))


def open_application_store(args_or_path: Any = None):
    """Create the shared SQLite store used by application-related commands."""
    from core.application_tracker import ApplicationStore

    if isinstance(args_or_path, (str, Path)):
        db_path = str(args_or_path)
    else:
        db_path = getattr(args_or_path, "db", None) or "offerget_applications.db"
    return ApplicationStore(db_path)


__all__ = [
    "read_text",
    "load_json",
    "load_json_or_text",
    "load_profile",
    "write_json",
    "write_text",
    "emit_json",
    "emit_stderr",
    "format_cli_error",
    "exit_cli_error",
    "fail_cli",
    "open_application_store",
    "require_file",
]

