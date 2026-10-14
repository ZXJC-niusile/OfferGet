"""Tests for shared QA helpers in scripts/qa_common.py."""

from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.qa_common import build_source_manifest, squash


def test_squash_handles_whitespace_and_empty():
    assert squash(None) == ""
    assert squash("") == ""
    assert squash("  hello \n \t world  ") == "helloworld"


def test_squash_removes_markdown_bold_and_zero_width_spaces():
    assert squash("**bold** fact") == "boldfact"
    assert squash("zero\u200bwidth\u200bspace") == "zerowidthspace"
    assert squash("**C++ & Python**\u200b; latency < 20 ms.") == "C++&Python;latency<20ms."


def test_squash_normalizes_unicode_nfkc():
    # Fullwidth letters and digits normalized to standard ascii
    assert squash("ＡＢＣ １２３") == "ABC123"


def test_build_source_manifest_computes_sha256_and_git_blob_sha1(tmp_path):
    f1 = tmp_path / "sample.py"
    content = b"print('hello world')\n"
    f1.write_bytes(content)

    manifest = build_source_manifest(tmp_path, ["sample.py"])
    assert "sample.py" in manifest

    expected_sha256 = hashlib.sha256(content).hexdigest()
    expected_blob_sha1 = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()

    assert manifest["sample.py"]["sha256"] == expected_sha256
    assert manifest["sample.py"]["git_blob_sha1"] == expected_blob_sha1
