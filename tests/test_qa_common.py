"""Tests for shared QA helpers in scripts/qa_common.py."""

from __future__ import annotations

import hashlib

from scripts.qa_common import (
    academic_docx_cases,
    build_source_manifest,
    expected_profile_text,
    fixtures,
    squash,
    synthetic_photo,
    text_content,
)


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


def test_shared_fixtures_and_text_helpers_are_available_from_qa_common():
    assert len(fixtures()) == 26
    assert any(case["name"] == "exam-publications" for case in academic_docx_cases())
    assert synthetic_photo().startswith("data:image/png;base64,")
    assert text_content("<html><body><p>Hello   QA</p></body></html>") == "Hello QA"
    anchors = expected_profile_text({"name": "Synthetic", "experience": [{"bullets": ["Fact one"]}]})
    assert "Synthetic" in anchors and "Factone" in anchors
