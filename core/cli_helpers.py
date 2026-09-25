"""
Standard CLI Helpers & I/O Abstraction for OfferGet.
Adopts best practices from applyr / RenderCV for clean I/O separation,
directory creation, and structured JSON output.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

# Common extensions that indicate path_or_str is expected to be a file
COMMON_FILE_EXTENSIONS = {
    ".txt", ".json", ".md", ".html", ".htm", ".yaml", ".yml",
    ".csv", ".tsv", ".pdf", ".py", ".sh", ".doc", ".docx", ".xml", ".log"
}


def read_text(path_or_str: str, must_exist: bool = False) -> str:
    """
    Read text content from a file path or return the raw string.

    - If path_or_str matches an existing file, its UTF-8 content is returned.
    - If path_or_str is a directory, IsADirectoryError is raised.
    - If must_exist is True and file does not exist, FileNotFoundError is raised.
    - If path_or_str looks like a file path (has known extension or path separators)
      and does not contain newlines, FileNotFoundError is raised when not found.
    - Otherwise, path_or_str itself is returned as raw text.
    """
    if not isinstance(path_or_str, str):
        raise TypeError(f"Expected str, got {type(path_or_str).__name__}")

    p = Path(path_or_str)
    try:
        if p.exists():
            if p.is_file():
                return p.read_text(encoding="utf-8")
            if p.is_dir():
                raise IsADirectoryError(f"Target path is a directory, not a file: {path_or_str}")
    except OSError as e:
        if isinstance(e, IsADirectoryError):
            raise
        # Path name too long or invalid path syntax on Windows -> treat as raw text
        return path_or_str

    if must_exist:
        raise FileNotFoundError(f"File not found: {path_or_str}")

    # Check if path_or_str resembles a file path
    has_newline = "\n" in path_or_str or "\r" in path_or_str
    looks_like_file = (
        p.suffix.lower() in COMMON_FILE_EXTENSIONS
        or "/" in path_or_str
        or "\\" in path_or_str
        or path_or_str.startswith((".", "~"))
    )
    if looks_like_file and not has_newline:
        raise FileNotFoundError(f"File not found: {path_or_str}")

    return path_or_str


def load_json(path_or_str: str) -> Dict[str, Any]:
    """
    Load and parse JSON from a file path or raw JSON string.

    Raises:
        FileNotFoundError: If path_or_str is a path that does not exist.
        json.JSONDecodeError / ValueError: If content cannot be parsed as valid JSON.
    """
    if not isinstance(path_or_str, str):
        raise TypeError(f"Expected str, got {type(path_or_str).__name__}")

    p = Path(path_or_str)
    try:
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except OSError:
        pass

    s = path_or_str.strip()
    if s.startswith(("{", "[")):
        return json.loads(s)

    # If it has path separators, .json extension, or is a single-line missing token
    has_newline = "\n" in path_or_str or "\r" in path_or_str
    if "/" in path_or_str or "\\" in path_or_str or p.suffix.lower() == ".json" or not has_newline:
        raise FileNotFoundError(f"JSON file not found: {path_or_str}")

    return json.loads(s)


def load_json_or_text(path_or_str: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Read input which may be a file or raw string, and attempt to parse as JSON.

    Returns:
        Tuple of (parsed_json_dict_or_none, raw_text_content).
        If JSON parsing succeeds and result is a dict (or list), parsed_json is returned.
        Otherwise, parsed_json is None and raw_text contains the UTF-8 text.
    """
    if not isinstance(path_or_str, str):
        raise TypeError(f"Expected str, got {type(path_or_str).__name__}")

    p = Path(path_or_str)
    is_file = False
    try:
        if p.exists() and p.is_file():
            text = p.read_text(encoding="utf-8")
            is_file = True
        else:
            text = path_or_str
    except OSError:
        text = path_or_str

    stripped = text.strip()
    parsed_json = None
    if (is_file and p.suffix.lower() == ".json") or stripped.startswith(("{", "[")):
        try:
            data = json.loads(stripped)
            if isinstance(data, (dict, list)):
                parsed_json = data
        except Exception:
            parsed_json = None

    return parsed_json, text


def write_json(data: Any, path: Union[str, Path]) -> str:
    """
    Write data as formatted JSON to path, automatically creating parent directories recursively.

    Returns:
        Normalized string path of the written file.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(p)


def write_text(content: str, path: Union[str, Path]) -> str:
    """
    Write text content to path, automatically creating parent directories recursively.

    Returns:
        Normalized string path of the written file.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return str(p)


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
    "write_json",
    "write_text",
    "emit_json",
    "emit_stderr",
    "format_cli_error",
    "exit_cli_error",
    "open_application_store",
]
