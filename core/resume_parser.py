"""
Resume Text & Markdown Ingestion Parser (core/resume_parser.py)
==============================================================
Deterministic, rule-based parser that converts Markdown or plain-text resumes
into canonical OfferGet Profile schemas (compatible with CandidateProfile,
ProfileContext, ResumeBuilder, and ATSAuditor) without requiring external LLMs.
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Binary document formats that cannot be parsed directly as resume text.
BINARY_RESUME_SUFFIXES = {
    ".doc", ".ppt", ".pptx", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".rar", ".7z",
}

_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _decode_text_bytes(data: bytes) -> str:
    """Decode bytes with UTF-8 BOM stripping and GB18030 fallback."""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_html_markdown(raw_html: str) -> str:
    """Extract readable text and Markdown heading structure from HTML."""
    cleaned = re.sub(r"<(script|style|noscript)\b[\s\S]*?</\1>", " ", raw_html, flags=re.IGNORECASE)
    for level in range(1, 7):
        pattern = re.compile(rf"<h{level}\b[^>]*>([\s\S]*?)</h{level}>", re.IGNORECASE)
        cleaned = pattern.sub(
            lambda m, lvl=level: f"\n\n{'#' * lvl} {re.sub(r'<[^>]+>', ' ', m.group(1)).strip()}\n\n",
            cleaned,
        )
    cleaned = re.sub(r"<(?:br|p|div|li|tr|section|article|blockquote)\b[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = _html.unescape(cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_docx_markdown(p: Path) -> str:
    """Zero-dependency DOCX parser extracting word/document.xml into Markdown-friendly text."""
    try:
        with zipfile.ZipFile(p, "r") as zf:
            if "word/document.xml" not in zf.namelist():
                raise ValueError(f"Invalid DOCX resume (missing word/document.xml): {p.name}")
            xml_bytes = zf.read("word/document.xml")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid or corrupted DOCX resume '{p.name}': {exc}") from exc

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"Corrupted XML inside DOCX resume '{p.name}': {exc}") from exc

    lines: List[str] = []
    w_tag = lambda local: f"{{{_WORD_NS}}}{local}"
    for para in root.iter(w_tag("p")):
        heading_level = 0
        p_pr = para.find(w_tag("pPr"))
        if p_pr is not None:
            p_style = p_pr.find(w_tag("pStyle"))
            if p_style is not None:
                val = p_style.attrib.get(w_tag("val")) or p_style.attrib.get("val", "")
                m = re.match(r"^(?:Heading|Title)\s*(\d)?", val, re.IGNORECASE)
                if m:
                    heading_level = min(6, max(1, int(m.group(1) or 1)))

        runs: List[str] = []
        for elem in para.iter():
            if elem.tag == w_tag("t") and elem.text:
                runs.append(elem.text)
            elif elem.tag == w_tag("tab"):
                runs.append("\t")
            elif elem.tag in (w_tag("br"), w_tag("cr")):
                runs.append("\n")

        line = "".join(runs).strip()
        if line:
            lines.append(f"{'#' * heading_level} {line}" if heading_level > 0 else line)

    return "\n\n".join(lines).strip()


def _extract_pdf_text(p: Path) -> str:
    """Extract text from PDF using pypdf or PyMuPDF when available."""
    errors: List[str] = []
    has_backend = False
    try:
        from pypdf import PdfReader
        has_backend = True
        reader = PdfReader(str(p))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n\n".join(pg for pg in pages if pg).strip()
        if text:
            return text
        errors.append("pypdf extracted no selectable text")
    except ImportError:
        pass
    except Exception as exc:
        errors.append(str(exc))

    try:
        import fitz
        has_backend = True
        with fitz.open(str(p)) as doc:
            pages = [page.get_text("text").strip() for page in doc]
        text = "\n\n".join(pg for pg in pages if pg).strip()
        if text:
            return text
        errors.append("PyMuPDF extracted no selectable text")
    except ImportError:
        pass
    except Exception as exc:
        errors.append(str(exc))

    if not has_backend:
        raise ValueError(
            f"Unsupported binary resume format '.pdf': {p.name}. "
            "Install pypdf/PyMuPDF or convert PDF to Markdown/DOCX/TXT first."
        )
    detail = "; ".join(errors) or "empty PDF text"
    raise ValueError(
        f"Failed to extract text from PDF resume '{p.name}' ({detail}). "
        "请确认 PDF 包含可选中文本，或先转换为 Markdown / DOCX / TXT 后重试。"
    )


def _read_resume_file(p: Path) -> str:
    """Read a resume file (.md/.txt/.docx/.html/.pdf/.json) into text."""
    suffix = p.suffix.lower()
    if suffix in BINARY_RESUME_SUFFIXES:
        raise ValueError(
            f"Unsupported binary resume format '{p.suffix}': {p.name}. "
            "ResumeTextParser ingests Markdown/TXT/HTML/DOCX/PDF or JSON profiles; "
            "请先将不受支持的格式转换为 Markdown、DOCX 或 TXT 后重试。"
        )
    if suffix == ".docx":
        return _extract_docx_markdown(p)
    if suffix in (".html", ".htm"):
        return _extract_html_markdown(_decode_text_bytes(p.read_bytes()))
    if suffix == ".pdf":
        return _extract_pdf_text(p)
    return _decode_text_bytes(p.read_bytes())


class ResumeTextParser:
    """Parses Markdown or plain-text resumes into structured OfferGet profile dicts."""

    # Section header identification patterns
    SECTION_PATTERNS = {
        "education": [
            r"教育(?:背景|经历|情况)",
            r"学历(?:背景|信息)?",
            r"education(?:al)?(?:\s+background)?",
            r"academic(?:\s+background)?",
        ],
        "competencies": [
            r"(?:专业|核心)?技能(?:清单|矩阵|概述)?",
            r"技术栈",
            r"competenc(?:ies|y)",
            r"(?:technical\s+)?skills?",
            r"tech\s+stack",
        ],
        "experience": [
            r"(?:工作|职业|实习|项目与工作)经历",
            r"(?:工作|实习)经验",
            r"(?:work\s+)?experience",
            r"employment(?:\s+history)?",
            r"internship(?:s)?",
        ],
        "projects": [
            r"(?:核心|重点|主要|个人|开源)?项目(?:经历|经验|作品|集)?",
            r"科研(?:经历|项目)?",
            r"projects?(?:\s+experience)?",
            r"key\s+projects?",
            r"portfolio",
        ],
        "honors": [
            r"(?:荣誉(?:奖项|资质)?|获奖(?:情况|经历|奖项)?|奖项(?:清单)?|奖学金)",
            r"honors?(?:\s*&|\s+and)?\s*awards?",
            r"awards?",
        ],

        "publications": [
            r"(?:学术|学术论文|发表)?论文(?:与专利)?",
            r"代表作",
            r"publications?",
            r"papers?",
            r"patents?",
        ],
        "narrative": [
            r"(?:个人|自我)(?:总结|评价|介绍|优势)",
            r"关于我",
            r"summary",
            r"profile(?:\s+summary)?",
            r"about\s+me",
            r"objective",
        ],
    }

    def __init__(self, raw_text: str):
        self.raw_text = raw_text.strip()
        self.lines = [line.rstrip() for line in self.raw_text.splitlines()]

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> ResumeTextParser:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Resume file not found: {file_path}")
        return cls(_read_resume_file(p))

    def parse(self) -> Dict[str, Any]:
        """Main entry point to parse raw text/markdown into standard profile dictionary."""
        candidate_info = self._parse_header()
        sections = self._split_sections()

        education_list = self._parse_education(sections.get("education", []))
        competencies_dict, flat_skills = self._parse_competencies(sections.get("competencies", []))
        experience_list = self._parse_experience(sections.get("experience", []))
        projects_list = self._parse_projects(sections.get("projects", []))
        honors_list = self._parse_list_section(sections.get("honors", []))
        publications_list = self._parse_list_section(sections.get("publications", []))
        narrative_text = self._parse_narrative(sections.get("narrative", []))

        # If degree or institution not in header, try extracting from education
        if not candidate_info.get("degree") and education_list:
            candidate_info["degree"] = education_list[0].get("degree", "")
        if not candidate_info.get("institution") and education_list:
            candidate_info["institution"] = education_list[0].get("school", "")
        if not candidate_info.get("major") and education_list:
            candidate_info["major"] = education_list[0].get("major", "")

        # Synthesize education badges if absent
        if not candidate_info.get("education_badges") and education_list:
            badges = []
            for edu in education_list:
                parts = [edu.get("school", ""), edu.get("degree", ""), edu.get("major", "")]
                non_empty = [p for p in parts if p]
                if non_empty:
                    badges.append(" · ".join(non_empty))
            candidate_info["education_badges"] = badges

        profile: Dict[str, Any] = {
            "profile_version": "2.0.0",
            "candidate": candidate_info,
            "narrative": {
                "summary_zh": narrative_text,
                "summary_en": "",
            },
            "education": education_list,
            "competencies": competencies_dict,
            "skills": flat_skills,
            "experience": experience_list,
            "projects": projects_list,
            "honors": honors_list,
            "publications": publications_list,
        }
        profile["_parse_report"] = self._build_parse_report(profile, sections)
        return profile

    def _build_parse_report(self, profile: Dict[str, Any], sections: Dict[str, List[str]]) -> Dict[str, Any]:
        warnings = []
        candidate = profile["candidate"]
        if not candidate.get("name") or candidate["name"] == "候选人":
            warnings.append({"code": "missing_name", "path": "candidate.name", "message": "未可靠识别姓名，请核对。"})
        if not (candidate.get("email") or candidate.get("phone")):
            warnings.append({"code": "missing_contact", "path": "candidate", "message": "未识别到电话或邮箱，请确认投递时使用的联系方式。"})
        for section in ("education", "experience", "projects"):
            for index, entry in enumerate(profile[section]):
                if not (entry.get("time") or entry.get("period")):
                    warnings.append({"code": "missing_date", "path": f"{section}[{index}].time",
                                     "message": "未识别到起止日期，请核对；确实无日期时可保留。"})
        unclassified = list(self.unclassified_lines)
        # Identify body text that did not survive the heuristic field parsers.
        corpus = re.sub(r"[\W_]+", "", json.dumps(profile, ensure_ascii=False)).lower()
        body_lines = {line for body in sections.values() for line in body}
        for number, line in enumerate(self.lines, 1):
            if self._is_section_header(line) or not line.strip() or line not in body_lines:
                continue
            tokens = [re.sub(r"[\W_]+", "", t).lower() for t in re.split(r"[\s|·，,:：()（）]+", self._content_line(line))]
            tokens = [t for t in tokens if len(t) > 1]
            if tokens and any(t not in corpus for t in tokens):
                unclassified.append({"line": number, "text": line, "reason": "需核对原文是否完整进入字段"})
        if unclassified:
            warnings.insert(0, {"code": "unclassified_content", "path": "_parse_report.unclassified_lines",
                                "message": f"有 {len(unclassified)} 行原文需核对归类，尚不能确认完整导入。"})
        return {"status": "needs_review" if warnings else "parsed",
                "recognized_counts": {s: len(profile[s]) for s in ("education", "experience", "projects", "skills", "honors", "publications")},
                "warnings": warnings, "unclassified_lines": unclassified,
                "next_action": "先核对未归类原文及缺失字段，再确认简历内容。" if warnings else "核对识别结果后，可使用默认主题导出。"}

    # -------------------------------------------------------------------------
    # Header & Contact Extraction
    # -------------------------------------------------------------------------
    def _parse_header(self) -> Dict[str, Any]:
        """Extract candidate personal info from the top lines before the first section."""
        header_lines: List[str] = []
        for line in self.lines:
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_section_header(stripped):
                break
            header_lines.append(stripped)

        header_text = "\n".join(header_lines)

        # 1. Candidate Name
        name = "候选人"
        if header_lines:
            first_line = header_lines[0]
            # Strip markdown heading
            cleaned = re.sub(r"^[#\*\s]+", "", first_line).strip()
            # Clean suffixes like "简历", "Resume", "CV", "个人简历"
            cleaned = re.sub(r"[\s_—\-(]*(?:个人)?(?:简历|Resume|CV)[\s_—\-]*(?:[0-9]{4})?$", "", cleaned, flags=re.IGNORECASE).strip()
            if cleaned and len(cleaned) <= 30:
                name = cleaned

        # 2. Email
        email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", header_text)
        email = email_match.group(1) if email_match else ""

        # 3. Phone
        phone_match = re.search(r"((?:\+?86[- ]?)?1[3-9]\d(?:[- ]?\d{4}){2}|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b)", header_text)
        phone = phone_match.group(1) if phone_match else ""

        # 4. Links (GitHub, LinkedIn)
        github_match = re.search(r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+)", header_text, re.IGNORECASE)
        github = f"https://github.com/{github_match.group(1)}" if github_match else ""

        linkedin_match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_-]+)", header_text, re.IGNORECASE)
        linkedin = f"https://linkedin.com/in/{linkedin_match.group(1)}" if linkedin_match else ""

        # 5. Location
        location = ""
        loc_match = re.search(r"(?:城市|地点|期望地点|Location|Base)?[:：\s]*((?:北京|上海|深圳|广州|杭州|成都|武汉|南京|西安|苏州|厦门|远程|Remote)(?:\s*(?:/|、|,)\s*(?:北京|上海|深圳|广州|杭州|成都|武汉|南京|西安|苏州|厦门|远程|Remote))*)", header_text)
        if loc_match:
            location = loc_match.group(1).strip()
        else:
            for city in ["北京", "上海", "深圳", "杭州", "广州", "成都", "武汉", "南京", "Remote"]:
                if city in header_text:
                    location = city
                    break


        # 6. Years of Experience
        yoe = 0.0
        yoe_match = re.search(r"(\d+)(?:\+)?\s*(?:年|years?)(?:研发|工作|相关)?(?:经验)?", header_text, re.IGNORECASE)
        if yoe_match:
            try:
                yoe = float(yoe_match.group(1))
            except ValueError:
                yoe = 0.0

        # 7. Professional Title
        title_zh = ""
        title_match = re.search(r"(?:职位|求职意向|意向岗位|Title)?[:：\s]*([^\n|•·]+(?:架构师|工程师|开发|算法|专家|Tech Lead|Researcher|Engineer|Developer))", header_text, re.IGNORECASE)
        if title_match:
            title_zh = title_match.group(1).strip()

        # 8. Degree & School
        degree = ""
        for d in ["博士 (Ph.D.)", "博士", "硕士 (Master)", "硕士", "本科 (Bachelor)", "本科", "大专"]:
            clean_d = d.split()[0]
            if clean_d in header_text:
                degree = d
                break

        institution = ""
        inst_match = re.search(r"([\u4e00-\u9fa5]+(?:大学|学院|研究所))", header_text)
        if inst_match:
            institution = inst_match.group(1)

        return {
            "name": name,
            "title_zh": title_zh,
            "title_en": "",
            "email": email,
            "phone": phone,
            "location": location,
            "github": github,
            "linkedin": linkedin,
            "years_of_experience": yoe,
            "degree": degree,
            "institution": institution,
            "major": "",
            "education_badges": [],
        }

    # -------------------------------------------------------------------------
    # Section Splitting
    # -------------------------------------------------------------------------
    def _content_line(self, line: str) -> str:
        """Normalize a section body line for content parsers.

        Markdown sub-headings inside a section often carry real entry data
        (e.g. ``### 2020.09 - 2024.06 | 清华大学``), so heading markers are
        stripped instead of dropping the whole line. Recognized nested section
        titles (``## 荣誉奖项``) are swallowed to avoid polluting entries.
        """
        cleaned = line.strip()
        if cleaned.startswith("#"):
            cleaned = re.sub(r"^#{1,6}\s*", "", cleaned).strip()
            if not cleaned or self._is_section_header(cleaned):
                return ""
        return cleaned

    def _is_section_header(self, line: str) -> Optional[str]:
        """Checks if a line represents a known section header; returns section name or None."""
        cleaned = re.sub(r"^[#\*\s\-【\[\(]+|[】\]\)\*\s]+$", "", line).strip()
        if not cleaned or len(cleaned) > 40:
            return None

        for section_name, patterns in self.SECTION_PATTERNS.items():
            for pat in patterns:
                if re.fullmatch(pat, cleaned, re.IGNORECASE) or re.search(rf"^{pat}$", cleaned, re.IGNORECASE):
                    return section_name
        return None

    def _split_sections(self) -> Dict[str, List[str]]:
        """Splits raw text lines into named section line lists."""
        sections: Dict[str, List[str]] = {}
        current_section: Optional[str] = None
        self.unclassified_lines: List[Dict[str, Any]] = []
        section_level = 2
        unknown_section = False

        for number, line in enumerate(self.lines, 1):
            stripped = line.strip()
            sec = self._is_section_header(stripped)
            if sec:
                current_section = sec
                if current_section not in sections:
                    sections[current_section] = []
                heading = re.match(r"^(#{1,6})\s", stripped)
                section_level = len(heading.group(1)) if heading else 2
                unknown_section = False
                continue

            heading = re.match(r"^(#{1,6})\s", stripped)
            if number > 1 and heading and len(heading.group(1)) <= section_level:
                current_section = None
                unknown_section = True
            if unknown_section and stripped:
                self.unclassified_lines.append({"line": number, "text": line, "reason": "未识别的章节"})
                continue

            if current_section:
                sections[current_section].append(line)

        return sections

    # -------------------------------------------------------------------------
    # Section Parsers
    # -------------------------------------------------------------------------
    def _parse_education(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse lines in education section into list of education entries."""
        entries: List[Dict[str, Any]] = []
        for line in lines:
            stripped = self._content_line(line)
            if not stripped:
                continue

            # Check if line contains school, major, degree, or time
            time_match = re.search(r"((?:20\d\d|19\d\d)(?:[.\-/年]\d{1,2}月?)?(?:\s*[-—~至到]\s*(?:至今|Present|现在|(?:20\d\d|19\d\d)(?:[.\-/年]\d{1,2}月?)?))?)", stripped)
            time_str = time_match.group(1).strip() if time_match else ""

            # Degree detection
            degree = ""
            for d in ["博士", "硕士", "本科", "学士", "大专", "Ph.D", "Master", "Bachelor"]:
                if d in stripped:
                    degree = d
                    break

            # Remove time and bullet prefixes to parse school/major
            core = re.sub(r"^[-*•\s]+", "", stripped)
            if time_str:
                core = core.replace(time_str, "")
            core = re.sub(r"[|｜()（）]", " ", core).strip()

            tokens = [t.strip() for t in re.split(r"[\s·,，]+", core) if t.strip()]
            school = ""
            major = ""
            for tok in tokens:
                if any(k in tok for k in ["大学", "学院", "分校", "University", "College", "Institute"]):
                    if not school:
                        school = tok
                elif any(k in tok for k in ["专业", "系", "工程", "科学", "技术", "智能", "数学", "物理", "自动化", "计算机"]):
                    if not major:
                        major = tok

            # Fallbacks if regex didn't isolate them
            if not school and tokens:
                school = tokens[0]
            if not major and len(tokens) > 1:
                major = tokens[1]

            if school or degree or major:
                entries.append({
                    "school": school,
                    "institution": school,
                    "major": major,
                    "degree": degree,
                    "time": time_str,
                    "period": time_str,
                })

        return entries

    def _parse_competencies(self, lines: List[str]) -> Tuple[Dict[str, List[str]], List[str]]:
        """Parse competencies into categorized dict and flat list."""
        competencies: Dict[str, List[str]] = {
            "programming": [],
            "frameworks": [],
            "infra_and_systems": [],
            "domain_skills": [],
        }
        flat_skills: List[str] = []

        category_map = {
            r"编程语言|语言|programming|languages?": "programming",
            r"框架|深度学习|算法|ai|ml|frameworks?|libraries": "frameworks",
            r"系统|架构|基础设施|分布式|云原生|infra|system|database": "infra_and_systems",
        }

        for line in lines:
            stripped = self._content_line(line)
            if not stripped:
                continue

            cleaned = re.sub(r"^[-*•\d\.\s]+", "", stripped).strip()
            # Check if line has "Category: item1, item2, item3"
            cat_match = re.match(r"^([^:：]{2,15})[:：]\s*(.+)$", cleaned)
            if cat_match:
                cat_name = cat_match.group(1).strip()
                items_str = cat_match.group(2).strip()

                # Determine category key
                target_key = "domain_skills"
                for pat, key in category_map.items():
                    if re.search(pat, cat_name, re.IGNORECASE):
                        target_key = key
                        break

                items = [item.strip() for item in re.split(r"[,，、;；|]\s*|\s+/\s+", items_str) if item.strip()]
                competencies.setdefault(target_key, []).extend(items)
                flat_skills.extend(items)
            else:
                # Flat bullet point
                items = [item.strip() for item in re.split(r"[,，、;；|]\s*|\s+/\s+", cleaned) if item.strip()]
                competencies["domain_skills"].extend(items)
                flat_skills.extend(items)


        # Deduplicate while preserving order
        dedup_flat = list(dict.fromkeys(flat_skills))
        for k in list(competencies.keys()):
            competencies[k] = list(dict.fromkeys(competencies[k]))
            if not competencies[k]:
                competencies.pop(k, None)

        return competencies, dedup_flat

    def _parse_experience(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse work/internship experiences."""
        experiences: List[Dict[str, Any]] = []
        current_exp: Optional[Dict[str, Any]] = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check if this line is an experience entry header (e.g. ### 字节跳动 · 算法工程师 (2022-2024))
            header_match = self._is_entry_header(stripped)
            if header_match:
                if current_exp:
                    experiences.append(current_exp)
                org, role, time_str = header_match
                current_exp = {
                    "company": org,
                    "org": org,
                    "role": role,
                    "time": time_str,
                    "period": time_str,
                    "bullets": [],
                    "highlights": [],
                }
            elif current_exp:
                # Bullet point or descriptive sentence
                bullet = re.sub(r"^[-*•\d\.\s]+", "", stripped).strip()
                if bullet:
                    current_exp["bullets"].append(bullet)
                    # Check for verified metrics
                    metrics_match = re.search(r"(\d+(?:\.\d+)?(?:%|倍|ms|s|TPS|QPS|G|T|P|万|亿|k|M|B|RMB|元))", bullet)
                    current_exp["highlights"].append({
                        "claim_zh": bullet,
                        "verified_metrics": metrics_match.group(1) if metrics_match else "",
                    })

        if current_exp:
            experiences.append(current_exp)

        return experiences

    def _parse_projects(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse project entries."""
        projects: List[Dict[str, Any]] = []
        current_proj: Optional[Dict[str, Any]] = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            header_match = self._is_entry_header(stripped)
            if header_match:
                if current_proj:
                    projects.append(current_proj)
                p_name, role, time_str = header_match
                current_proj = {
                    "name": p_name,
                    "role": role or "核心开发者",
                    "time": time_str,
                    "period": time_str,
                    "description": "",
                    "bullets": [],
                }
            elif current_proj:
                # Check if this bullet declares role or time: e.g. - **角色**：核心负责人 | 2023.10 - 2024.04
                role_match = re.search(r"(?:角色|Role)[:：\s*]*([^\n|•·]+)", stripped)
                time_match = re.search(r"((?:20\d\d|19\d\d)(?:[.\-/年]\d{1,2}月?)?(?:\s*[-—~至到]\s*(?:至今|Present|现在|(?:20\d\d|19\d\d)(?:[.\-/年]\d{1,2}月?)?))?)", stripped)
                if role_match and not current_proj.get("role"):
                    current_proj["role"] = role_match.group(1).replace("*", "").strip()
                if time_match and not current_proj.get("time"):
                    current_proj["time"] = time_match.group(1).strip()
                    current_proj["period"] = time_match.group(1).strip()

                bullet = re.sub(r"^[-*•\d\.\s]+", "", stripped).strip()
                if bullet and not (role_match and len(bullet) < 50):
                    current_proj["bullets"].append(bullet)

        if current_proj:
            projects.append(current_proj)

        return projects

    def _is_entry_header(self, line: str) -> Optional[Tuple[str, str, str]]:
        """Detects if a line looks like 'Org/Project · Role (2022.03 - 2024.01)'."""
        # Never treat bullets or numbered lists as entry headers
        if re.match(r"^[-*•\d\.]+\s+", line):
            return None

        # Check time pattern
        time_match = re.search(r"((?:20\d\d|19\d\d)(?:[.\-/年]\d{1,2}月?)?(?:\s*[-—~至到]\s*(?:至今|Present|现在|(?:20\d\d|19\d\d)(?:[.\-/年]\d{1,2}月?)?))?)", line)
        time_str = time_match.group(1).strip() if time_match else ""

        is_heading = line.startswith(("#", "**"))
        # If it's a markdown heading or has explicit delimiter with time
        if is_heading or (time_str and any(delim in line for delim in ["·", "|", "｜", " - ", "—"])):
            cleaned = re.sub(r"^[#\*\s]+|[\*\s]+$", "", line).strip()
            if time_str:
                cleaned = cleaned.replace(time_str, "").strip()
            cleaned = re.sub(r"[\(\)（）]+", " ", cleaned).strip()

            # Split only on explicit separators: ·, |, ｜, —, or " - "
            parts = [p.strip() for p in re.split(r"\s*(?:·|[|｜—]|\s+-\s+)\s*", cleaned) if p.strip()]
            if not parts:
                return None

            org_or_name = parts[0]
            role = parts[1] if len(parts) > 1 else ""
            return (org_or_name, role, time_str)

        return None


    def _parse_list_section(self, lines: List[str]) -> List[str]:
        """Parse list-based sections like Honors, Awards, Publications."""
        items: List[str] = []
        for line in lines:
            stripped = self._content_line(line)
            if not stripped:
                continue
            cleaned = re.sub(r"^[-*•\d\.\s]+", "", stripped).strip()
            if cleaned:
                items.append(cleaned)
        return items

    def _parse_narrative(self, lines: List[str]) -> str:
        """Parse narrative/summary section into a consolidated paragraph."""
        paragraphs: List[str] = []
        for line in lines:
            stripped = self._content_line(line)
            if not stripped:
                continue
            cleaned = re.sub(r"^[-*•\s]+", "", stripped).strip()
            if cleaned:
                paragraphs.append(cleaned)
        return " ".join(paragraphs)


def parse_resume_to_profile(text_or_path: Union[str, Path]) -> Dict[str, Any]:
    """Helper that parses a resume file or string into a validated OfferGet profile dict."""
    if isinstance(text_or_path, Path) or (isinstance(text_or_path, str) and os.path.exists(text_or_path)):
        p = Path(text_or_path)
        if p.is_file():
            text = _read_resume_file(p)
            # If it's already JSON, parse directly
            if p.suffix.lower() == ".json":
                try:
                    data = json.loads(text)
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
            if p.suffix.lower() == ".bib":
                from core.academic_sync import BibTexPublicationParser

                entries = BibTexPublicationParser.parse_string(text)
                pubs = [
                    {
                        "title": e.title,
                        "authors": e.authors,
                        "venue": e.venue,
                        "year": str(e.year) if e.year else "",
                        **({"url": e.url} if e.url else {}),
                        **({"doi": e.doi} if e.doi else {}),
                        **({"status": e.status} if e.status else {}),
                        **({"ccf_rank": e.ccf_rank} if e.ccf_rank and e.ccf_rank != "None" else {}),
                    }
                    for e in entries
                ]
                return {"candidate": {}, "publications": pubs}
            return ResumeTextParser(text).parse()

    # Raw string
    text = str(text_or_path).strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return ResumeTextParser(text).parse()
