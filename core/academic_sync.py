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
    ccf_rank: str = "None"  # CCF-A, CCF-B, CCF-C, SCI-Q1, SCI-Q2, None
    presentation_type: str = "Regular"  # Oral, Spotlight, Poster, Regular
    is_first_or_corresponding: bool = False


@dataclass
class CampPresentationSlide:
    """夏令营/保研/学术面试单页 PPT 规范"""
    page_number: int
    slide_title: str
    allocated_seconds: int
    key_talking_points: List[str] = field(default_factory=list)
    visual_layout_suggestion: str = ""
    script_preview: str = ""


@dataclass
class CampPresentationPlan:
    """3-5 分钟夏令营面试自我介绍 PPT 全套方案"""
    candidate_name: str
    target_lab_or_institution: str
    total_target_seconds: int
    slides: List[CampPresentationSlide] = field(default_factory=list)
    markdown_outline: str = ""


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
                    ccf_rank=ccf,
                    presentation_type=presentation,
                    is_first_or_corresponding=is_first,
                )
            )

        return entries


class CampPresentationPlanner:
    """规划 3~5 分钟夏令营/学术面试自述 PPT 规范与逐页脚本"""

    @classmethod
    def plan(
        cls,
        candidate_name: str,
        target_lab_or_institution: str,
        target_direction: str,
        publications: List[AcademicPublication],
        key_projects: List[str],
        total_seconds: int = 210,  # 默认 3.5 分钟 (210 秒)
    ) -> CampPresentationPlan:
        # P1: 个人画像与学术底色 (45s)
        p1 = CampPresentationSlide(
            page_number=1,
            slide_title="个人学术画像与学业基石 (Academic Portrait & Foundation)",
            allocated_seconds=45,
            key_talking_points=[
                f"教育背景与专业排名，展现稳扎稳打的数理计算机基础",
                f"保研推免资格、国家奖学金或竞赛核心荣誉",
                f"为什么坚定选择 {target_lab_or_institution} 攻读硕士/博士学位",
            ],
            visual_layout_suggestion="左侧个人照/院系背景，右侧 3 栏指标卡片（GPA排名、核心课程均分、核心荣誉清单）。",
            script_preview=(
                f"各位老师好，我是 {candidate_name}。非常荣幸能参加 {target_lab_or_institution} 的学术选拔交流。"
                f"本科期间我始终保持对前沿技术的探索好奇心，专业排名前列，具备扎实的数理与计算机系统底座。"
            ),
        )

        # P2: 代表性科研攻关与论文发表 (60s)
        top_pub = publications[0] if publications else None
        pub_title = top_pub.title if top_pub else "前沿课题学术攻关与算法探索"
        pub_venue = f"{top_pub.venue} ({top_pub.ccf_rank})" if top_pub else "高水平学术成果"
        p2 = CampPresentationSlide(
            page_number=2,
            slide_title="代表性科研突破与学术产出 (Representative Research & Paper)",
            allocated_seconds=60,
            key_talking_points=[
                f"核心突破课题: {pub_title}",
                f"发表/录用情况: {pub_venue}",
                f"针对传统方法的根本缺陷，阐明本人的第一创新点与数学/算法推导",
                f"实验收益与对比基线，突出严谨可复现的科研范式",
            ],
            visual_layout_suggestion="左侧研究背景架构图与问题形式化，右侧关键实验消融对比曲线柱状图与论文录用证明截屏。",
            script_preview=(
                f"在科研攻关方面，针对 {target_direction} 场景下的关键性能瓶颈，我主导推进了相关算法优化。"
                f"成果发表/录用于 {pub_venue}。我们提出的方法相比既有 SOTA 基线取得了显著提升。"
            ),
        )

        # P3: 复杂工程项目实操与系统攻坚 (60s)
        proj_str = "、".join(key_projects[:2]) if key_projects else "高并发分布式系统实战"
        p3 = CampPresentationSlide(
            page_number=3,
            slide_title="核心系统工程与攻坚落地 (Engineering Delivery & Systems)",
            allocated_seconds=60,
            key_talking_points=[
                f"工程实战项目: {proj_str}",
                f"拒绝纸上谈兵：展现真实集群部署、高并发压测或落地开销优化能力",
                f"核心解决的不可替代工程难点与指标收益",
            ],
            visual_layout_suggestion="上半部分系统拓扑链路流转图，下半部分核心模块时序与指标基线对比表。",
            script_preview=(
                f"除了算法推演，我高度重视工程落地素养。在 {proj_str} 项目中，"
                f"我负责核心底座构建与全链路压测，保障了系统在高负载下的极致低延时与高可用性。"
            ),
        )

        # P4: 读研学术志趣与意向课题规划 (45s)
        p4 = CampPresentationSlide(
            page_number=4,
            slide_title="研究生学术志趣与意向课题规划 (Future Vision & Lab Roadmap)",
            allocated_seconds=45,
            key_talking_points=[
                f"紧密贴合课题组在 {target_direction} 领域的前沿规划",
                f"研一至研三阶梯式产出路线（基础攻坚 -> 顶会产出 -> 落地转化）",
                f"表达能打硬仗、潜心科研的学术决心",
            ],
            visual_layout_suggestion="未来三年发展甘特图 / 意向课题三角支撑图（技术底座 + 创新课题 + 课题组需求）。",
            script_preview=(
                f"若有幸加入 {target_lab_or_institution}，我希望在 {target_direction} 方向持续深耕。"
                f"我已阅读了课题组近期的代表性工作，期待能与各位老师深入探讨，贡献扎实的学术与工程力量！谢谢各位老师！"
            ),
        )

        slides = [p1, p2, p3, p4]

        # 组织 Markdown 大纲
        md_lines = [
            f"# 🎓 {candidate_name} - 夏令营/保研面试 4 页自述 PPT 规范方案",
            f"- **目标院系/实验室**: {target_lab_or_institution}",
            f"- **意向研究方向**: {target_direction}",
            f"- **建议控时**: 3分30秒 (共 210 秒，预留 30 秒弹性机动)",
            "",
        ]
        for s in slides:
            md_lines.extend([
                f"## P{s.page_number}. {s.slide_title} (⏱️ {s.allocated_seconds}s)",
                f"- **视觉排版布局建议**: {s.visual_layout_suggestion}",
                "- **核心阐述要点**:",
            ])
            for pt in s.key_talking_points:
                md_lines.append(f"  * {pt}")
            md_lines.extend([
                f"- **现场讲稿口径参考**:",
                f"  > \"{s.script_preview}\"",
                "",
            ])

        markdown_outline = "\n".join(md_lines).strip()

        return CampPresentationPlan(
            candidate_name=candidate_name,
            target_lab_or_institution=target_lab_or_institution,
            total_target_seconds=total_seconds,
            slides=slides,
            markdown_outline=markdown_outline,
        )
