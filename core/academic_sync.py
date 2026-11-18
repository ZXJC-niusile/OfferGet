from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AcademicPublication:
    """学术论文/科研产出标准数据类"""
    cite_key: str
    entry_type: str  # inproceedings, article, conference, misc
    title: str
    authors: List[str] = field(default_factory=list)
    venue: str = ""  # 会议名或期刊名
    year: int = 0
    doi: str = ""
    url: str = ""
    status: str = ""
    ccf_rank: str = "None"  # CCF-A, CCF-B, CCF-C, SCI-Q1, SCI-Q2, None
    presentation_type: str = "Regular"  # Oral, Spotlight, Poster, Regular
    is_first_or_corresponding: bool = False


class BibTexPublicationParser:
    """BibTeX 学术引文解析与等级推断器"""

    # 常见知名顶级会议/期刊简写映射
    KNOWN_CCF_A = {
        "cvpr", "iccv", "neurips", "icml", "iclr", "acl", "kdd", "sigmod",
        "vldb", "osdi", "sosp", "atc", "usenix atc", "aaai", "ijcai", "www",
    }
    KNOWN_CCF_B = {
        "eccv", "emnlp", "cikm", "icde", "fast", "infocom", "sensys",
    }

    @classmethod
    def _clean_latex_braces(cls, text: str) -> str:
        if not text:
            return ""
        # 移除 {} 和多余空白
        res = re.sub(r"[\{\}]", "", text)
        return " ".join(res.split())

    @classmethod
    def _infer_ccf(cls, venue: str) -> str:
        v_low = venue.lower()
        for a_conf in cls.KNOWN_CCF_A:
            if re.search(r"\b" + re.escape(a_conf) + r"\b", v_low):
                return "CCF-A"
        for b_conf in cls.KNOWN_CCF_B:
            if re.search(r"\b" + re.escape(b_conf) + r"\b", v_low):
                return "CCF-B"
        return "None"

    @classmethod
    def _split_bibtex_entries(cls, text: str) -> List[tuple[str, str, str]]:
        """使用平衡括号状态机切分 BibTeX 条目，完美支持多层嵌套括号"""
        entries = []
        i = 0
        n = len(text)
        while i < n:
            at_idx = text.find('@', i)
            if at_idx == -1:
                break
            open_brace = text.find('{', at_idx)
            if open_brace == -1:
                break
            entry_type = text[at_idx + 1:open_brace].strip().lower()
            depth = 1
            idx = open_brace + 1
            while idx < n and depth > 0:
                ch = text[idx]
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                idx += 1
            if depth == 0:
                entry_content = text[open_brace + 1:idx - 1]
                if ',' in entry_content:
                    cite_key, fields_body = entry_content.split(',', 1)
                    entries.append((entry_type, cite_key.strip(), fields_body.strip()))
                i = idx
            else:
                i = open_brace + 1
        return entries

    @classmethod
    def _parse_bibtex_fields(cls, fields_body: str) -> Dict[str, str]:
        """解析单条目内的字段，支持嵌套括号和引号"""
        fields: Dict[str, str] = {}
        i = 0
        n = len(fields_body)
        while i < n:
            eq_idx = fields_body.find('=', i)
            if eq_idx == -1:
                break
            raw_key = fields_body[i:eq_idx].strip().rstrip(',').strip()
            key_match = re.search(r'([a-zA-Z0-9_-]+)$', raw_key)
            if not key_match:
                i = eq_idx + 1
                continue
            field_name = key_match.group(1).lower()

            v_start = eq_idx + 1
            while v_start < n and fields_body[v_start] in ' \t\r\n':
                v_start += 1
            if v_start >= n:
                break

            if fields_body[v_start] == '{':
                depth = 1
                v_curr = v_start + 1
                while v_curr < n and depth > 0:
                    if fields_body[v_curr] == '{':
                        depth += 1
                    elif fields_body[v_curr] == '}':
                        depth -= 1
                    v_curr += 1
                field_val = fields_body[v_start + 1:v_curr - 1]
                fields[field_name] = cls._clean_latex_braces(field_val)
                i = v_curr
            elif fields_body[v_start] == '"':
                v_end = fields_body.find('"', v_start + 1)
                if v_end == -1:
                    v_end = n
                field_val = fields_body[v_start + 1:v_end]
                fields[field_name] = cls._clean_latex_braces(field_val)
                i = v_end + 1
            else:
                comma_idx = fields_body.find(',', v_start)
                if comma_idx == -1:
                    comma_idx = n
                field_val = fields_body[v_start:comma_idx].strip()
                fields[field_name] = cls._clean_latex_braces(field_val)
                i = comma_idx + 1
        return fields

    @classmethod
    def parse_string(
        cls,
        bib_content: str,
        candidate_name: Optional[str] = None,
    ) -> List[AcademicPublication]:
        """从字符串解析多条 BibTeX 条目"""
        entries: List[AcademicPublication] = []
        if not bib_content.strip():
            return entries

        raw_entries = cls._split_bibtex_entries(bib_content)
        for entry_type, cite_key, fields_body in raw_entries:
            field_dict = cls._parse_bibtex_fields(fields_body)

            title = field_dict.get("title", "")
            venue = field_dict.get("booktitle") or field_dict.get("journal") or ""
            year_str = field_dict.get("year", "0")
            year = int(re.sub(r"\D", "", year_str) or 0)
            doi = field_dict.get("doi", "")
            url = field_dict.get("url", "")
            status = field_dict.get("status") or field_dict.get("note") or field_dict.get("howpublished") or ""
            presentation = field_dict.get("presentation", "Regular")
            if "oral" in fields_body.lower():
                presentation = "Oral"
            elif "spotlight" in fields_body.lower():
                presentation = "Spotlight"

            # 解析作者列表
            author_raw = field_dict.get("author", "")
            authors: List[str] = []
            if author_raw:
                parts = author_raw.split(" and ")
                for p in parts:
                    clean_author = p.strip()
                    if "," in clean_author:
                        # Lastname, Firstname -> Firstname Lastname
                        sub_p = clean_author.split(",", 1)
                        clean_author = f"{sub_p[1].strip()} {sub_p[0].strip()}"
                    authors.append(clean_author)

            # 判定候选人是否为一作或通讯作者
            is_first = False
            if candidate_name and authors:
                cand_low = candidate_name.lower().replace(" ", "")
                first_low = authors[0].lower().replace(" ", "")
                if cand_low in first_low or first_low in cand_low:
                    is_first = True

            ccf = cls._infer_ccf(venue)

            entries.append(
                AcademicPublication(
                    cite_key=cite_key,
                    entry_type=entry_type,
                    title=title,
                    authors=authors,
                    venue=venue,
                    year=year,
                    doi=doi,
                    url=url,
                    status=status,
                    ccf_rank=ccf,
                    presentation_type=presentation,
                    is_first_or_corresponding=is_first,
                )
            )

        return entries
