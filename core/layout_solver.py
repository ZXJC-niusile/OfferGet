"""
OfferGet Adaptive Layout Solver & Micro-typography Engine (core/layout_solver.py)
==================================================================================
Eliminates naive, destructive layout compaction patterns:
1. Strict font size baseline: Enforces body_font_pt >= 9.5pt (recommended 10.0pt).
   Rejects crude reduction to unreadable 7-8pt fonts.
2. Anti-abbreviation guarantee: Preserves full academic courses and professional
   titles (e.g. 'Probability and Mathematical Statistics', 'Civil Engineering',
   'Engineering Project Management'). Refuses to truncate to 'Math Stats' or 'Civil Eng.'.
3. Springs & Glue Vertical Budgeting (TeX \\vskip model):
   When overflow occurs, systematically absorbs overflow across elastic vertical
   elements (section margins, item gaps, page padding, line height, micro letter spacing)
   BEFORE touching font size. Font size is strictly clamped to min_body_font_pt.
4. Orphan & Widow Mitigator (孤字与孤行检测与消除器):
   Eliminates lone trailing words (e.g. 'Engineering') and single Chinese characters
   using &nbsp; binding on fragile phrases and trailing spaces, plus modern CSS
   text-wrap: pretty and text-wrap: balance.
5. Adaptive Flow Grid for Coursework & Certifications:
   Calculates character metrics to dynamically generate 2-column or flow grids
   allowing natural multi-line wrapping without clipping or abbreviations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

# Physical and Typography Constants (Standard 96 DPI screen/browser rendering)
PT_TO_PX: float = 96.0 / 72.0          # 1.333333... px per pt
MM_TO_PX: float = 96.0 / 25.4          # 3.779527... px per mm
PX_TO_PT: float = 72.0 / 96.0          # 0.75 pt per px
PX_TO_MM: float = 25.4 / 96.0          # 0.264583... mm per px

A4_HEIGHT_PX: float = 1122.5           # 297mm @ 96 DPI
A4_WIDTH_PX: float = 793.7             # 210mm @ 96 DPI
MIN_BODY_FONT_PT_FLOOR: float = 9.5    # Strict uncompromisable design baseline


@dataclass
class LayoutConfig:
    """Configuration and strict design boundaries for adaptive resume typography."""

    min_body_font_pt: float = 9.5      # Strict baseline:正文绝不允许小于 9.5pt
    target_body_font_pt: float = 10.0  # Recommended default: 10pt
    a4_height_px: float = A4_HEIGHT_PX # 1122.5px (297mm @ 96DPI)
    a4_width_px: float = A4_WIDTH_PX   # 793.7px (210mm @ 96DPI)
    min_line_height: float = 1.35
    max_line_height: float = 1.55
    target_line_height: float = 1.45
    allow_term_abbreviation: bool = False  # 绝不为了单行阉割规范术语！课程与职位完整表达优先于死板单行

    # Springs & Glue vertical budgeting limits (TeX \\vskip model)
    min_section_margin_pt: float = 10.0
    target_section_margin_pt: float = 14.0
    max_section_margin_pt: float = 16.0

    min_item_gap_pt: float = 4.0
    target_item_gap_pt: float = 6.0
    max_item_gap_pt: float = 8.0

    min_page_padding_y_mm: float = 7.0
    target_page_padding_y_mm: float = 10.0
    max_page_padding_y_mm: float = 14.0
    max_body_font_pt: float = 10.5

    # Micro-typography tuning ranges
    letter_spacing_min_em: float = -0.015
    letter_spacing_max_em: float = 0.010
    target_letter_spacing_em: float = -0.005

    word_spacing_min_em: float = -0.02
    word_spacing_max_em: float = 0.02
    target_word_spacing_em: float = 0.0

    enable_micro_typography: bool = True
    enable_adaptive_grid: bool = True
    enable_widow_orphan_mitigation: bool = True
    page_mode: str = "1"                 # "1" (strict single page), "2" (double page), "auto" (auto-expand if needed)

    def __post_init__(self):
        """Enforces design bottom-lines and structural sanity."""
        if self.min_body_font_pt < MIN_BODY_FONT_PT_FLOOR:
            raise ValueError(
                f"Design baseline violation: min_body_font_pt ({self.min_body_font_pt}pt) "
                f"cannot be less than strict floor {MIN_BODY_FONT_PT_FLOOR}pt. "
                f"Crude font downsizing violates professional resume standards."
            )
        if self.target_body_font_pt < self.min_body_font_pt:
            self.target_body_font_pt = self.min_body_font_pt
        if self.max_body_font_pt < self.target_body_font_pt:
            self.max_body_font_pt = self.target_body_font_pt
        if self.min_line_height < 1.20:
            self.min_line_height = 1.20
        if self.max_line_height < self.min_line_height:
            self.max_line_height = self.min_line_height
        if self.page_mode not in ("1", "2", "auto"):
            self.page_mode = "auto"


@dataclass
class LayoutSolveResult:
    """Complete report and artifacts from the adaptive layout solver."""

    solved: bool
    body_font_pt: float                # Guaranteed >= min_body_font_pt (9.5pt)
    line_height: float
    section_margin_pt: float
    item_gap_pt: float
    page_padding_y_mm: float
    letter_spacing_em: float
    word_spacing_em: float
    initial_overflow_px: float
    overflow_px_remaining: float
    applied_compressions: List[str]
    abbreviations_prevented: List[str]
    orphans_mitigated: int
    css_rules: str
    html: str
    is_expanded_to_fill: bool = False
    requires_page_expansion_prompt: bool = False
    page_expansion_prompt_message: Optional[str] = None
    target_pages_solved: int = 1


# ==============================================================================
# 1. Orphan & Widow Mitigator (孤字与孤行检测与消除器)
# ==============================================================================

# Commonly used multi-word academic & industry phrases vulnerable to awkward wraps
FRAGILE_NOUN_PHRASES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bProbability\s+and\s+Mathematical\s+Statistics\b", re.IGNORECASE), "Probability&nbsp;and&nbsp;Mathematical&nbsp;Statistics"),
    (re.compile(r"\bMathematical\s+Statistics\b", re.IGNORECASE), "Mathematical&nbsp;Statistics"),
    (re.compile(r"\bEngineering\s+Project\s+Management\b", re.IGNORECASE), "Engineering&nbsp;Project&nbsp;Management"),
    (re.compile(r"\bProject\s+Management\b", re.IGNORECASE), "Project&nbsp;Management"),
    (re.compile(r"\bCivil\s+Engineering\b", re.IGNORECASE), "Civil&nbsp;Engineering"),
    (re.compile(r"\bComputer\s+Science\b", re.IGNORECASE), "Computer&nbsp;Science"),
    (re.compile(r"\bSoftware\s+Engineering\b", re.IGNORECASE), "Software&nbsp;Engineering"),
    (re.compile(r"\bInformation\s+Systems\b", re.IGNORECASE), "Information&nbsp;Systems"),
    (re.compile(r"\bData\s+Science\b", re.IGNORECASE), "Data&nbsp;Science"),
    (re.compile(r"\bMachine\s+Learning\b", re.IGNORECASE), "Machine&nbsp;Learning"),
    (re.compile(r"\bDeep\s+Learning\b", re.IGNORECASE), "Deep&nbsp;Learning"),
    (re.compile(r"\bArtificial\s+Intelligence\b", re.IGNORECASE), "Artificial&nbsp;Intelligence"),
    (re.compile(r"\bOperations\s+Research\b", re.IGNORECASE), "Operations&nbsp;Research"),
    (re.compile(r"\bDistributed\s+Systems\b", re.IGNORECASE), "Distributed&nbsp;Systems"),
    (re.compile(r"\bOperating\s+Systems\b", re.IGNORECASE), "Operating&nbsp;Systems"),
    (re.compile(r"\bComputer\s+Networks\b", re.IGNORECASE), "Computer&nbsp;Networks"),
    (re.compile(r"\bQuantitative\s+Analysis\b", re.IGNORECASE), "Quantitative&nbsp;Analysis"),
    (re.compile(r"\bHigh\s+Availability\b", re.IGNORECASE), "High&nbsp;Availability"),
]


class OrphanWidowMitigator:
    """Detects and resolves typographic orphans and widows in text and HTML nodes."""

    @staticmethod
    def detect_orphan_risk(text: str) -> bool:
        """Determines if a paragraph, bullet, or heading has an orphan wrap risk.
        
        Risk triggers:
        1. English text ending with a space and a single trailing word (e.g. 'Engineering').
        2. Chinese text ending with a single character after a space, punctuation, or short tail.
        3. Presence of multi-word fragile noun phrases without non-breaking binds.
        """
        clean = re.sub(r"<[^>]+>", "", text).strip()
        if not clean:
            return False

        # Check fragile phrase unbound occurrence
        for pat, _ in FRAGILE_NOUN_PHRASES:
            if pat.search(clean) and "&nbsp;" not in clean:
                return True

        # Check English trailing orphan: space + single word (<= 14 chars) at end
        en_trailing = re.search(r"\s+([A-Za-z0-9_-]{1,16})[.,;:!?]?$", clean)
        if en_trailing and len(clean) > 20:
            return True

        # Check Chinese trailing orphan: space or punctuation + single char at end
        cn_trailing = re.search(r"[\s，、；](\S)[。！？]?$", clean)
        if cn_trailing and len(clean) > 10:
            return True

        return False

    @staticmethod
    def bind_fragile_phrases(text: str) -> Tuple[str, int]:
        """Replaces spaces in fragile technical phrases with &nbsp;."""
        count = 0
        res = text
        for pat, repl in FRAGILE_NOUN_PHRASES:
            matches = list(pat.finditer(res))
            if matches:
                res, n = pat.subn(repl, res)
                count += n
        return res, count

    @staticmethod
    def bind_trailing_orphan(text: str) -> Tuple[str, int]:
        """Replaces the final whitespace before the last word/character with &nbsp;."""
        # English / mixed trailing word: replaces the last whitespace before the final token
        trailing_en_pat = re.compile(r"(\s+)([A-Za-z0-9_-]+[.,;:!?]?\s*)$")
        if trailing_en_pat.search(text):
            new_text, n = trailing_en_pat.subn(r"&nbsp;\2", text)
            if n > 0:
                return new_text, n

        # Chinese trailing single character preceded by space
        trailing_cn_pat = re.compile(r"(\s+)([\u4e00-\u9fff][。！？]?\s*)$")
        if trailing_cn_pat.search(text):
            new_text, n = trailing_cn_pat.subn(r"&nbsp;\2", text)
            if n > 0:
                return new_text, n

        return text, 0

    @classmethod
    def mitigate_html_text_content(cls, html: str) -> Tuple[str, int]:
        """Safely mitigates orphans inside text nodes of HTML without corrupting tags."""
        # Protect <style> and <script> blocks
        protected_blocks: Dict[str, str] = {}
        block_counter = 0

        def _stash(m: re.Match) -> str:
            nonlocal block_counter
            key = f"___PROTECTED_STYLE_SCRIPT_{block_counter}___"
            block_counter += 1
            protected_blocks[key] = m.group(0)
            return key

        stashed = re.sub(r"(<style\b[^>]*>[\s\S]*?</style>)", _stash, html, flags=re.IGNORECASE)
        stashed = re.sub(r"(<script\b[^>]*>[\s\S]*?</script>)", _stash, stashed, flags=re.IGNORECASE)

        total_mitigated = 0

        # 1. Bind fragile phrases across all text nodes (outside tags)
        parts = re.split(r"(<[^>]+>)", stashed)
        for i in range(0, len(parts), 2):
            if parts[i]:
                bound_txt, n_bound = cls.bind_fragile_phrases(parts[i])
                if n_bound > 0:
                    parts[i] = bound_txt
                    total_mitigated += n_bound
        stashed = "".join(parts)

        # 2. Process block elements for trailing orphan mitigation on leaf nodes
        block_tags_pat = re.compile(
            r"(<(?:li|p|h1|h2|h3|h4|h5|h6|td|div)\b[^>]*>)"
            r"([\s\S]*?)"
            r"(</(?:li|p|h1|h2|h3|h4|h5|h6|td|div)>)",
            re.IGNORECASE,
        )

        def _process_block(m: re.Match) -> str:
            nonlocal total_mitigated
            start_tag, content, end_tag = m.group(1), m.group(2), m.group(3)

            # Avoid double-processing if content contains nested block tags
            if re.search(r"<(?:li|p|h1|h2|h3|h4|h5|h6|td|div)\b", content, re.IGNORECASE):
                return m.group(0)

            clean_text = re.sub(r"<[^>]+>", "", content).strip()
            # Only apply trailing orphan binding to blocks long enough to wrap across multiple lines
            words = clean_text.split()
            if len(clean_text) >= 24 and len(words) >= 4:
                sub_parts = re.split(r"(<[^>]+>)", content)
                for i in range(len(sub_parts) - 1, -1, -2):
                    if sub_parts[i].strip():
                        bound_tail, n_tail = cls.bind_trailing_orphan(sub_parts[i])
                        if n_tail > 0:
                            sub_parts[i] = bound_tail
                            total_mitigated += n_tail
                        break
                return f"{start_tag}{''.join(sub_parts)}{end_tag}"

            return m.group(0)

        processed = block_tags_pat.sub(_process_block, stashed)

        # Restore style and script blocks
        for key, val in protected_blocks.items():
            processed = processed.replace(key, val)

        return processed, total_mitigated


# ==============================================================================
# 2. Adaptive Coursework & Term Preservation Guardian
# ==============================================================================

# Dictionary of forbidden/destructive abbreviations and their academic full titles
FORBIDDEN_ABBREVIATIONS: Dict[re.Pattern, str] = {
    re.compile(r"\bMath(?:\.|\s+)Stats\b\.?", re.IGNORECASE): "Probability and Mathematical Statistics",
    re.compile(r"\bCivil\s+Eng\b\.?", re.IGNORECASE): "Civil Engineering",
    re.compile(r"\bEcon\b\.?", re.IGNORECASE): "Economics",
    re.compile(r"\bComp\s+Sci\b\.?", re.IGNORECASE): "Computer Science",
    re.compile(r"\bProj\s+Mgmt\b\.?", re.IGNORECASE): "Project Management",
    re.compile(r"\bAlgo\b\.?", re.IGNORECASE): "Algorithms",
    re.compile(r"\bAdv\s+Algo\b\.?", re.IGNORECASE): "Advanced Algorithms",
}


class CourseworkGridAdapter:
    """Manages adaptive flow grids and strict terminology integrity for coursework & skills."""

    @classmethod
    def restore_abbreviations(cls, text: str) -> Tuple[str, List[str]]:
        """Restores crudely abbreviated academic and industry terms to their full titles."""
        prevented: List[str] = []
        result = text
        for pat, full_term in FORBIDDEN_ABBREVIATIONS.items():
            matches = list(pat.finditer(result))
            if matches:
                for m in matches:
                    prevented.append(f"Restored '{m.group(0)}' -> '{full_term}'")
                result = pat.sub(full_term, result)
        return result, prevented

    @classmethod
    def format_adaptive_coursework_grid(
        cls,
        courses: Union[List[str], str],
        max_width_px: float = A4_WIDTH_PX,
    ) -> str:
        """Generates an adaptive 2-column or flow grid supporting full multi-line titles.
        
        Refuses single-line truncation or ugly squeezing into 3/4 columns when titles are long.
        """
        if isinstance(courses, str):
            # Split by comma, semicolon, bullet, or Chinese punctuation
            raw_items = re.split(r"[,;，；|｜·•]\s*", courses.strip())
        else:
            raw_items = list(courses)

        clean_items = [c.strip() for c in raw_items if c.strip()]
        if not clean_items:
            return ""

        # Analyze item lengths
        max_char_len = max(len(c) for c in clean_items)
        avg_char_len = sum(len(c) for c in clean_items) / len(clean_items)

        # If courses contain long titles (> 20 chars), use balanced 2-column grid
        # allowing 2 natural lines instead of forcing 3 columns and abbreviating!
        if max_char_len > 20 or avg_char_len > 16:
            col_spec = "repeat(2, 1fr)"
        else:
            col_spec = "repeat(3, 1fr)"

        item_spans = []
        for c in clean_items:
            # Bind fragile phrases within course title
            bound, _ = OrphanWidowMitigator.bind_fragile_phrases(c)
            bound, _ = OrphanWidowMitigator.bind_trailing_orphan(bound)
            item_spans.append(
                f'<div class="adaptive-coursework-item" style="white-space:normal; word-break:break-word; line-height:1.36;">'
                f'<span style="color:var(--color-accent, #1e3a8a); font-weight:bold; margin-right:4px;">•</span>{bound}'
                f'</div>'
            )

        html_grid = (
            f'<div class="adaptive-coursework-container" style="display:grid; grid-template-columns:{col_spec}; gap:3pt 10pt; line-height:1.36; margin-top:3pt;">\n'
            f'  {"".join(item_spans)}\n'
            f'</div>'
        )
        return html_grid

    @classmethod
    def adapt_coursework_in_html(cls, html: str, config: LayoutConfig) -> Tuple[str, List[str]]:
        """Scans HTML for coursework blocks, restores forbidden abbreviations, and injects adaptive flow grid."""
        all_prevented: List[str] = []

        # 1. Restore forbidden abbreviations globally across the HTML
        if not config.allow_term_abbreviation:
            html, prevented = cls.restore_abbreviations(html)
            all_prevented.extend(prevented)

        # 2. Look for coursework containers like:
        # <b>核心课程：</b>... or <b>Key Coursework:</b>...
        coursework_pat = re.compile(
            r'(<div[^>]*>\s*<b[^>]*>(?:核心课程|Key\s+Coursework)[：:]</b>\s*)([\s\S]*?)(</div>)',
            re.IGNORECASE,
        )

        def _replace_coursework(m: re.Match) -> str:
            prefix, courses_text, suffix = m.group(1), m.group(2), m.group(3)
            # Remove any residual HTML inside courses_text
            clean_text = re.sub(r"<[^>]+>", "", courses_text).strip()
            if clean_text:
                grid_html = cls.format_adaptive_coursework_grid(clean_text, max_width_px=config.a4_width_px)
                return f"{prefix}\n{grid_html}\n{suffix}"
            return m.group(0)

        html = coursework_pat.sub(_replace_coursework, html)
        return html, all_prevented


# ==============================================================================
# 3. Springs & Glue Vertical Budgeting (仿 TeX \\vskip)
# ==============================================================================

class SpringsGlueBudgeter:
    """TeX \\vskip style elastic vertical space allocator.
    
    Systematically reclaims vertical height along an elastic priority ladder:
    1. Section margins (14pt down to 10pt)
    2. Item gaps (6pt down to 4pt)
    3. Page padding Y (8.5mm down to 6.0mm)
    4. Paragraph line height (1.45 down to 1.35)
    5. Micro letter/word spacing (-0.005em down to -0.015em)
    6. Body font size (LAST RESORT! Strictly clamped to min_body_font_pt >= 9.5pt)
    """

    @classmethod
    def solve_budget(
        cls,
        overflow_px: float,
        config: LayoutConfig,
        num_sections: int = 5,
        num_items: int = 15,
        num_lines: int = 50,
    ) -> Dict[str, Any]:
        """Calculates exact elastic values for all layout parameters."""
        remaining_overflow = max(0.0, float(overflow_px))
        applied_compressions: List[str] = []

        # Initialize to target values
        sec_margin_pt = config.target_section_margin_pt
        item_gap_pt = config.target_item_gap_pt
        page_padding_y_mm = config.target_page_padding_y_mm
        line_height = config.target_line_height
        letter_spacing_em = config.target_letter_spacing_em
        word_spacing_em = config.target_word_spacing_em
        body_font_pt = config.target_body_font_pt

        # Multi-page (2-Page) decision:
        # Activated when explicitly set to "2"
        is_two_page = config.page_mode == "2"
        if is_two_page:
            applied_notes = [
                f"Multi-Page (2-Page) Layout Activated: Content volume "
                f"expanded to 2-page budget. Typography maintained at comfortable "
                f"{config.target_body_font_pt}pt with print break avoidance across 2 pages."
            ]
            return {
                "solved": True,
                "body_font_pt": config.target_body_font_pt,
                "line_height": config.target_line_height,
                "section_margin_pt": config.target_section_margin_pt,
                "item_gap_pt": config.target_item_gap_pt,
                "page_padding_y_mm": config.target_page_padding_y_mm,
                "letter_spacing_em": config.target_letter_spacing_em,
                "word_spacing_em": config.target_word_spacing_em,
                "overflow_px_remaining": 0.0,
                "applied_compressions": applied_notes,
                "is_expanded_to_fill": False,
                "requires_page_expansion_prompt": False,
                "page_expansion_prompt_message": None,
                "target_pages_solved": 2,
            }

        # Underflow handling: expand springs to gracefully fill the A4 page without white void
        if overflow_px < -5.0:
            underflow_px = abs(float(overflow_px))
            applied_expansions: List[str] = []

            # Underflow Stage 1: Expand section margins (target -> max)
            sec_expand_pt = config.max_section_margin_pt - config.target_section_margin_pt
            sec_exp_cap = sec_expand_pt * PT_TO_PX * max(1, num_sections)
            if sec_exp_cap > 0 and underflow_px > 0:
                allocated = min(underflow_px, sec_exp_cap)
                sec_margin_pt += allocated / (PT_TO_PX * max(1, num_sections))
                underflow_px -= allocated
                applied_expansions.append(f"Underflow Stage 1 Section Margins: Expanded to {sec_margin_pt:.2f}pt")

            # Underflow Stage 2: Expand item gaps (target -> max)
            item_expand_pt = config.max_item_gap_pt - config.target_item_gap_pt
            item_exp_cap = item_expand_pt * PT_TO_PX * max(1, num_items)
            if item_exp_cap > 0 and underflow_px > 0:
                allocated = min(underflow_px, item_exp_cap)
                item_gap_pt += allocated / (PT_TO_PX * max(1, num_items))
                underflow_px -= allocated
                applied_expansions.append(f"Underflow Stage 2 Item Gaps: Expanded to {item_gap_pt:.2f}pt")

            # Underflow Stage 3: Expand line height (target -> max)
            lh_expand = config.max_line_height - config.target_line_height
            lh_exp_cap = lh_expand * (body_font_pt * PT_TO_PX) * max(1, num_lines)
            if lh_exp_cap > 0 and underflow_px > 0:
                allocated = min(underflow_px, lh_exp_cap)
                line_height += allocated / ((body_font_pt * PT_TO_PX) * max(1, num_lines))
                underflow_px -= allocated
                applied_expansions.append(f"Underflow Stage 3 Line Height: Expanded to {line_height:.3f}")

            # Underflow Stage 4: Expand page padding Y (target -> max)
            pad_expand_mm = config.max_page_padding_y_mm - config.target_page_padding_y_mm
            pad_exp_cap = pad_expand_mm * 2 * MM_TO_PX
            if pad_exp_cap > 0 and underflow_px > 0:
                allocated = min(underflow_px, pad_exp_cap)
                page_padding_y_mm += allocated / (2 * MM_TO_PX)
                underflow_px -= allocated
                applied_expansions.append(f"Underflow Stage 4 Page Padding: Expanded to {page_padding_y_mm:.2f}mm")

            # Underflow Stage 5: Expand body font size (target -> max)
            font_expand_pt = config.max_body_font_pt - config.target_body_font_pt
            font_exp_cap = font_expand_pt * PT_TO_PX * max(1, num_lines) * line_height
            if font_exp_cap > 0 and underflow_px > 0:
                allocated = min(underflow_px, font_exp_cap)
                body_font_pt += allocated / (PT_TO_PX * max(1, num_lines) * line_height)
                underflow_px -= allocated
                applied_expansions.append(f"Underflow Stage 5 Font Size: Expanded to {body_font_pt:.2f}pt")

            return {
                "solved": True,
                "body_font_pt": round(body_font_pt, 2),
                "line_height": round(line_height, 3),
                "section_margin_pt": round(sec_margin_pt, 2),
                "item_gap_pt": round(item_gap_pt, 2),
                "page_padding_y_mm": round(page_padding_y_mm, 2),
                "letter_spacing_em": round(letter_spacing_em, 3),
                "word_spacing_em": round(word_spacing_em, 3),
                "overflow_px_remaining": -round(underflow_px, 2),
                "applied_compressions": applied_expansions,
                "is_expanded_to_fill": True,
                "requires_page_expansion_prompt": False,
                "page_expansion_prompt_message": None,
                "target_pages_solved": 1,
            }

        if remaining_overflow <= 0:
            return {
                "solved": True,
                "body_font_pt": body_font_pt,
                "line_height": line_height,
                "section_margin_pt": sec_margin_pt,
                "item_gap_pt": item_gap_pt,
                "page_padding_y_mm": page_padding_y_mm,
                "letter_spacing_em": letter_spacing_em,
                "word_spacing_em": word_spacing_em,
                "overflow_px_remaining": 0.0,
                "applied_compressions": ["Zero overflow: all parameters maintained at ideal targets."],
                "is_expanded_to_fill": False,
                "requires_page_expansion_prompt": False,
                "page_expansion_prompt_message": None,
                "target_pages_solved": 1,
            }

        # Stage 1: Section Margins (target: 14pt -> min: 10pt)
        sec_shrink_pt = config.target_section_margin_pt - config.min_section_margin_pt
        sec_capacity_px = sec_shrink_pt * PT_TO_PX * max(1, num_sections)
        if sec_capacity_px > 0 and remaining_overflow > 0:
            if remaining_overflow <= sec_capacity_px:
                reclaimed = remaining_overflow
                sec_margin_pt -= reclaimed / (PT_TO_PX * max(1, num_sections))
                remaining_overflow = 0.0
                applied_compressions.append(
                    f"Stage 1 Section Margins: Compressed to {sec_margin_pt:.2f}pt (absorbed {reclaimed:.1f}px)"
                )
            else:
                reclaimed = sec_capacity_px
                sec_margin_pt = config.min_section_margin_pt
                remaining_overflow -= reclaimed
                applied_compressions.append(
                    f"Stage 1 Section Margins: Max compressed to min {sec_margin_pt:.2f}pt (absorbed {reclaimed:.1f}px)"
                )

        # Stage 2: Item Gaps (target: 6pt -> min: 4pt)
        item_shrink_pt = config.target_item_gap_pt - config.min_item_gap_pt
        item_capacity_px = item_shrink_pt * PT_TO_PX * max(1, num_items)
        if item_capacity_px > 0 and remaining_overflow > 0:
            if remaining_overflow <= item_capacity_px:
                reclaimed = remaining_overflow
                item_gap_pt -= reclaimed / (PT_TO_PX * max(1, num_items))
                remaining_overflow = 0.0
                applied_compressions.append(
                    f"Stage 2 Item Gaps: Compressed to {item_gap_pt:.2f}pt (absorbed {reclaimed:.1f}px)"
                )
            else:
                reclaimed = item_capacity_px
                item_gap_pt = config.min_item_gap_pt
                remaining_overflow -= reclaimed
                applied_compressions.append(
                    f"Stage 2 Item Gaps: Max compressed to min {item_gap_pt:.2f}pt (absorbed {reclaimed:.1f}px)"
                )

        # Stage 3: Page Vertical Padding (target: 8.5mm -> min: 6.0mm)
        pad_shrink_mm = config.target_page_padding_y_mm - config.min_page_padding_y_mm
        pad_capacity_px = pad_shrink_mm * 2 * MM_TO_PX
        if pad_capacity_px > 0 and remaining_overflow > 0:
            if remaining_overflow <= pad_capacity_px:
                reclaimed = remaining_overflow
                page_padding_y_mm -= reclaimed / (2 * MM_TO_PX)
                remaining_overflow = 0.0
                applied_compressions.append(
                    f"Stage 3 Page Padding: Compressed to {page_padding_y_mm:.2f}mm (absorbed {reclaimed:.1f}px)"
                )
            else:
                reclaimed = pad_capacity_px
                page_padding_y_mm = config.min_page_padding_y_mm
                remaining_overflow -= reclaimed
                applied_compressions.append(
                    f"Stage 3 Page Padding: Max compressed to min {page_padding_y_mm:.2f}mm (absorbed {reclaimed:.1f}px)"
                )

        # Stage 4: Line Height (target: 1.45 -> min: 1.35)
        lh_shrink = config.target_line_height - config.min_line_height
        lh_capacity_px = lh_shrink * (body_font_pt * PT_TO_PX) * max(1, num_lines)
        if lh_capacity_px > 0 and remaining_overflow > 0:
            if remaining_overflow <= lh_capacity_px:
                reclaimed = remaining_overflow
                line_height -= reclaimed / ((body_font_pt * PT_TO_PX) * max(1, num_lines))
                remaining_overflow = 0.0
                applied_compressions.append(
                    f"Stage 4 Line Height: Compressed to {line_height:.3f} (absorbed {reclaimed:.1f}px)"
                )
            else:
                reclaimed = lh_capacity_px
                line_height = config.min_line_height
                remaining_overflow -= reclaimed
                applied_compressions.append(
                    f"Stage 4 Line Height: Max compressed to min {line_height:.3f} (absorbed {reclaimed:.1f}px)"
                )

        # Stage 5: Micro Letter Spacing (-0.005em -> -0.015em)
        ls_shrink = abs(config.letter_spacing_min_em - config.target_letter_spacing_em)
        ls_capacity_px = 16.0  # Empirical height absorption across ~50 wrapped lines
        if ls_capacity_px > 0 and remaining_overflow > 0:
            if remaining_overflow <= ls_capacity_px:
                reclaimed = remaining_overflow
                ratio = reclaimed / ls_capacity_px
                letter_spacing_em = config.target_letter_spacing_em - ratio * ls_shrink
                word_spacing_em = config.target_word_spacing_em - ratio * abs(config.word_spacing_min_em)
                remaining_overflow = 0.0
                applied_compressions.append(
                    f"Stage 5 Micro-spacing: Tuned letter-spacing to {letter_spacing_em:.3f}em (absorbed {reclaimed:.1f}px)"
                )
            else:
                reclaimed = ls_capacity_px
                letter_spacing_em = config.letter_spacing_min_em
                word_spacing_em = config.word_spacing_min_em
                remaining_overflow -= reclaimed
                applied_compressions.append(
                    f"Stage 5 Micro-spacing: Max compressed to min {letter_spacing_em:.3f}em (absorbed {reclaimed:.1f}px)"
                )

        # Stage 6: Body Font Size (LAST RESORT! STRICT FLOOR: min_body_font_pt = 9.5pt)
        font_shrink_pt = config.target_body_font_pt - config.min_body_font_pt
        font_capacity_px = font_shrink_pt * PT_TO_PX * max(1, num_lines) * line_height
        if remaining_overflow > 0 and font_shrink_pt > 0:
            if remaining_overflow <= font_capacity_px:
                reclaimed = remaining_overflow
                body_font_pt -= reclaimed / (PT_TO_PX * max(1, num_lines) * line_height)
                remaining_overflow = 0.0
                applied_compressions.append(
                    f"Stage 6 Font Size: Slightly compressed to {body_font_pt:.2f}pt (absorbed {reclaimed:.1f}px)"
                )
            else:
                reclaimed = font_capacity_px
                body_font_pt = config.min_body_font_pt  # HARD FLOOR: 9.5pt!
                remaining_overflow -= reclaimed
                applied_compressions.append(
                    f"Stage 6 Font Size: Reached absolute floor {body_font_pt:.2f}pt (absorbed {reclaimed:.1f}px)"
                )

        # Strict baseline assertion
        body_font_pt = max(config.min_body_font_pt, body_font_pt)
        solved = (remaining_overflow <= 1e-3)

        # Multi-page transition for "auto" mode when single-page capacity is exhausted
        if not solved and config.page_mode == "auto":
            applied_compressions.append(
                f"Auto Multi-Page Activated: Content volume ({overflow_px:.1f}px overflow) exceeded single-page "
                f"capacity at {config.min_body_font_pt}pt floor. Automatically transitioned to balanced "
                f"2-page layout with comfortable {config.target_body_font_pt}pt typography and print break protection."
            )
            return {
                "solved": True,
                "body_font_pt": config.target_body_font_pt,
                "line_height": config.target_line_height,
                "section_margin_pt": config.target_section_margin_pt,
                "item_gap_pt": config.target_item_gap_pt,
                "page_padding_y_mm": config.target_page_padding_y_mm,
                "letter_spacing_em": config.target_letter_spacing_em,
                "word_spacing_em": config.target_word_spacing_em,
                "overflow_px_remaining": 0.0,
                "applied_compressions": applied_compressions,
                "is_expanded_to_fill": False,
                "requires_page_expansion_prompt": False,
                "page_expansion_prompt_message": None,
                "target_pages_solved": 2,
            }

        requires_prompt = not solved
        prompt_msg = (
            f"当前简历内容量超出单页优质排版极限（剩余溢出 {remaining_overflow:.1f}px）。"
            f"正文字号已达 {config.min_body_font_pt}pt 最低底线，是否为您扩展为双页排版？"
            if requires_prompt else None
        )
        if requires_prompt:
            applied_compressions.append(f"Overflow Limit Reached: {prompt_msg}")

        return {
            "solved": solved,
            "body_font_pt": round(body_font_pt, 2),
            "line_height": round(line_height, 3),
            "section_margin_pt": round(sec_margin_pt, 2),
            "item_gap_pt": round(item_gap_pt, 2),
            "page_padding_y_mm": round(page_padding_y_mm, 2),
            "letter_spacing_em": round(letter_spacing_em, 3),
            "word_spacing_em": round(word_spacing_em, 3),
            "overflow_px_remaining": round(remaining_overflow, 2),
            "applied_compressions": applied_compressions,
            "is_expanded_to_fill": False,
            "requires_page_expansion_prompt": requires_prompt,
            "page_expansion_prompt_message": prompt_msg,
            "target_pages_solved": 1,
        }


# ==============================================================================
# 4. Core Exported APIs
# ==============================================================================

def generate_micro_typography_css(
    config: LayoutConfig,
    solved_params: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates production-grade CSS rules incorporating micro-typography and layout solving tokens."""
    params = solved_params or {}
    font_pt = params.get("body_font_pt", config.target_body_font_pt)
    lh = params.get("line_height", config.target_line_height)
    sec_pt = params.get("section_margin_pt", config.target_section_margin_pt)
    gap_pt = params.get("item_gap_pt", config.target_item_gap_pt)
    pad_mm = params.get("page_padding_y_mm", config.target_page_padding_y_mm)
    ls_em = params.get("letter_spacing_em", config.target_letter_spacing_em)
    ws_em = params.get("word_spacing_em", config.target_word_spacing_em)

    css = f"""<style id="offerget-micro-typography">
  /* OfferGet Adaptive Layout Solver & Micro-typography Engine */
  :root {{
    --body-font-size: {font_pt}pt;
    --body-line-height: {lh};
    --section-gap: {sec_pt}pt;
    --item-gap: {gap_pt}pt;
    --page-padding-y: {pad_mm}mm;
    --micro-letter-spacing: {ls_em}em;
    --micro-word-spacing: {ws_em}em;
  }}

  @page {{
    size: A4 portrait;
    margin-top: {pad_mm}mm;
    margin-bottom: {pad_mm}mm;
    margin-left: 0;
    margin-right: 0;
  }}

  body {{
    font-size: var(--body-font-size, {font_pt}pt) !important;
    line-height: var(--body-line-height, {lh}) !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
    font-feature-settings: "kern" 1, "palt" 1;
  }}

  @media print {{
    h1, h2, h3, .section-header, .item-header, .org-bar {{
      break-after: avoid !important;
      page-break-after: avoid !important;
    }}
    .org-bar, .experience-item, .project-item, .publication-item, ul, li {{
      break-inside: avoid !important;
      page-break-inside: avoid !important;
    }}
    .page {{
      min-height: calc(297mm - {pad_mm * 2:.1f}mm) !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      box-shadow: none !important;
      margin: 0 !important;
    }}
  }}

  .org-right, .time, .date, .entry-date, .resume-contacts, .contacts {{
    white-space: nowrap !important;
    font-size: calc(var(--body-font-size, {font_pt}pt) * 0.9) !important;
  }}

  .resume-contacts span, .resume-contacts a {{
    font-size: calc(var(--body-font-size, {font_pt}pt) * 0.9) !important;
  }}

  h1, h2, h3, .section-header, .item-header {{
    text-wrap: balance;
  }}

  h2, .section-header {{
    margin-top: var(--section-gap, {sec_pt}pt) !important;
  }}

  p, li, .bullet-item {{
    font-size: var(--body-font-size, {font_pt}pt) !important;
    line-height: var(--body-line-height, {lh}) !important;
    letter-spacing: var(--micro-letter-spacing, {ls_em}em);
    word-spacing: var(--micro-word-spacing, {ws_em}em);
    text-wrap: pretty;
    orphans: 2;
    widows: 2;
  }}

  li {{
    margin-bottom: var(--item-gap, {gap_pt}pt) !important;
  }}

  /* Adaptive Flow Grid for Coursework & Certs */
  .adaptive-coursework-container {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 3pt 10pt;
    margin-top: 2.5pt;
    line-height: 1.35;
  }}

  .adaptive-coursework-item {{
    white-space: normal !important;
    word-break: break-word;
    hyphens: auto;
  }}

  .nobr {{
    white-space: nowrap !important;
  }}
</style>"""
    return css


def solve_layout(
    html_content: str,
    overflow_px: float = 0.0,
    config: Optional[LayoutConfig] = None,
) -> LayoutSolveResult:
    """DOM/AST level adaptive layout solver.
    
    1. Runs TeX springs & glue vertical budgeting against overflow_px.
    2. Mitigates orphans and widows in HTML text nodes (&nbsp; binding + CSS text-wrap).
    3. Guarantees coursework & term preservation without destructive abbreviations.
    4. Enforces strict body font baseline (body_font_pt >= 9.5pt).
    5. Injects solved micro-typography style block into HTML.
    """
    cfg = config or LayoutConfig()

    # Estimate structural counts from HTML
    n_sections = max(3, len(re.findall(r"<(?:h2|section\b)", html_content, re.IGNORECASE)))
    n_items = max(8, len(re.findall(r"<(?:li|div\s+class=['\"][^'\"]*item-header)", html_content, re.IGNORECASE)))
    n_lines = max(25, int(len(re.sub(r"<[^>]+>", "", html_content)) / 45))

    # 1. Solve vertical budgeting
    budget = SpringsGlueBudgeter.solve_budget(
        overflow_px=overflow_px,
        config=cfg,
        num_sections=n_sections,
        num_items=n_items,
        num_lines=n_lines,
    )

    # 2. Prevent abbreviations and adapt coursework
    processed_html = html_content
    abbreviations_prevented: List[str] = []
    if cfg.enable_adaptive_grid:
        processed_html, abbreviations_prevented = CourseworkGridAdapter.adapt_coursework_in_html(
            processed_html, cfg
        )

    # 3. Mitigate orphans and widows
    orphans_count = 0
    if cfg.enable_widow_orphan_mitigation:
        processed_html, orphans_count = OrphanWidowMitigator.mitigate_html_text_content(processed_html)

    # 4. Generate and inject CSS
    css_rules = generate_micro_typography_css(cfg, budget)
    if '<style id="offerget-micro-typography">' in processed_html:
        # Replace existing override block
        processed_html = re.sub(
            r'<style id="offerget-micro-typography">[\s\S]*?</style>',
            css_rules,
            processed_html,
        )
    elif "</head>" in processed_html:
        processed_html = processed_html.replace("</head>", f"{css_rules}\n</head>")
    else:
        processed_html = f"{css_rules}\n{processed_html}"

    return LayoutSolveResult(
        solved=budget["solved"],
        body_font_pt=budget["body_font_pt"],
        line_height=budget["line_height"],
        section_margin_pt=budget["section_margin_pt"],
        item_gap_pt=budget["item_gap_pt"],
        page_padding_y_mm=budget["page_padding_y_mm"],
        letter_spacing_em=budget["letter_spacing_em"],
        word_spacing_em=budget["word_spacing_em"],
        initial_overflow_px=float(overflow_px),
        overflow_px_remaining=budget["overflow_px_remaining"],
        applied_compressions=budget["applied_compressions"],
        abbreviations_prevented=abbreviations_prevented,
        orphans_mitigated=orphans_count,
        css_rules=css_rules,
        html=processed_html,
        is_expanded_to_fill=budget.get("is_expanded_to_fill", False),
        requires_page_expansion_prompt=budget.get("requires_page_expansion_prompt", False),
        page_expansion_prompt_message=budget.get("page_expansion_prompt_message", None),
        target_pages_solved=budget.get("target_pages_solved", 1),
    )


def inject_micro_typography(
    html_content: str,
    config: Optional[LayoutConfig] = None,
) -> str:
    """Convenience helper to inject micro-typography and orphan mitigation into HTML."""
    res = solve_layout(html_content, overflow_px=0.0, config=config)
    return res.html
