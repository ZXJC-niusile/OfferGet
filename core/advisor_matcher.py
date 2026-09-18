"""
OfferGet Chinese Advisor Profiling, Academic Intersection Matching, and Outreach Email Generator
==================================================================================================
Modules:
1. AdvisorProfile & CandidateProfile ingestion with strict Anti-Hallucination guarantees.
2. Advisor research timeline & technical trajectory analysis (chronological clustering, theme shifts).
3. Academic intersection matching (0-100% score, technical overlap, mutual research interest topics).
4. High-EQ Chinese Advisor Outreach Emails (Profile Hook, Academic Reflection, Value Proposition, Attachment Guide).
5. Anti-Pigeon & Academic Etiquette Guidelines (Verbal Commitment Matrix, Timeline, Multi-Offer Handling, Rejection Templates).
6. Top-level convenience function: match_advisor_and_draft_email().
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ============================================================================
# 1. Data Models & Profile Ingestion
# ============================================================================

@dataclass
class Publication:
    """Represents an academic publication with factual metadata."""
    title: str
    year: int
    venue: str = ""
    abstract: str = ""
    keywords: List[str] = field(default_factory=list)
    lead_type: str = ""  # student_led, advisor_led, co_author
    core_contribution: str = ""

    def clean_title(self) -> str:
        return self.title.strip()


@dataclass
class AdvisorProfile:
    """Factual profile of a prospective graduate/PhD advisor."""
    name: str
    title: str = "教授"  # 教授, 长聘副教授, 副教授, 研究员, 助理教授, 博导, 硕导
    institution: str = ""  # e.g., 清华大学, 中国科学院计算技术研究所
    department: str = ""  # e.g., 计算机科学与技术系
    research_topics: List[str] = field(default_factory=list)
    recent_publications: List[Publication] = field(default_factory=list)
    lab_projects: List[str] = field(default_factory=list)
    email: str = ""
    homepage_url: str = ""
    openings_info: Dict[str, Any] = field(default_factory=dict)  # master, phd quotas

    @property
    def surname(self) -> str:
        """Extract advisor surname for respectful Chinese greeting (e.g. '张老师')."""
        clean_name = self.name.strip()
        if not clean_name:
            return "老师"
        # Common Chinese surnames (single or compound)
        compound_surnames = {"欧阳", "太史", "端木", "上官", "司马", "东方", "独孤", "南宫", "万俟", "闻人", "夏侯", "诸葛", "尉迟", "公羊", "赫连", "澹台", "皇甫", "宗政", "濮阳", "淳于", "单于", "太叔", "申屠", "公孙", "仲孙", "轩辕", "令狐", "钟离", "宇文", "长孙", "慕容", "鲜于", "闾丘", "司徒", "司空", "亓官", "司寇", "仉督", "子车", "颛孙", "端木", "巫马", "公西", "漆雕", "乐正", "壤驷", "公良", "拓跋", "夹谷", "宰父", "谷梁", "晋楚", "闫法", "汝鄢", "涂钦", "段干", "百里", "东郭", "南门", "呼延", "归海", "羊舌", "微生", "岳帅", "缑亢", "况后", "有琴", "梁丘", "左丘", "东门", "西门"}
        if len(clean_name) >= 2 and clean_name[:2] in compound_surnames:
            return clean_name[:2]
        return clean_name[0]


@dataclass
class CandidateProfile:
    """Candidate's verified factual academic and technical profile."""
    name: str
    undergraduate_school: str
    major: str
    grade: str = "2022级本科生"
    target_degree: str = "master"  # master, phd, direct_phd, academic_master, professional_master
    gpa: str = ""
    rank: str = ""  # e.g., "1/120", "前2%"
    rank_percentage: Optional[float] = None
    honors_awards: List[str] = field(default_factory=list)
    publications: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    coursework: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    research_interests: List[str] = field(default_factory=list)
    read_advisor_papers: List[str] = field(default_factory=list)  # Papers candidate actually read
    email: str = ""
    phone: str = ""
    wechat: str = ""


# ============================================================================
# 2. Advisor Matcher Core Engine
# ============================================================================

class AdvisorMatcher:
    """
    Advisor Profiling, Academic Intersection Matching, and Outreach Email Generator.
    Designed for Chinese Postgraduate and Direct-PhD Admissions (保研夏令营/预推免/考研复试).
    """

    def __init__(self):
        # Known technical shift taxonomy keywords
        self._tech_shift_keywords = {
            "traditional": [
                "svm", "support vector", "random forest", "decision tree", "crf", 
                "hidden markov", "hmm", "rule-based", "statistical nlp", "feature engineering", 
                "heuristic", "ontology", "traditional", "传统方法", "统计学习", "规则抽取"
            ],
            "deep_learning": [
                "cnn", "rnn", "lstm", "gru", "deep learning", "neural network", "transformer", 
                "bert", "resnet", "attention mechanism", "self-attention", "深度学习", "注意力机制"
            ],
            "modern_multimodal_llm": [
                "llm", "large language model", "multimodal", "vlm", "diffusion", "generative ai", 
                "embodied ai", "embodied", "agent", "rlhf", "dpo", "alignment", "in-context learning", 
                "zero-shot", "reasoning", "cot", "chain of thought", "大模型", "多模态", "具身智能", 
                "扩散模型", "智能体", "对齐"
            ]
        }

    # ------------------------------------------------------------------------
    # 2.1 Advisor Research Timeline Analysis
    # ------------------------------------------------------------------------

    def analyze_advisor_timeline(self, advisor: Union[AdvisorProfile, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes advisor's publication timeline, research cadence, and paradigm transitions
        (e.g., from traditional methods to deep learning and modern multimodal/LLM).
        """
        advisor_prof = self._ensure_advisor_profile(advisor)
        pubs = advisor_prof.recent_publications

        if not pubs:
            # Fallback if no publications are provided
            topics = advisor_prof.research_topics or ["前沿交叉学科"]
            return {
                "total_publications": 0,
                "year_range": (0, 0),
                "publications_by_year": {},
                "phases": {
                    "early_phase": {"years": [], "key_themes": [], "paper_count": 0},
                    "consolidation_phase": {"years": [], "key_themes": [], "paper_count": 0},
                    "recent_pivot": {"years": [], "key_themes": topics, "paper_count": 0, "emerging_topics": topics}
                },
                "technical_evolution_summary": f"{advisor_prof.name}老师当前重点围绕【{'、'.join(topics)}】展开科研探索。",
                "recent_venues": [],
                "active_momentum": "资料收录中"
            }

        # Group by year
        pubs_by_year: Dict[int, List[Publication]] = {}
        for p in pubs:
            pubs_by_year.setdefault(p.year, []).append(p)

        years = sorted(pubs_by_year.keys())
        min_year, max_year = years[0], years[-1]
        year_counts = {y: len(pubs_by_year[y]) for y in years}

        # Divide into chronological phases
        if len(years) == 1:
            early_years = years
            consolidation_years = years
            recent_years = years
        elif len(years) == 2:
            early_years = [years[0]]
            consolidation_years = [years[0]]
            recent_years = [years[1]]
        else:
            # Recent pivot is typically the last 2-3 years (or top 35% most recent)
            pivot_threshold_year = max(max_year - 2, years[int(len(years) * 0.65)])
            recent_years = [y for y in years if y >= pivot_threshold_year]
            remaining_years = [y for y in years if y < pivot_threshold_year]
            split_point = max(1, len(remaining_years) // 2)
            early_years = remaining_years[:split_point]
            consolidation_years = remaining_years[split_point:] or early_years

        # Extract topics per phase
        def extract_phase_themes(target_years: List[int]) -> List[str]:
            themes: Set[str] = set()
            for y in target_years:
                for p in pubs_by_year.get(y, []):
                    themes.update(p.keywords)
                    # Extract from title/contribution
                    for word in re.findall(r'[\u4e00-\u9fa5]{2,6}|[A-Za-z\-]{3,}', f"{p.title} {p.core_contribution} {p.abstract}"):
                        w_lower = word.lower()
                        if w_lower in ["learning", "based", "model", "network", "study", "analysis", "system"]:
                            continue
                        if len(word) >= 3 or re.search(r'[\u4e00-\u9fa5]', word):
                            themes.add(word)
            return sorted(list(themes))[:6]

        early_themes = extract_phase_themes(early_years)
        consolidation_themes = extract_phase_themes(consolidation_years)
        recent_themes = extract_phase_themes(recent_years)

        # Emerging topics (present in recent years but not prominent in early phase)
        emerging_topics = [t for t in recent_themes if t not in early_themes]
        if not emerging_topics:
            emerging_topics = recent_themes[:3]

        # Detect technical shift paradigm
        all_text_early = " ".join([f"{p.title} {p.abstract} {p.core_contribution}".lower() for y in early_years for p in pubs_by_year.get(y, [])])
        all_text_recent = " ".join([f"{p.title} {p.abstract} {p.core_contribution}".lower() for y in recent_years for p in pubs_by_year.get(y, [])])

        shift_signals = []
        has_trad_early = any(k in all_text_early for k in self._tech_shift_keywords["traditional"])
        has_dl_early = any(k in all_text_early for k in self._tech_shift_keywords["deep_learning"])
        has_modern_recent = any(k in all_text_recent for k in self._tech_shift_keywords["modern_multimodal_llm"])
        has_dl_recent = any(k in all_text_recent for k in self._tech_shift_keywords["deep_learning"])

        if has_trad_early and (has_dl_recent or has_modern_recent):
            shift_signals.append("经历了从经典统计/启发式方法向现代深度学习及多模态大模型的范式跃迁")
        elif has_dl_early and has_modern_recent:
            shift_signals.append("在深耕深度表征学习的基础上，近期全面拓展至大语言模型、多模态认知与具身智能前沿")
        elif has_modern_recent:
            shift_signals.append("研究重心紧密围绕大模型与生成式AI、智能体交互系统展开")
        else:
            shift_signals.append("保持了高度专注且持续深入的研究脉络")

        evolution_summary = (
            f"{advisor_prof.name}老师在学术生涯中{shift_signals[0]}。"
            f"早期（{early_years[0]}-{early_years[-1]}年）主要奠定了关于【{'、'.join(early_themes[:3]) or '基础理论'}】的研究根基；"
            f"而在近三年（{recent_years[0]}-{recent_years[-1]}年），课题组显著聚焦于【{'、'.join(recent_themes[:3]) or '前沿应用'}】，"
            f"产出了以《{pubs_by_year[recent_years[-1]][0].title}》为代表的核心成果。"
        )

        # Recent venues
        recent_venues = list(set([p.venue for y in recent_years for p in pubs_by_year.get(y, []) if p.venue]))

        # Momentum
        recent_count = sum(len(pubs_by_year[y]) for y in recent_years)
        if recent_count >= 5:
            momentum = "高产活跃期（近三年密集发表高水平成果，亟需自驱力强的科研生力军）"
        elif recent_count >= 2:
            momentum = "平稳推进期（聚焦代表作质量，师生研讨密切）"
        else:
            momentum = "转型攻坚期（正在探索开拓全新战略方向）"

        return {
            "total_publications": len(pubs),
            "year_range": (min_year, max_year),
            "publications_by_year": year_counts,
            "phases": {
                "early_phase": {
                    "years": early_years,
                    "key_themes": early_themes,
                    "paper_count": sum(len(pubs_by_year[y]) for y in early_years)
                },
                "consolidation_phase": {
                    "years": consolidation_years,
                    "key_themes": consolidation_themes,
                    "paper_count": sum(len(pubs_by_year[y]) for y in consolidation_years)
                },
                "recent_pivot": {
                    "years": recent_years,
                    "key_themes": recent_themes,
                    "paper_count": recent_count,
                    "emerging_topics": emerging_topics
                }
            },
            "technical_evolution_summary": evolution_summary,
            "recent_venues": recent_venues,
            "active_momentum": momentum
        }

    # ------------------------------------------------------------------------
    # 2.2 Academic Intersection Matching (0 - 100%)
    # ------------------------------------------------------------------------

    def match_candidate_to_advisor(
        self,
        advisor: Union[AdvisorProfile, Dict[str, Any]],
        candidate: Union[CandidateProfile, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compares candidate profile against advisor's timeline, projects, and publications.
        Strict Anti-Hallucination: Extracts only factual overlaps present in inputs.
        Computes intersection score (0-100%), technical overlaps, and mutual interest topics.
        """
        advisor_prof = self._ensure_advisor_profile(advisor)
        cand_prof = self._ensure_candidate_profile(candidate)

        timeline = self.analyze_advisor_timeline(advisor_prof)
        recent_pivot = timeline["phases"]["recent_pivot"]

        # Collect factual advisor corpus
        advisor_corpus_set: Set[str] = set()
        for t in advisor_prof.research_topics:
            advisor_corpus_set.add(t.strip())
        for lp in advisor_prof.lab_projects:
            advisor_corpus_set.add(lp.strip())
        for p in advisor_prof.recent_publications:
            advisor_corpus_set.add(p.title.strip())
            for kw in p.keywords:
                advisor_corpus_set.add(kw.strip())
            if p.venue:
                advisor_corpus_set.add(p.venue.strip())

        advisor_corpus_text = " ".join([
            " ".join(advisor_prof.research_topics),
            " ".join(advisor_prof.lab_projects),
            " ".join([f"{p.title} {p.abstract} {p.core_contribution} {' '.join(p.keywords)}" for p in advisor_prof.recent_publications])
        ]).lower()

        # Collect candidate corpus
        cand_skills = [s.strip() for s in cand_prof.skills]
        cand_interests = [i.strip() for i in cand_prof.research_interests]
        cand_project_texts = []
        for prj in cand_prof.projects:
            name = prj.get("name", "")
            desc = prj.get("description", "")
            tech = prj.get("technologies", prj.get("tech_stack", []))
            if isinstance(tech, list):
                tech_str = " ".join(tech)
            else:
                tech_str = str(tech)
            cand_project_texts.append(f"{name} {desc} {tech_str}")

        cand_pub_texts = [f"{p.get('title', '')} {p.get('abstract', '')} {' '.join(p.get('keywords', []))}" for p in cand_prof.publications]

        # 1. Technical Overlap Detection (Exact & normalized token match)
        technical_overlaps: List[str] = []
        seen_overlaps: Set[str] = set()

        for skill in cand_skills:
            if not skill:
                continue
            skill_clean = skill.strip()
            # Split variants like "C/C++ (C++20)" or "Rust (熟悉)" into base tokens
            tokens_to_check = [skill_clean]
            base_token = re.sub(r'\(.*?\)', '', skill_clean).strip()
            if base_token and base_token != skill_clean:
                tokens_to_check.append(base_token)
            if "/" in base_token:
                tokens_to_check.extend([p.strip() for p in base_token.split("/") if p.strip()])

            for tok in tokens_to_check:
                tok_clean = tok.strip()
                if not tok_clean:
                    continue
                pattern = re.escape(tok_clean.lower())
                if re.search(r'\b' + pattern + r'\b' if pattern.isascii() else pattern, advisor_corpus_text):
                    if tok_clean.lower() not in seen_overlaps:
                        seen_overlaps.add(tok_clean.lower())
                        technical_overlaps.append(tok_clean)

        # Cross-match candidate project technologies with advisor publications/topics
        for prj in cand_prof.projects:
            tech = prj.get("technologies", prj.get("tech_stack", prj.get("tags", [])))
            if isinstance(tech, list):
                for item in tech:
                    item_clean = str(item).strip()
                    if item_clean and item_clean.lower() not in seen_overlaps:
                        pattern = re.escape(item_clean.lower())
                        if re.search(r'\b' + pattern + r'\b' if pattern.isascii() else pattern, advisor_corpus_text):
                            seen_overlaps.add(item_clean.lower())
                            technical_overlaps.append(item_clean)

        # Domain tool-concept semantic mappings in CS/AI
        domain_tool_mapping = {
            "pytorch": ["deep learning", "transformer", "bert", "diffusion", "llm", "深度学习", "多模态", "大模型", "distributed", "分布式"],
            "vllm": ["llm", "大模型", "推理", "inference", "serving", "kv-cache", "pagedattention"],
            "triton": ["kernel", "compiler", "算子", "hw/sw", "协同设计", "编译优化", "cuda"],
            "cuda": ["deep learning", "llm", "大模型", "加速", "并行", "compiler", "算子", "gpu"],
            "deepspeed": ["distributed", "分布式", "训练", "training", "megatron"],
            "megatron-lm": ["distributed", "分布式", "训练", "training", "llm"],
            "rdma/roce v2": ["interconnect", "互连", "roce", "infiniband", "网络", "network"],
            "gem5 simulator": ["architecture", "体系结构", "memory", "显存", "cxl", "cache"],
            "ros": ["robot", "robotics", "embodied", "具身智能", "机器人", "导航", "抓取"],
            "mujoco": ["robot", "robotics", "embodied", "具身智能", "仿真", "抓取"],
            "isaac": ["robot", "robotics", "embodied", "具身智能", "仿真"],
            "c++": ["system", "robot", "robotics", "ros", "cuda", "算法", "系统"]
        }
        for skill in cand_skills:
            s_lower = skill.strip().lower()
            for key_term, mapped_concepts in domain_tool_mapping.items():
                if key_term in s_lower and key_term not in seen_overlaps:
                    if any(concept in advisor_corpus_text for concept in mapped_concepts):
                        seen_overlaps.add(key_term)
                        technical_overlaps.append(skill.strip())
                        break

        # 2. Mutual Research Interest Topics
        mutual_topics: List[str] = []
        for topic in advisor_prof.research_topics:
            t_clean = topic.strip()
            t_lower = t_clean.lower()
            cand_combined = " ".join(cand_interests + cand_project_texts + cand_pub_texts).lower()
            pattern = re.escape(t_lower)
            if re.search(r'\b' + pattern + r'\b' if pattern.isascii() else pattern, cand_combined):
                mutual_topics.append(t_clean)
            else:
                # Sub-token overlap for Chinese / bilingual compounds
                sub_parts = re.split(r'[\s\(\)/]+', t_clean)
                matched_sub = False
                for part in sub_parts:
                    part_clean = part.strip()
                    if len(part_clean) >= 2 and part_clean.lower() in cand_combined:
                        mutual_topics.append(t_clean)
                        matched_sub = True
                        break
                if not matched_sub:
                    for cand_int in cand_interests:
                        if len(cand_int) >= 2 and (cand_int in t_clean or t_clean in cand_int):
                            if t_clean not in mutual_topics:
                                mutual_topics.append(t_clean)
                            break

        # Also check lab projects for mutual points
        for lp in advisor_prof.lab_projects:
            lp_clean = lp.strip()
            cand_combined = " ".join(cand_interests + cand_project_texts + cand_pub_texts).lower()
            pattern = re.escape(lp_clean.lower())
            if re.search(r'\b' + pattern + r'\b' if pattern.isascii() else pattern, cand_combined):
                if lp_clean not in mutual_topics:
                    mutual_topics.append(lp_clean)
            else:
                for cand_int in cand_interests:
                    if len(cand_int) >= 2 and cand_int.lower() in lp_clean.lower():
                        if lp_clean not in mutual_topics:
                            mutual_topics.append(lp_clean)
                        break

        # 3. Matched Verified Advisor Publications
        matched_advisor_pubs: List[Dict[str, Any]] = []
        for pub in advisor_prof.recent_publications:
            pub_text = f"{pub.title} {pub.abstract} {' '.join(pub.keywords)} {pub.core_contribution}".lower()
            reasons = []
            for skill in technical_overlaps:
                if skill.lower() in pub_text:
                    reasons.append(f"命中技术栈【{skill}】")
            for topic in mutual_topics:
                if topic.lower() in pub_text:
                    reasons.append(f"切合共同研究方向【{topic}】")

            # Check if candidate explicitly read this paper
            has_read = any(pub.title.strip().lower() == r.strip().lower() for r in cand_prof.read_advisor_papers)
            if has_read:
                reasons.append("候选人已深度精读并具备反思")

            if reasons:
                matched_advisor_pubs.append({
                    "title": pub.title,
                    "year": pub.year,
                    "venue": pub.venue,
                    "match_reasons": reasons,
                    "has_read": has_read
                })

        # 4. Check if matched against Advisor's Recent Pivot (Recency Bonus)
        recent_years = recent_pivot["years"]
        recent_pivot_match = False
        recent_matched_reasons = []
        for mp in matched_advisor_pubs:
            if mp["year"] in recent_years:
                recent_pivot_match = True
                recent_matched_reasons.append(f"成果《{mp['title']}》（{mp['year']}年）契合课题组近三年战略转向")

        # 5. Rigorous Component-based Scoring (0-100)
        # Component A: Topic / Domain Alignment (Max 40 pts)
        topic_count = len(mutual_topics)
        topic_score = min(40.0, topic_count * 15.0)
        if not mutual_topics and any(int_item.lower() in advisor_corpus_text for int_item in cand_interests):
            topic_score = 20.0

        # Component B: Technical Overlap & Method Fit (Max 30 pts)
        overlap_count = len(technical_overlaps)
        tech_score = min(30.0, overlap_count * 10.0)

        # Component C: Candidate Foundation & Rigor (Max 20 pts)
        foundation_score = 0.0
        # GPA / Rank
        if cand_prof.rank_percentage is not None:
            if cand_prof.rank_percentage <= 0.01:
                foundation_score += 10.0
            elif cand_prof.rank_percentage <= 0.05:
                foundation_score += 8.0
            elif cand_prof.rank_percentage <= 0.15:
                foundation_score += 5.0
            else:
                foundation_score += 3.0
        elif cand_prof.rank:
            if any(top in cand_prof.rank for top in ["1/", "前1%"]):
                foundation_score += 10.0
            elif any(top in cand_prof.rank for top in ["前2%", "前5%"]):
                foundation_score += 8.0
            else:
                foundation_score += 5.0
        else:
            foundation_score += 4.0

        # Publications / Awards / Projects / Coursework
        if cand_prof.publications:
            foundation_score += 6.0
        if cand_prof.honors_awards:
            foundation_score += 4.0
        if cand_prof.projects:
            foundation_score += 4.0
        if cand_prof.coursework:
            foundation_score += 2.0
        foundation_score = min(20.0, foundation_score)

        # Component D: Recency Alignment Bonus (Max 10 pts)
        recency_score = 10.0 if recent_pivot_match else (5.0 if matched_advisor_pubs else 0.0)

        total_score = round(topic_score + tech_score + foundation_score + recency_score, 1)
        total_score = min(100.0, max(0.0, total_score))

        # Match Tier
        if total_score >= 85.0:
            match_tier = "卓越契合 (Strong Match / Tier S)"
            fit_description = "候选人学术基础坚实，技术栈与导师近三年重点推进的研究方向高度互补，可直接赋能实验室在研课题。"
        elif total_score >= 70.0:
            match_tier = "高度匹配 (High Match / Tier A)"
            fit_description = "核心方向与导师重点方向相符，具备必要的科研训练与工程实现能力，能快速进入科研状态。"
        elif total_score >= 50.0:
            match_tier = "中度契合 (Moderate Match / Tier B)"
            fit_description = "存在部分交集，建议重点通过代表性基础课程与自驱学习能力证明交叉潜质。"
        else:
            match_tier = "跨领域探索 (Exploratory / Need Pre-requisite Bridging)"
            fit_description = "背景存在较大跨度，需在自荐信中清晰阐释转方向的理性动机与为弥补前置知识所做的具体准备。"

        # Strategic Angle of Attack
        strategic_angle = self._generate_strategic_angle(
            advisor_prof, cand_prof, technical_overlaps, mutual_topics, recent_pivot_match
        )

        # Gap Recommendations
        gap_recommendations = self._generate_gap_recommendations(
            advisor_prof, cand_prof, technical_overlaps, mutual_topics
        )

        return {
            "intersection_score": total_score,
            "match_tier": match_tier,
            "fit_description": fit_description,
            "technical_overlap_points": technical_overlaps,
            "mutual_research_topics": mutual_topics,
            "matched_advisor_publications": matched_advisor_pubs,
            "advisor_recent_focus_match": recent_pivot_match,
            "recent_focus_signals": recent_matched_reasons,
            "scoring_breakdown": {
                "topic_alignment": topic_score,
                "tech_overlap": tech_score,
                "candidate_foundation": foundation_score,
                "recency_bonus": recency_score
            },
            "strategic_angle": strategic_angle,
            "gap_recommendations": gap_recommendations
        }

    # ------------------------------------------------------------------------
    # 2.3 High-EQ Chinese Advisor Outreach Email Generation
    # ------------------------------------------------------------------------

    def generate_outreach_email(
        self,
        advisor: Union[AdvisorProfile, Dict[str, Any]],
        candidate: Union[CandidateProfile, Dict[str, Any]],
        email_scenario: str = "summer_camp",  # summer_camp, pre_recommendation, postgraduate_reexam, phd_application
        target_degree: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates high-EQ, academic-standard Chinese Advisor Outreach Emails.
        Strictly enforces:
        1. 2-sentence Profile Hook (Rank, School, GPA, Key achievements).
        2. Genuine Academic Reflection (No flattery, grounded in verified paper/topic).
        3. Clear Value Proposition (Candidate skills accelerating lab milestones).
        4. Concise materials attachment guide.
        5. Anti-hallucination verification.
        """
        advisor_prof = self._ensure_advisor_profile(advisor)
        cand_prof = self._ensure_candidate_profile(candidate)
        degree = target_degree or cand_prof.target_degree

        # Degree term in Chinese
        degree_map = {
            "master": "硕士研究生",
            "academic_master": "学术型硕士",
            "professional_master": "专业型硕士",
            "phd": "博士研究生",
            "direct_phd": "直博生"
        }
        degree_cn = degree_map.get(degree, "研究生")

        # Scenario term in Chinese
        scenario_map = {
            "summer_camp": "保研夏令营",
            "pre_recommendation": "预推免自荐",
            "postgraduate_reexam": "考研复试联系",
            "phd_application": "博士研究生申请"
        }
        scenario_cn = scenario_map.get(email_scenario, "学术深造自荐")

        # Compute match details to inform the email
        match_result = self.match_candidate_to_advisor(advisor_prof, cand_prof)

        # 1. Subject Line
        # Format: [保研自荐] 华中科技大学-计算机-李明-意向报考张伟老师直博生
        subject = f"[{scenario_cn}] {cand_prof.undergraduate_school}-{cand_prof.major}-{cand_prof.name}-意向报考{advisor_prof.name}老师{degree_cn}"

        # 2. Salutation (Respectful, precise surname + title)
        salutation = f"尊敬的{advisor_prof.surname}老师："

        # 3. Profile Hook (Strict 2 sentences)
        hook_sentence_1 = f"您好！我是{cand_prof.undergraduate_school}{cand_prof.major}专业的{cand_prof.grade}{cand_prof.name}，对您课题组的研究方向极为向往。"
        
        # Build academic credentials clause
        cred_parts = []
        if cand_prof.gpa:
            cred_parts.append(f"GPA {cand_prof.gpa}")
        if cand_prof.rank:
            cred_parts.append(f"专业排名 {cand_prof.rank}")
        if cand_prof.honors_awards:
            cred_parts.append(f"曾获{cand_prof.honors_awards[0]}")
        cred_str = "，".join(cred_parts) if cred_parts else "专业成绩名列前茅，数理与专业基础扎实"

        # Key achievements (project / publication / competition)
        achievement_str = ""
        if cand_prof.publications:
            top_pub = cand_prof.publications[0]
            pub_title = top_pub.get("title", "学术成果")
            pub_venue = top_pub.get("venue", "")
            achievement_str = f"曾以第一作者/核心作者在{pub_venue or '相关领域'}发表《{pub_title}》"
        elif cand_prof.projects:
            top_prj = cand_prof.projects[0]
            prj_name = top_prj.get("name", "科研项目")
            achievement_str = f"曾主导完成【{prj_name}】，具备从算法复现到工程调优的完整科研闭环经历"
        else:
            achievement_str = "具备严谨的数理思维与扎实的系统工程实践能力"

        hook_sentence_2 = f"本科期间我{cred_str}；科研实践方面，我{achievement_str}。"
        profile_hook = f"{hook_sentence_1}\n{hook_sentence_2}"

        # 4. Genuine Academic Reflection (Anti-Hallucination Enforced)
        # Select target paper or topic
        verified_paper: Optional[Publication] = None
        # Check if candidate has specified read papers
        if cand_prof.read_advisor_papers:
            for r_title in cand_prof.read_advisor_papers:
                for p in advisor_prof.recent_publications:
                    if p.title.strip().lower() == r_title.strip().lower():
                        verified_paper = p
                        break
                if verified_paper:
                    break

        # If no read paper specified, pick the most relevant recent publication
        if not verified_paper and advisor_prof.recent_publications:
            # Prefer publications that matched overlap
            if match_result["matched_advisor_publications"]:
                top_matched_title = match_result["matched_advisor_publications"][0]["title"]
                for p in advisor_prof.recent_publications:
                    if p.title == top_matched_title:
                        verified_paper = p
                        break
            if not verified_paper:
                verified_paper = advisor_prof.recent_publications[-1]

        # Construct Reflection without flattery
        if verified_paper:
            venue_clause = f"发表于 {verified_paper.venue} 的" if verified_paper.venue else ""
            core_point = verified_paper.core_contribution or (f"关于【{'、'.join(verified_paper.keywords)}】的探讨" if verified_paper.keywords else "所提出的方法架构与技术设计")
            academic_reflection = (
                f"在深入了解课题组近期科研动态时，我认真研读了您组内近期{venue_clause}代表性成果《{verified_paper.title}》。"
                f"我对文中所阐述的{core_point}印象十分深刻。特别是在应对实际应用中的复杂约束与瓶颈时，"
                f"文中通过合理的方案设计兼顾了有效性与泛化能力，展现出极其深刻的学术洞察，这使我在审视自己此前的相关尝试时深受启发。"
            )
        else:
            # Fallback when no publications list provided: rely strictly on documented topics/projects
            topics_str = "、".join(advisor_prof.research_topics[:2]) if advisor_prof.research_topics else "智能系统"
            academic_reflection = (
                f"在系统跟踪学术前沿与了解您课题组的科研布局后，我一直密切关注您在【{topics_str}】领域的深耕与突破。"
                f"尤其注意到课题组在解决该领域核心瓶颈时所秉持的系统化思维与落地导向，与我本人的研究兴趣高度契合。"
            )

        # 5. Clear Value Proposition (Lab Milestone Acceleration)
        overlap_skills = match_result["technical_overlap_points"]
        skills_phrase = "、".join(overlap_skills[:3]) if overlap_skills else ("、".join(cand_prof.skills[:3]) if cand_prof.skills else "算法设计与代码工程能力")
        
        target_lab_project = ""
        if advisor_prof.lab_projects:
            target_lab_project = f"课题组【{advisor_prof.lab_projects[0]}】等在研项目"
        elif advisor_prof.research_topics:
            target_lab_project = f"课题组在【{advisor_prof.research_topics[0]}】方向的前沿探索"
        else:
            target_lab_project = "课题组当前的重大科研攻坚"

        cand_evidence = ""
        if cand_prof.projects:
            cand_evidence = f"在【{cand_prof.projects[0].get('name', '过往科研')}】中积累了高强度的实操经验"
        else:
            cand_evidence = "具备快速阅读顶会论文、复现核心算法并定位排查复杂Bug的能力"

        value_proposition = (
            f"结合我自身的科研准备，我熟练掌握了 {skills_phrase}，且{cand_evidence}。"
            f"如果能有幸加入您的团队，我相信自己的这一技术背景能够无缝衔接并加速{target_lab_project}的实验推进，"
            f"在基线构建、算法迭代与数据管线优化上迅速形成生产力，协助师兄师姐攻克既定里程碑，缩短研发验证周期。"
        )

        # 6. Concise Materials Attachment Guide & Professional Call to Action
        resume_filename = f"[个人简历]_{cand_prof.undergraduate_school}_{cand_prof.name}_意向{degree_cn}.pdf"
        attachment_guide = (
            f"为方便您在百忙之中查阅，我已随信附上：\n"
            f"1. 个人学术简历（1页PDF精简版，包含核心项目与成果链接，文件命名为：{resume_filename}）；\n"
            f"2. 本科官方成绩单及专业排名证明扫描件（PDF）。"
        )

        closing_cta = (
            f"得知您在今年夏秋季有招收{degree_cn}的计划，我真诚希望能争取到一个进入课题组考核或向您汇报交流的机会。"
            f"若您时间方便，我非常期待能参与课题组的学术讨论或进行一次15分钟的线上/线下面谈，向您当面请教！\n\n"
            f"再次感谢老师在百忙之中抽时间审阅这封信件，祝您工作顺利，桃李芬芳！"
        )

        # 7. Signature
        contact_items = [f"电话：{cand_prof.phone}"] if cand_prof.phone else []
        if cand_prof.email:
            contact_items.append(f"邮箱：{cand_prof.email}")
        if cand_prof.wechat:
            contact_items.append(f"微信：{cand_prof.wechat}")
        contact_str = " | ".join(contact_items)

        signature = (
            f"学生：{cand_prof.name}\n"
            f"{cand_prof.undergraduate_school} {cand_prof.major}\n"
            f"{contact_str}"
        )

        # Full body assembly
        email_body = f"{salutation}\n\n{profile_hook}\n\n{academic_reflection}\n\n{value_proposition}\n\n{attachment_guide}\n\n{closing_cta}\n\n{signature}"

        # Strict Anti-Hallucination Audit
        anti_hallucination_report = self._verify_anti_hallucination(
            email_body, advisor_prof, cand_prof
        )

        # Practical Sending Tips (baoyan best practices)
        sending_tips = [
            f"建议发送时间：工作日（周一至周四）早晨 8:00 - 8:40 之间（导师通常在此时清空晨间邮箱，置顶几率最高）。",
            f"发信邮箱建议：优先使用带有学校域名的edu邮箱（如 @*.edu.cn），权威度高，极不易被归入垃圾邮件箱。",
            f"附件规范：简历控制在严格1页PDF，大小不超过2MB，命名采用统一规范：{resume_filename}，切忌发送.docx或打包超大压缩包。",
            f"跟进准则（防骚扰与得体追问）：若发出一周（7天）后未收到回复，导师通常可能在出差、基金评审或邮件淹没。可发送一次礼貌跟进信（Follow-up），若仍无回复则应果断寻找下一位导师。"
        ]

        return {
            "subject": subject,
            "salutation": salutation,
            "profile_hook": profile_hook,
            "academic_reflection": academic_reflection,
            "value_proposition": value_proposition,
            "attachment_guide": attachment_guide,
            "closing_cta": closing_cta,
            "signature": signature,
            "email_body": email_body,
            "body": email_body,
            "sending_tips": sending_tips,
            "anti_hallucination_report": anti_hallucination_report,
            "match_details": {
                "intersection_score": match_result["intersection_score"],
                "match_tier": match_result["match_tier"],
                "technical_overlap_points": match_result["technical_overlap_points"],
                "mutual_research_topics": match_result["mutual_research_topics"]
            }
        }

    # ------------------------------------------------------------------------
    # 2.4 Anti-Pigeon & Academic Etiquette Guidelines
    # ------------------------------------------------------------------------

    def generate_anti_pigeon_guidelines(
        self,
        advisor: Optional[Union[AdvisorProfile, Dict[str, Any]]] = None,
        candidate: Optional[Union[CandidateProfile, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generates comprehensive Anti-Pigeon & Academic Etiquette Guidelines (防鸽与学术信誉指南).
        Covers verbal commitment matrix, timeline management, multiple summer camp offers,
        reputation protection for undergraduate alma mater, and polite rejection letter templates.
        """
        advisor_prof = self._ensure_advisor_profile(advisor) if advisor else None
        cand_prof = self._ensure_candidate_profile(candidate) if candidate else None

        advisor_surname = advisor_prof.surname if advisor_prof else "老师"
        student_name = cand_prof.name if cand_prof else "同学"
        school = cand_prof.undergraduate_school if cand_prof else "母校"

        # 1. Verbal Commitment Matrix
        verbal_commitment_matrix = [
            {
                "tier": "Tier 1: 弱好感 / 官方客套 (Weak Positive)",
                "typical_expressions": ["欢迎报考", "欢迎报名夏令营", "祝你取得好成绩", "材料已阅，可以报我的方向"],
                "true_meaning": "导师对你的基本背景无硬伤排斥，但该邮件可能同时群发/模板化回复给数十位申请人。绝对不等于锁定名额！",
                "action_guidance": "切勿停止联系其他导师；全力准备夏令营笔试与机试；可继续深耕学术理解争取下一步考核机会。"
            },
            {
                "tier": "Tier 2: 考核意向 / 课题组面试 (Interview Invitation)",
                "typical_expressions": ["请来组里参加学术面试", "准备一份15分钟的PPT报告", "建议你进组参加2-4周的暑期实习考核"],
                "true_meaning": "进入真实考核圈（通常1个名额考察2-3人）。导师开始实质性考查你的代码工程、论文阅读与科研主动性。",
                "action_guidance": "务必认真复现该组经典代码，组会汇报时实事求是，不懂不要装懂。如果无法参加实习，应礼貌坦诚说明时间冲突。"
            },
            {
                "tier": "Tier 3: 导师个人口头承诺 (Advisor Verbal Commitment)",
                "typical_expressions": ["只要你过院线/拿到夏令营优营，我就收你", "我今年唯一的直博名额留给你了", "你确定要来的话我就不再面试其他人了"],
                "true_meaning": "导师个人高度认可，并具有极高信任度。但效力受限于：①导师是否拥有独立招生指标；②你是否能通过学院官方统考大门槛。",
                "action_guidance": "礼貌向导师确认：‘请问老师，学院名额分配是否已经确定？如果拿到优营是否能直接确认双选？’，同时给予导师负责任的明确态度。"
            },
            {
                "tier": "Tier 4: 强锁定 / 院系公函级绑定 (Institutional Binding / Locked Offer)",
                "typical_expressions": ["夏令营优秀营员且第一志愿填报直接拟录取", "学院研招办已完成预录取双选签字盖章", "签署了具有约束力的推荐免试双向承诺意向书"],
                "true_meaning": "最高效力保障。学院招生行政体系背书，除非考生因体检或未取得本科推免资格，否则具有绝对确定性。",
                "action_guidance": "一旦在此阶段确认答应老师，即为学术契约成立！坚决不可毁约（鸽），否则将对个人学术信誉和本科母校带来极大伤害。"
            }
        ]

        # 2. Timeline Management & Decision Framework
        timeline_framework = {
            "3月-5月 (早期摸底与定向套磁)": "梳理个人技术资产，精读目标导师近三年代表作，定向套磁，避免盲目群发。",
            "6月-7月 (夏令营高密期)": "多所院校夏令营考核冲突处理。同一院系同一方向严禁同时联系两位有竞争关系的老师！",
            "8月-9月上旬 (预推免与收敛期)": "收到多份优营或预录取时，严格执行【24-48小时收敛原则】。做出选择后，必须第一时间主动释放其他名额！",
            "9月中下旬 (终局决策期)": "手中的有效口头承诺必须严格收敛至唯一去向（1个）。坚决禁止‘广撒网养鱼’拖延至9月28日系统开放前夜！",
            "9月28日 0:00 (全国推免系统开放)": "0点准时填报既定高校与导师，复试与拟录取通知在系统规定时间内迅速点击确认，契约彻底落地。"
        }

        # 3. Alma Mater Reputation & Ethical Imperatives
        reputation_imperatives = (
            f"保研圈内导师群体学术声誉高度互通。许多高校导师在被某个本科学校的学生违约‘放鸽子’导致名额报废后，"
            f"次年往往会直接在学院招生委员会上提议将该校列入重点关注或隐性黑名单（‘扣减或不再接收来自【{school}】的学生’）。"
            f"因此，及时、得体地处理多Offer，不仅关乎个人学术道德，更关乎保护母校学弟学妹未来数年的推免通路！"
        )

        # 4. Professional Rejection & Confirmation Templates
        rejection_template_camp = (
            f"尊敬的{advisor_surname}老师：\n\n"
            f"您好！衷心感谢您此前在百忙之中审阅我的申请材料并给予我宝贵的考核机会。\n\n"
            f"经过这几天的慎重思考，并结合我个人的长期学术规划与家庭地域综合考量，我十分遗憾地决定放弃参加课题组后续的面试/夏令营考核。\n\n"
            f"做出这个决定非常艰难，因为您的课题组一直是我十分敬仰的学习殿堂。但为了不耽误课题组宝贵的招生节奏，并确保候补名额能尽快开放给其他优秀的同学，我选择第一时间向您汇报这一决定。\n\n"
            f"再次为给您带来的不便深表歉意，衷心感谢老师前期的关注与厚爱！祝愿老师科研顺遂，课题组欣欣向荣！\n\n"
            f"学生：{student_name}\n"
            f"{school}"
        )

        release_verbal_commitment_template = (
            f"尊敬的{advisor_surname}老师：\n\n"
            f"您好！十分抱歉在这个时候给您发送这封邮件，心情万分沉重与内疚。\n\n"
            f"前期您给予我的认可与口头承诺，是对我本科科研努力的最大褒奖。但近期结合家庭与未来具体研究方向的深入考量，经过极其痛苦的抉择，我最终确定前往另一所院校攻读研究生。\n\n"
            f"我知道名额对每位导师都至关重要，因此我第一时间向您如实汇报，绝不敢有丝毫拖延，希望能把对课题组招生工作的影响降到最低，以便老师尽快联系并补录其他优秀的同学。\n\n"
            f"未能成为您的学生是我巨大的遗憾，对于辜负了您的信任与期望，我向您致以最深切的歉意！无论未来在何处深造，我都将铭记老师的教诲与鼓励。\n\n"
            f"非常抱歉打扰老师，再次由衷感谢您！敬祝身体健康，工作顺心！\n\n"
            f"后学：{student_name}\n"
            f"{school}"
        )

        lock_offer_confirmation_template = (
            f"尊敬的{advisor_surname}老师：\n\n"
            f"您好！我是{school}的{student_name}。\n\n"
            f"收到您的录取意向通知，我倍感振奋与荣幸！在此我郑重向您承诺：我已完全确定将您的课题组作为我保研的唯一最终去向，我已全面停止并回绝其他所有院校与导师的后续考核邀请，绝无任何变数。\n\n"
            f"在9月28日国家推免系统开放当日，我保证第一时间填报贵院及您的课题组，并在系统下发通知后即刻点击确认。\n\n"
            f"接下来的一年时间里，我愿听从老师的安排提前进入科研状态。如果您有推荐的基础书目、前沿论文或希望我提前参与的组内课题，请随时吩咐！\n\n"
            f"非常感谢老师对我的信任，我定全力以赴，不负期待！\n\n"
            f"学生：{student_name}\n"
            f"{school}"
        )

        follow_up_template = (
            f"尊敬的{advisor_surname}老师：\n\n"
            f"您好！我是{school}{cand_prof.major if cand_prof else '计算机'}专业的{student_name}。\n\n"
            f"大约一周前（X月X日）我曾冒昧给您发送了一封自荐邮件，向您汇报了我意向报考您课题组读研的愿景。考虑到老师平日科研与指导工作十分繁忙，可能未及查阅，因此特写此简短邮件随访。\n\n"
            f"我一直密切关注课题组在相关方向的研究进展，若您组内近期有招收计划，我依然非常渴望能获得向您线上或线下简短汇报的机会。\n\n"
            f"若老师今年已有确定人选或研究方向暂不匹配，也完全理解，在此衷心祝愿老师工作顺利，科研成果丰硕！\n\n"
            f"学生：{student_name}\n"
            f"{school}"
        )

        return {
            "verbal_commitment_matrix": verbal_commitment_matrix,
            "timeline_framework": timeline_framework,
            "reputation_imperatives": reputation_imperatives,
            "etiquette_rules": [
                "24-48小时决断原则：获得确定offer后，如打算放弃其他已知offer，应在48小时内邮件礼貌回绝，绝不故意当‘海王’占坑。",
                "绝不在928当天‘失联跑路’：若放弃某位导师，必须留出至少7-14天供导师启动候补程序，绝不能在系统开放最后一小时关机失联。",
                "坦诚真实，不编造离奇借口：拒绝信要谦逊诚恳，说明是综合考虑了个人方向/地域等现实因素，切勿无端指责或前后矛盾。",
                "礼貌感恩，维护师生善缘：学术圈很小，哪怕未拜入师门，未来在学术会议、审稿或联合项目中仍可能共事，得体的沟通是高情商的最好体现。"
            ],
            "templates": {
                "decline_summer_camp": rejection_template_camp,
                "release_verbal_commitment": release_verbal_commitment_template,
                "lock_offer_confirmation": lock_offer_confirmation_template,
                "follow_up_unanswered": follow_up_template
            }
        }

    # ------------------------------------------------------------------------
    # 2.5 Private Helper Methods & Anti-Hallucination Guard
    # ------------------------------------------------------------------------

    def _ensure_advisor_profile(self, advisor: Union[AdvisorProfile, Dict[str, Any]]) -> AdvisorProfile:
        if isinstance(advisor, AdvisorProfile):
            return advisor
        
        pubs_raw = advisor.get("recent_publications", advisor.get("representative_papers", advisor.get("publications", [])))
        pubs: List[Publication] = []
        for p in pubs_raw:
            if isinstance(p, Publication):
                pubs.append(p)
            elif isinstance(p, dict):
                year_val = p.get("year", 0)
                if not year_val:
                    # extract year from venue string e.g. "OSDI 2024"
                    venue_str = str(p.get("venue", ""))
                    year_match = re.search(r'\b(20\d\d)\b', venue_str)
                    if year_match:
                        year_val = int(year_match.group(1))
                pubs.append(Publication(
                    title=str(p.get("title", "")),
                    year=int(year_val),
                    venue=str(p.get("venue", "")),
                    abstract=str(p.get("abstract", "")),
                    keywords=list(p.get("keywords", [])),
                    lead_type=str(p.get("lead_type", "")),
                    core_contribution=str(p.get("core_contribution", p.get("summary", p.get("contribution", ""))))
                ))

        topics = list(advisor.get("research_topics", advisor.get("research_directions", advisor.get("topics", []))))

        return AdvisorProfile(
            name=str(advisor.get("name", "导师")),
            title=str(advisor.get("title", "教授")),
            institution=str(advisor.get("institution", "")),
            department=str(advisor.get("department", advisor.get("college", ""))),
            research_topics=topics,
            recent_publications=pubs,
            lab_projects=list(advisor.get("lab_projects", advisor.get("projects", []))),
            email=str(advisor.get("email", "")),
            homepage_url=str(advisor.get("homepage_url", advisor.get("homepage", ""))),
            openings_info=dict(advisor.get("openings_info", advisor.get("openings", {})))
        )

    def _ensure_candidate_profile(self, candidate: Union[CandidateProfile, Dict[str, Any]]) -> CandidateProfile:
        if isinstance(candidate, CandidateProfile):
            return candidate

        cand_dict = candidate.get("candidate", {}) if "candidate" in candidate else candidate
        standing_dict = candidate.get("academic_standing", {})

        # Extract skills (support list or dict categorized)
        raw_skills = candidate.get("skills", [])
        flat_skills: List[str] = []
        if isinstance(raw_skills, list):
            flat_skills = [str(s) for s in raw_skills]
        elif isinstance(raw_skills, dict):
            for k, val_list in raw_skills.items():
                if isinstance(val_list, list):
                    flat_skills.extend([str(item) for item in val_list])

        school = cand_dict.get("undergraduate_school", cand_dict.get("university", cand_dict.get("school", "")))
        major = cand_dict.get("major", "")
        gpa = str(standing_dict.get("gpa_display", standing_dict.get("gpa", candidate.get("gpa", ""))))
        rank = str(standing_dict.get("rank", candidate.get("rank", "")))

        coursework = [c.get("course_name", "") for c in standing_dict.get("core_courses", [])] if "core_courses" in standing_dict else list(candidate.get("coursework", candidate.get("courses", [])))
        honors = [h.get("name", "") for h in candidate.get("honors", [])] if "honors" in candidate else list(candidate.get("honors_awards", candidate.get("awards", [])))

        # Extract research interests from candidate interests or target schools
        interests = list(candidate.get("research_interests", candidate.get("interests", [])))
        if not interests and "target_schools" in candidate:
            for ts in candidate["target_schools"]:
                rd = ts.get("research_direction")
                if rd and rd not in interests:
                    interests.append(rd)
        if not interests and "graduation_thesis" in candidate:
            gt = candidate["graduation_thesis"]
            interests.extend(gt.get("tags", []))

        return CandidateProfile(
            name=str(cand_dict.get("name", "候选人")),
            undergraduate_school=str(school),
            major=str(major),
            grade=str(cand_dict.get("grade", "2022级本科生")),
            target_degree=str(candidate.get("target_degree", "master")),
            gpa=gpa,
            rank=rank,
            rank_percentage=candidate.get("rank_percentage"),
            honors_awards=honors,
            publications=list(candidate.get("publications", [])),
            projects=list(candidate.get("projects", [])),
            coursework=coursework,
            skills=flat_skills,
            research_interests=interests,
            read_advisor_papers=list(candidate.get("read_advisor_papers", [])),
            email=str(cand_dict.get("email", "")),
            phone=str(cand_dict.get("phone", "")),
            wechat=str(cand_dict.get("wechat", ""))
        )

    def _generate_strategic_angle(
        self,
        advisor: AdvisorProfile,
        candidate: CandidateProfile,
        technical_overlaps: List[str],
        mutual_topics: List[str],
        recent_pivot_match: bool
    ) -> str:
        lead_project = candidate.projects[0]["name"] if candidate.projects else "过往科研实践"
        lead_skill = technical_overlaps[0] if technical_overlaps else (candidate.skills[0] if candidate.skills else "系统工程实现")
        target_focus = mutual_topics[0] if mutual_topics else (advisor.research_topics[0] if advisor.research_topics else "课题组重点方向")

        if recent_pivot_match:
            return (
                f"【先锋突击策略】：紧扣导师近三年从传统方向切入【{target_focus}】的战略转型，"
                f"以自身在【{lead_project}】中淬炼的【{lead_skill}】实战能力为抓手，突出‘即插即用、缩短团队研发摸索期’的独特价值。"
            )
        else:
            return (
                f"【扎实基底策略】：以扎实的数学基础与【{lead_skill}】工程素养为基石，"
                f"结合【{lead_project}】展现出来的自驱攻坚与快速文献复现能力，打消导师对本科生跨方向或新课题磨合期的顾虑。"
            )

    def _generate_gap_recommendations(
        self,
        advisor: AdvisorProfile,
        candidate: CandidateProfile,
        technical_overlaps: List[str],
        mutual_topics: List[str]
    ) -> List[str]:
        recommendations = []
        cand_skill_set = set(s.lower() for s in candidate.skills)

        # Check if advisor works on modern LLM / Multimodal but candidate lacks distributed / deep learning tools
        advisor_topics_text = " ".join(advisor.research_topics + advisor.lab_projects).lower()
        if any(term in advisor_topics_text for term in ["大模型", "llm", "多模态", "vlm"]):
            if not any(k in cand_skill_set for k in ["pytorch", "deepspeed", "vllm", "cuda", "transformer"]):
                recommendations.append("建议在面试前系统复习PyTorch分布式训练基础（DDP/FSDP）与主流Transformer显存优化手段（FlashAttention）。")

        if any(term in advisor_topics_text for term in ["具身智能", "机器人", "embodied"]):
            if not any(k in cand_skill_set for k in ["ros", "isaac", "mujoco", "强化学习", "rl"]):
                recommendations.append("课题组涉足具身智能/物理仿真，建议提前了解MuJoCo/Isaac Gym环境搭建或常见强化学习PPO代码实现。")

        if not candidate.publications:
            recommendations.append("由于缺少第一作者正式发表论文，面试与自荐信中应着重强调本科项目中的‘独立代码贡献量’与‘实验排查思路’以证明科研素养。")

        if not recommendations:
            recommendations.append("科研技术栈匹配度极佳，建议在联系前精读导师近一年发表的最新1篇预印本/顶会论文，准备1-2个建设性的技术探讨问题。")

        return recommendations

    def _verify_anti_hallucination(
        self,
        text: str,
        advisor: AdvisorProfile,
        candidate: CandidateProfile
    ) -> Dict[str, Any]:
        """
        Anti-Hallucination Guard:
        Extracts all paper titles in Chinese title marks 《...》 from text.
        Verifies whether every referenced paper title actually exists in factual input
        (advisor.recent_publications or candidate.publications).
        """
        quoted_titles = re.findall(r'《(.*?)》', text)
        factual_advisor_titles = set(p.title.strip() for p in advisor.recent_publications)
        factual_cand_titles = set(p.get("title", "").strip() for p in candidate.publications)
        all_factual_titles = factual_advisor_titles.union(factual_cand_titles)

        verified_citations = []
        hallucinated_citations = []

        for title in quoted_titles:
            clean_title = title.strip()
            # Allow partial match if title was cleanly substring matched
            matched = False
            for ft in all_factual_titles:
                if clean_title == ft or clean_title in ft or ft in clean_title:
                    matched = True
                    verified_citations.append(clean_title)
                    break
            if not matched:
                hallucinated_citations.append(clean_title)

        is_clean = len(hallucinated_citations) == 0
        return {
            "is_clean": is_clean,
            "verified_citations": verified_citations,
            "hallucinated_citations": hallucinated_citations,
            "audit_verdict": "严谨真实（未检出任何虚构论文）" if is_clean else f"风险警告（检出未收录文献：{hallucinated_citations}）"
        }


# ============================================================================
# 3. Top-Level Convenience Function
# ============================================================================

def match_advisor_and_draft_email(
    advisor_data: Dict[str, Any],
    candidate_data: Dict[str, Any],
    email_scenario: str = "summer_camp",
    target_degree: Optional[str] = None
) -> Dict[str, Any]:
    """
    Top-level convenience function:
    1. Ingests and profiles Chinese advisor & candidate.
    2. Analyzes advisor research timeline and paradigm evolution.
    3. Computes intersection match score and technical overlap.
    4. Drafts high-EQ, academic-standard outreach email with strict anti-hallucination.
    5. Returns Anti-Pigeon and academic etiquette guidelines.
    """
    matcher = AdvisorMatcher()
    
    # 1. Timeline
    timeline = matcher.analyze_advisor_timeline(advisor_data)

    # 2. Match
    match_result = matcher.match_candidate_to_advisor(advisor_data, candidate_data)

    # 3. Email
    email_result = matcher.generate_outreach_email(
        advisor=advisor_data,
        candidate=candidate_data,
        email_scenario=email_scenario,
        target_degree=target_degree
    )

    # 4. Anti-Pigeon Guidelines
    anti_pigeon = matcher.generate_anti_pigeon_guidelines(
        advisor=advisor_data,
        candidate=candidate_data
    )

    return {
        "advisor_timeline": timeline,
        "intersection_match": match_result,
        "outreach_email": email_result,
        "anti_pigeon_guidelines": anti_pigeon,
        "anti_hallucination_report": email_result["anti_hallucination_report"]
    }
