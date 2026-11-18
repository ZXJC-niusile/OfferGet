"""OfferGet QA Common Utilities.

Shared helpers, fabricated fixtures, and portrait generators for layout QA suites
across HTML/PDF, ATS plain, DOCX, LaTeX, and Typst formats.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_THEME = "modern-navy"
STRUCTURAL_LAYOUTS = {"modern-navy": "label-gutter", "classic-tech": "date-rail"}


def squash(text: Any) -> str:
    """Normalize and strip whitespace, markdown bold formatting, and invisible characters for robust text assertions."""
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    return re.sub(r"\s+", "", normalized).replace("**", "").replace("\u200b", "")


def build_source_manifest(root: Path, sources: List[str]) -> Dict[str, Dict[str, str]]:
    """Generate SHA256 and Git blob SHA1 signatures for test-reproducibility manifests."""
    manifest = {}
    for source in sources:
        data = (root / source).read_bytes()
        manifest[source] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha1": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
        }
    return manifest


class BodyText(HTMLParser):
    """Extract text independent of line wrapping or incidental style whitespace."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True

    def handle_endtag(self, tag):
        if tag == "body":
            self.in_body = False

    def handle_data(self, data):
        if self.in_body:
            self.parts.append(data)


def text_content(html: str) -> str:
    """Extract normalized whitespace-collapsed visible body text from HTML."""
    parser = BodyText()
    parser.feed(html)
    return " ".join("".join(parser.parts).split())


def synthetic_portrait_png() -> bytes:
    """Byte-identical, code-drawn test portrait shared by photo-contract tests."""
    from PIL import Image, ImageDraw

    picture = Image.new("RGB", (120, 160), "#E6EDF2")
    draw = ImageDraw.Draw(picture)
    draw.ellipse((40, 22, 80, 70), fill="#D8A47F")
    draw.rectangle((52, 64, 68, 87), fill="#D8A47F")
    draw.rounded_rectangle((21, 83, 99, 164), radius=27, fill="#264C72")
    draw.ellipse((40, 20, 80, 36), fill="#29323B")
    draw.rectangle((3, 3, 116, 156), outline="#C25252", width=2)
    output = io.BytesIO()
    picture.save(output, format="PNG")
    return output.getvalue()


def synthetic_photo() -> str:
    """A synthetic head-and-shoulders illustration, never a person's photo."""
    return "data:image/png;base64," + base64.b64encode(synthetic_portrait_png()).decode("ascii")


def fixtures(theme: str = DEFAULT_THEME):
    """All names, organizations, contacts and claims here are fabricated QA data."""
    short = {
        "name": "林示例 Alex Lin", "intent": "平台工程师 / Platform Engineer",
        "phone": "+00 000 000 0000", "email": "alex.qa@example.invalid", "city": "示例城市 / Remote",
        "education": {"school": "示例理工大学 / Example Institute", "degree": "计算机硕士 / MSc",
                      "major": "计算机科学 / Computer Science", "time": "2018.09 - 2020.06",
                      "gpa": "3.8/4.0", "awards": "示例奖学金 / Test Scholarship"},
        "experience": [{"company": "示例平台团队 / Example Platform Team", "role": "工程师 / Engineer",
                        "time": "2020.07 - 2024.12", "bullets": [
                            "QA-EXP-01：维护服务运行手册并记录发布结果。 Maintained service runbooks.",
                            "QA-EXP-02：整理故障复盘，验证修复步骤。 Documented repeatable recovery checks."]}],
        "campus_experience": [{"name": "示例开源项目 / Example Project", "role": "维护者 / Maintainer",
                               "time": "2019.01 - 2020.06", "bullets": [
                                   "QA-PROJ-01：补充使用说明与测试用例。 Added documentation and regression tests."]}],
        "skills": {"语言 / Languages": "Python, SQL", "工具 / Tools": "Git, Linux"},
    }
    long = json.loads(json.dumps(short))
    long.update({
        "name": "Alexandria Catherine Montgomery-Wellington 示例",
        "intent": "Principal Distributed Systems Architect and Research Engineering Lead / 平台架构",
        "email": "alexandria.montgomery.wellington." + "research" * 9 + "@engineering.example.invalid",
        "city": "示例城市 / Remote across several international research teams",
    })
    long["education"].update({
        "school": "International Institute of Advanced Computing and Reliability Research / 示例大学",
        "degree": "Master of Science in Distributed Systems / 计算机硕士",
        "awards": "PostgraduateResearchAndEngineeringExcellenceScholarship" * 2,
    })
    long["experience"][0].update({
        "company": "InternationalInfrastructureCompatibilityAndReliabilityResearchLaboratory" * 2,
        "role": "Principal Distributed Systems Architect and Engineering Lead / 负责人",
    })
    long["campus_experience"][0].update({
        "name": "OpenInfrastructureCompatibilityAndReliabilityResearchInitiative" * 2,
        "role": "Research Coordinator and Project Maintainer / 维护者",
    })
    dense = json.loads(json.dumps(short))
    dense["experience"] = [{
        "company": f"示例研究团队 {i + 1} / Example Research Team {i + 1}",
        "role": "平台工程师 / Platform Engineer", "time": f"{2010+i}.01 - {2011+i}.12",
        "bullets": [f"QA-DENSE-{i+1}-{j+1}：维护服务文档，与团队核对发布步骤和运行结果。 "
                    "Maintained operational documentation, reviewed release procedures with the team, "
                    "and recorded reproducible validation results for the shared infrastructure."
                    for j in range(4)],
    } for i in range(4)]
    result = []
    for label, profile, mode, max_pages in [
        ("short", short, "raw", 1), ("long", long, "raw", 2),
        ("dense", dense, "solver", 4), ("compact", long, "compact", 2),
    ]:
        for photo in ("none", "reserved"):
            result.append({"name": f"{label}-{photo}", "profile": profile, "photo": photo,
                           "mode": mode, "max_pages": max_pages})
    result.append({"name": "long-embedded", "profile": long, "photo": "embedded",
                   "photo_data_uri": synthetic_photo(), "mode": "raw", "max_pages": 2})
    result.append({"name": "production-reserved", "profile": short, "photo": "reserved",
                   "mode": "builder", "max_pages": 1})
    professional = json.loads(json.dumps(short))
    professional["experience"] = [
        {"company": "示例云平台 / Example Cloud", "role": "后端工程师 / Backend Engineer",
         "time": "2022.07 - 2025.06", "bullets": [
             "维护订单服务的 Python 接口，补充输入校验与错误处理。 Maintained Python APIs for the order service and added request validation.",
             "为发布流程建立回归检查，记录验证步骤与回滚条件。 Added release regression checks with documented validation and rollback steps.",
             "与产品和支持团队复盘用户反馈，修复可重现的问题。 Worked with product and support teams to reproduce and resolve reported issues."]},
        {"company": "示例软件工作室 / Example Software", "role": "软件工程师 / Software Engineer",
         "time": "2020.07 - 2022.06", "bullets": [
             "开发内部数据查询工具，为运营同事提供统一的检索入口。 Built an internal data lookup tool for the operations team.",
             "整理 SQL 查询与数据字段说明，补充常见问题排查文档。 Documented SQL queries, data fields, and common troubleshooting steps.",
             "参与代码评审与单元测试维护，跟进缺陷直到验证完成。 Reviewed code, maintained unit tests, and verified defect fixes."]},
    ]
    professional["campus_experience"] = [
        {"name": "服务运行手册 / Service Runbooks", "role": "维护者 / Maintainer",
         "time": "2023.03 - 2024.12", "bullets": [
             "汇总值班流程与故障处理步骤，使用测试环境验证操作顺序。 Organized on-call procedures and verified recovery steps in a test environment.",
             "补充检索索引与更新记录，方便团队定位相关说明。 Added a search index and change log for shared operational documentation."]},
        {"name": "开源数据工具 / Open Data Tools", "role": "贡献者 / Contributor",
         "time": "2019.09 - 2020.06", "bullets": [
             "为 CSV 导入流程添加格式检查，并编写中英文使用示例。 Added CSV format checks and bilingual usage examples.",
             "整理社区报告的边界情况，补充对应回归测试。 Converted reported edge cases into repeatable regression tests."]},
    ]
    for photo in ("none", "reserved"):
        result.append({"name": f"professional-{photo}", "profile": professional,
                       "photo": photo, "mode": "builder", "max_pages": 2})
    skills_long = json.loads(json.dumps(short))
    skills_long["skills"] = {
        "分布式系统可靠性与故障排查 / Distributed Systems Reliability and Troubleshooting":
            "Python, SQL, Linux, reproducible validation and operational documentation",
        "CrossPlatformInfrastructureCompatibilityAndResearchEngineering" * 2:
            "LongUnbrokenTechnicalSkillValueForWrappingChecks" * 3,
    }
    for mode in ("raw", "builder"):
        for photo in ("none", "reserved"):
            result.append({"name": f"skills-long-{mode}-{photo}", "profile": skills_long,
                           "photo": photo, "mode": mode, "max_pages": 2,
                           "require_autofit": False})
    if theme == "academic-postgraduate":
        for long_exam in (False, True):
            academic = json.loads(json.dumps(short))
            academic["intent"] = "计算机科学硕士 / MSc Computer Science"
            academic["postgraduate_exam"] = {
                "target_school": "示例大学 / Example University",
                "target_major": "计算机科学与技术 / Computer Science",
                "direction": "可信软件 / Reliable Software",
                "scores": {"思想政治理论": "72", "英语（一）": "78", "数学（一）": "125", "计算机学科基础": "120"},
                "total_score": "395",
            }
            if long_exam:
                academic["postgraduate_exam"].update({
                    "target_school": "InternationalInstituteOfAdvancedComputingAndInterdisciplinaryResearch" * 2,
                    "direction": "分布式系统的形式化验证与可信软件研究 / Formal Verification of Distributed Systems",
                    "scores": {"思想政治理论 / Political Theory": "72", "英语（一） / Academic English": "78",
                               "AdvancedMathematicsAndStatisticalMethods" * 2: "125",
                               "计算机学科专业基础综合 / Computer Science Foundations": "120"},
                })
            for photo in ("none", "reserved"):
                label = "long" if long_exam else "normal"
                result.append({"name": f"exam-{label}-{photo}", "profile": academic,
                               "photo": photo, "mode": "builder", "max_pages": 2})
    existing_names = {case["name"] for case in result}
    portrait = synthetic_photo()
    for case in list(result):
        if case["photo"] != "none":
            continue
        name = case["name"].removesuffix("-none") + "-embedded"
        if name not in existing_names:
            result.append(dict(case, name=name, photo="embedded", photo_data_uri=portrait))
    for mode in ("raw", "builder"):
        result.append({"name": f"source-photo-{mode}-none", "profile": short,
                       "photo": "none", "source_photo": True, "photo_data_uri": portrait,
                       "mode": mode, "max_pages": 1})
    if theme in STRUCTURAL_LAYOUTS:
        complete = json.loads(json.dumps(professional))
        complete["postgraduate_exam"] = {
            "target_school": "示例大学 / Example University",
            "target_major": "计算机科学 / Computer Science",
            "direction": "可信软件 / Reliable Software",
            "scores": {"政治 / Politics": "72", "英语 / English": "78", "数学 / Mathematics": "125"},
            "total_score": "275",
        }
        complete["publications"] = [
            {"title": "QA-PUB-01: Reproducible Reliability Checks", "authors": "Synthetic A, Synthetic B",
             "venue": "Example Systems Workshop", "conference": "Synthetic Reliability Meeting", "year": "2024",
             "status": "Submitted, not accepted", "author_role": "Co-author",
             "highlight": "QA-PUB-HIGHLIGHT-01: Checked 17 recorded cases.",
             "summary": "Synthetic validation study.", "individual_contribution": "Prepared reproducible fixtures."},
            {"title": "QA-PUB-02: Ordered Verification Notes", "authors": "Synthetic B, Synthetic A",
             "venue": "Example Testing Workshop", "conference": "Synthetic Methods Meeting", "year": "2025",
             "status": "Submitted, not accepted", "author_role": "Co-author",
             "highlight": "QA-PUB-HIGHLIGHT-02: Checked 23 recorded cases.",
             "summary": "Synthetic replication study.", "individual_contribution": "Reviewed recorded outputs."},
        ]
        for photo in ("none", "embedded"):
            result.append({"name": f"all-fields-{photo}", "profile": complete, "photo": photo,
                           "photo_data_uri": portrait, "mode": "raw", "max_pages": 3})
    for case in result:
        case["theme"] = theme
    return result


def academic_docx_cases():
    """Shared synthetic bilingual/academic cases for DOCX, LaTeX, and Typst QA."""
    wanted = {"professional-none", "professional-reserved", "long-none", "dense-none"}
    result = [copy.deepcopy(case) for case in fixtures() if case["name"] in wanted]
    professional = next(case for case in result if case["name"] == "professional-none")
    academic = copy.deepcopy(professional)
    academic["name"] = "exam-publications"
    academic["profile"]["postgraduate_exam"] = {
        "target_school": "示例研究生院 / Example Graduate School", "target_major": "计算机 / Computing",
        "direction": "Systems & Reliability", "scores": {"政治 / Politics": 70, "英语 / English": 80,
                                                             "数学 / Mathematics": 130, "专业课 / Computing": 120},
        "total_score": 400,
    }
    academic["profile"]["publications"] = [{
        "title": "Reliability & Evidence <Review>", "authors": "Alex Lin & Sam Example",
        "venue": "Synthetic Systems Journal", "year": "2025",
    }]
    academic["profile"]["experience"][0]["bullets"].append("DOCX-RAW-FACT: **C++ & Python**; latency < 20 ms.")
    result.append(academic)
    embedded = copy.deepcopy(professional)
    embedded.update(name="professional-embedded", photo="embedded", photo_data_uri=synthetic_photo())
    result.append(embedded)
    return result


def expected_profile_text(profile: Dict[str, Any]) -> List[str]:
    """Source-side assertions independent of view-model and formatter implementations."""
    anchors = [profile[k] for k in ("name", "intent", "phone", "email", "city") if profile.get(k)]
    education = profile.get("education", {})
    anchors.extend(str(value) for value in education.values() if value)
    for collection in ("experience", "campus_experience", "publications"):
        for item in profile.get(collection, []):
            for key, value in item.items():
                anchors.extend(value if key == "bullets" else [str(value)])
    for key, value in profile.get("skills", {}).items():
        anchors.append(key)
        anchors.extend(value if isinstance(value, list) else [value])
    exam = profile.get("postgraduate_exam", {})
    for key, value in exam.items():
        if key == "scores":
            anchors.extend(f"{subject}: {score}" for subject, score in value.items())
        else:
            anchors.append(str(value))
    return [squash(anchor) for anchor in anchors if anchor]
