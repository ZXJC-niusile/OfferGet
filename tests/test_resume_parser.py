"""
Unit and Integration Tests for ResumeTextParser & Profile Ingestion
===================================================================
Tests markdown/plain-text resume parsing into canonical OfferGet Profile schemas,
verifying zero-loss extraction of candidates, education, skills, experiences, and projects.
"""

import json
import tempfile
from pathlib import Path

from core.resume_parser import ResumeTextParser, parse_resume_to_profile
from core.cli_helpers import load_profile
from core.profile_adapter import build_profile_context, normalize_candidate_profile


SAMPLE_MD_RESUME = """# 李华
139-1234-5678 | lihua.dev@pku.edu.cn | 杭州 | GitHub: https://github.com/lihua-dev | 5年研发经验

## 求职意向
资深后端高并发架构师

## 个人总结
5 年高并发分布式系统与云原生架构经验，精通 Go 与 Java 核心源码，主导过亿级日活交易底座重构，对分布式事务与缓存一致性有深刻理解。

## 教育背景
北京大学 · 软件工程 · 硕士 | 2019.09 - 2022.06
北京邮电大学 · 计算机科学 · 本科 | 2015.09 - 2019.06

## 专业技能
- 编程语言: Go, Java, Python, C++, SQL
- 中间件与系统: Kafka, RocketMQ, Redis, MySQL, Docker, Kubernetes, Linux
- 核心领域: 分布式事务, 缓存设计, RPC 框架, 微服务治理, DDD 领域建模

## 工作经历
### 蚂蚁集团 · 资深后端工程师 (2022.07 - 至今)
- 主导支付清算引擎重构，采用无锁环形队列与分库分表，单机 TPS 从 1.2w 提升至 3.8w。
- 解决极端并发下的双写缓存穿透问题，线上故障率下降 65%。

### 字节跳动 · 后端开发工程师 (2020.06 - 2022.06)
- 负责电商购物车与促销结算链路研发，P99 延迟降低 25ms。

## 项目经历
### 基于 Raft 的轻量级分布式 KV 存储引擎
- **角色**：项目独立设计与开发者 | 2021.03 - 2021.11
- 从零实现 Raft 选主、日志复制与快照压缩机制，通过 Jepsen 故障注入测试。

## 荣誉奖项
- 全国研究生数学建模竞赛一等奖 (2020)
- 优秀毕业生 (2022)
"""


def test_resume_parser_chinese_markdown():
    parser = ResumeTextParser(SAMPLE_MD_RESUME)
    profile = parser.parse()

    assert profile["profile_version"] == "2.0.0"
    cand = profile["candidate"]
    assert cand["name"] == "李华"
    assert cand["title_zh"] == "资深后端高并发架构师"
    assert cand["email"] == "lihua.dev@pku.edu.cn"
    assert cand["phone"] == "139-1234-5678"
    assert cand["location"] == "杭州"
    assert cand["github"] == "https://github.com/lihua-dev"
    assert cand["years_of_experience"] == 5.0
    assert "北京大学" in cand["institution"]
    assert "硕士" in cand["degree"]

    # Education
    assert len(profile["education"]) == 2
    assert profile["education"][0]["school"] == "北京大学"
    assert profile["education"][0]["major"] == "软件工程"
    assert profile["education"][0]["degree"] == "硕士"

    # Competencies
    comp = profile["competencies"]
    assert "programming" in comp
    assert "Go" in comp["programming"]
    assert "Java" in comp["programming"]
    assert "Redis" in profile["skills"]

    # Experience
    assert len(profile["experience"]) == 2
    assert "蚂蚁集团" in profile["experience"][0]["company"]
    assert len(profile["experience"][0]["bullets"]) == 2

    # Projects
    assert len(profile["projects"]) == 1
    assert "Raft" in profile["projects"][0]["name"]
    assert profile["projects"][0]["time"] == "2021.03 - 2021.11"

    # Honors
    assert len(profile["honors"]) == 2


def test_parse_resume_to_profile_string():
    profile = parse_resume_to_profile(SAMPLE_MD_RESUME)
    assert profile["candidate"]["name"] == "李华"


def test_load_profile_from_file():
    with tempfile.TemporaryDirectory() as tmp_dir:
        md_file = Path(tmp_dir) / "resume.md"
        md_file.write_text(SAMPLE_MD_RESUME, encoding="utf-8")

        profile = load_profile(str(md_file))
        assert profile["candidate"]["name"] == "李华"
        assert len(profile["experience"]) == 2

        # Verify normalization into ProfileContext
        context = build_profile_context(profile)
        assert context is not None
        assert len(context.skills) > 0


def test_parse_normalize_integration():
    profile = parse_resume_to_profile(SAMPLE_MD_RESUME)
    assert profile["candidate"]["name"] == "李华"

    normalized = normalize_candidate_profile(profile)
    assert normalized["candidate"]["name"] == "李华"


def test_parse_report_keeps_unknown_sections_out_of_experience_and_flags_missing_fields():
    profile = ResumeTextParser("# Synthetic\n## 工作经历\n### Example · 开发工程师\n- 开发接口服务并交付。\n## 资格证书\n- 某证书原文\n## 项目经历\n### 报表项目\n- 使用 Python 开发工具。\n").parse()
    report = profile["_parse_report"]
    assert report["status"] == "needs_review"
    assert report["recognized_counts"]["experience"] == 1
    assert any("某证书原文" in item["text"] for item in report["unclassified_lines"])
    assert "某证书原文" not in str(profile["experience"])
    assert {w["code"] for w in report["warnings"]} >= {"missing_contact", "missing_date", "unclassified_content"}


def test_cli_profile_parse():
    from presentation.commands.profile_cmd import cmd_profile_parse
    import argparse

    with tempfile.TemporaryDirectory() as tmp_dir:
        md_file = Path(tmp_dir) / "test_resume.md"
        md_file.write_text(SAMPLE_MD_RESUME, encoding="utf-8")
        out_json = Path(tmp_dir) / "parsed.json"

        args = argparse.Namespace(
            input_file=str(md_file),
            output=str(out_json),
            json=False,
        )
        cmd_profile_parse(args)

        assert out_json.exists()
        saved = json.loads(out_json.read_text(encoding="utf-8"))
        assert saved["candidate"]["name"] == "李华"
        args.input_file = str(out_json)
        args.confirm_parsed = True
        cmd_profile_parse(args)
        reviewed = json.loads(out_json.read_text(encoding="utf-8"))
        assert reviewed["_parse_report"]["status"] == "reviewed"
        assert reviewed["_parse_report"]["warnings"] == saved["_parse_report"]["warnings"]


# ---------------------------------------------------------------------------
# Robustness regression tests: encoding, binary interception, sub-headings
# ---------------------------------------------------------------------------

import pytest


def test_parse_gbk_encoded_txt_resume():
    """Legacy Notepad/WPS GBK exports must not crash with UnicodeDecodeError."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        txt_file = Path(tmp_dir) / "resume.txt"
        txt_file.write_bytes(
            "王五\n13900000000\n## 教育背景\n清华大学 · 计算机 · 本科 | 2020.09 - 2024.06".encode("gbk")
        )
        profile = parse_resume_to_profile(txt_file)
        assert profile["candidate"]["name"] == "王五"
        assert profile["education"][0]["school"] == "清华大学"


def test_parse_utf8_bom_resume():
    """A leading BOM must be stripped so it cannot pollute name matching."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        txt_file = Path(tmp_dir) / "resume.txt"
        txt_file.write_bytes("李四\nlisi@example.com".encode("utf-8-sig"))
        profile = parse_resume_to_profile(txt_file)
        assert profile["candidate"]["name"] == "李四"


def test_parse_rejects_binary_resume_files():
    """Unsupported binary inputs and corrupted DOCX/PDF files must fail with clear ValueErrors."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        doc_file = Path(tmp_dir) / "legacy.doc"
        doc_file.write_bytes(b"\xd0\xcf\x11\xe0 fake")
        with pytest.raises(ValueError, match="binary resume format"):
            parse_resume_to_profile(doc_file)

        pdf_file = Path(tmp_dir) / "resume.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        with pytest.raises(ValueError):
            parse_resume_to_profile(pdf_file)

        docx_file = Path(tmp_dir) / "resume.docx"
        docx_file.write_bytes(b"PK fake")
        with pytest.raises(ValueError, match="DOCX"):
            ResumeTextParser.from_file(docx_file)


def test_parse_docx_resume_with_headings():
    """Zero-dependency DOCX parser must restore Heading styles into Markdown and parse sections."""
    import zipfile

    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>张敏</w:t></w:r></w:p>
    <w:p><w:r><w:t>138-0000-1111 | zhangmin@example.com | 北京</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>教育背景</w:t></w:r></w:p>
    <w:p><w:r><w:t>复旦大学 · 软件工程 · 硕士 | 2021.09 - 2024.06</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>专业技能</w:t></w:r></w:p>
    <w:p><w:r><w:t>Python, Go, Kubernetes, Redis</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>工作经历</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr><w:r><w:t>星河科技 · 后端工程师 (2024.07 - 至今)</w:t></w:r></w:p>
    <w:p><w:r><w:t>- 主导网关限流重构，P99 延迟降低 35%。</w:t></w:r></w:p>
  </w:body>
</w:document>"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docx_path = Path(tmp_dir) / "candidate.docx"
        with zipfile.ZipFile(docx_path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)

        profile = parse_resume_to_profile(docx_path)
        assert profile["candidate"]["name"] == "张敏"
        assert profile["candidate"]["email"] == "zhangmin@example.com"
        assert profile["education"][0]["school"] == "复旦大学"
        assert "Python" in profile["skills"]
        assert "星河科技" in profile["experience"][0]["company"]
        assert len(profile["experience"][0]["bullets"]) == 1


def test_parse_html_resume():
    """HTML resume imports must strip scripts and preserve heading hierarchy."""
    html_doc = """<!doctype html><html><head><style>body{color:red}</style><script>alert(1)</script></head>
    <body>
      <h1>陈雷</h1>
      <p>chenlei@example.com | 上海</p>
      <h2>教育背景</h2>
      <p>浙江大学 · 计算机 · 本科 | 2018.09 - 2022.06</p>
      <h2>专业技能</h2>
      <ul><li>Rust, C++ &amp; Linux</li></ul>
    </body></html>"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        html_path = Path(tmp_dir) / "resume.html"
        html_path.write_text(html_doc, encoding="utf-8")

        profile = parse_resume_to_profile(html_path)
        assert profile["candidate"]["name"] == "陈雷"
        assert profile["candidate"]["email"] == "chenlei@example.com"
        assert profile["education"][0]["school"] == "浙江大学"
        assert "Rust" in profile["skills"]


def test_reference_knowledge_index_and_cli_refs(capsys):
    """ReferenceKnowledgeIndex and `profile refs` must tag all hits reference-only."""
    import cli
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        notes_dir = Path(tmp_dir) / "notes"
        notes_dir.mkdir()
        (notes_dir / "gateway_postmortem.md").write_text(
            "# 网关限流重构复盘\n## 压测数据\n采用令牌桶与本地缓存后，集群 QPS 从 12000 提升到 38000，P99 降至 18ms。\n",
            encoding="utf-8",
        )
        (notes_dir / "other.txt").write_text("日常周报：完成需求评审与代码走查。", encoding="utf-8")

        orig_argv = sys.argv
        try:
            sys.argv = ["offerget", "profile", "refs", "--docs", str(notes_dir), "--query", "网关 QPS 38000", "--json"]
            cli.main()
        finally:
            sys.argv = orig_argv

        out = json.loads(capsys.readouterr().out)
        assert out["visibility"] == "reference-only"
        assert len(out["hits"]) >= 1
        assert out["hits"][0]["visibility"] == "reference-only"
        assert "38000" in out["hits"][0]["content"]


def test_parse_preserves_subheading_entries():
    """### sub-headings inside sections carry entry data and must not be dropped."""
    md = (
        "# 赵六\n"
        "## 教育背景\n"
        "### 2020.09 - 2024.06 | 清华大学 | 计算机系 (学士)\n"
        "## 荣誉奖项\n"
        "### 2021 国家奖学金\n"
    )
    profile = ResumeTextParser(md).parse()
    assert len(profile["education"]) == 1
    assert profile["education"][0]["school"] == "清华大学"
    assert profile["education"][0]["degree"] == "学士"
    assert profile["honors"] == ["国家奖学金"]
