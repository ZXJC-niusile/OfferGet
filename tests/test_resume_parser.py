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
from services.profile_service import ProfileService
from services.match_service import MatchService
from services.jd_service import JDService


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


def test_profile_service_integration():
    service = ProfileService()
    profile = service.parse_resume_text(SAMPLE_MD_RESUME)
    assert profile["candidate"]["name"] == "李华"

    normalized = service.normalize(profile)
    assert normalized["candidate"]["name"] == "李华"


def test_markdown_resume_jd_match():
    """Verifies that an auto-parsed markdown resume can directly feed into JD matching."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        md_file = Path(tmp_dir) / "resume.md"
        md_file.write_text(SAMPLE_MD_RESUME, encoding="utf-8")

        profile_data = load_profile(str(md_file))
        sample_jd_path = Path(__file__).resolve().parent.parent / "examples" / "sample_ai_jd.txt"
        if sample_jd_path.exists():
            jd_text = sample_jd_path.read_text(encoding="utf-8")
            decoded = JDService().decode_jd(jd_text)
            match_result = MatchService().match(decoded, profile_data)
            assert match_result is not None
            assert "overall_match_score" in match_result
            assert match_result["candidate_name"] == "李华"


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
