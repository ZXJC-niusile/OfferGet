"""
OfferGet Fact Verification Guard Module
Strictly anchors tailored resume bullets against candidate SSOT (candidate_profile.json)
to prevent AI hallucination, metric inflation, and ungrounded claims.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ---------------------------------------------------------------------------
# Technology & Version Whitelist & Inflation Lexicons (Centralized SSOT)
# ---------------------------------------------------------------------------
from core.profile_adapter import (
    ProfileEvidenceIndex,
    build_profile_evidence_index,
)
from core.registry import (
    AliasRegistry,
    MetricPatternRegistry,
    QualityRuleRegistry,
    TaxonomyRegistry,
)

NON_METRIC_TECH_PATTERNS = MetricPatternRegistry.NON_METRIC_TECH_PATTERNS
INFLATION_PATTERNS = QualityRuleRegistry.INFLATION_PATTERNS
FORBIDDEN_BUZZWORDS = QualityRuleRegistry.FORBIDDEN_BUZZWORDS
METRIC_TYPE_TO_TOPICS: Dict[str, Set[str]] = MetricPatternRegistry.METRIC_TYPE_TO_TOPICS


def _build_known_tech_terms() -> Set[str]:
    """Builds the comprehensive set of known technology and framework names."""
    terms: Set[str] = set()

    # 1. Terms and aliases from AliasRegistry
    for canon, aliases in AliasRegistry.all_aliases().items():
        terms.add(canon.lower())
        for a in aliases:
            terms.add(a.lower())

    # 2. Keywords from technical engineering role taxonomies in TaxonomyRegistry
    tech_roles = {
        "ai_algorithm", "backend_distributed", "frontend_fullstack",
        "client_mobile", "bigdata_infra", "cloudnative_sre"
    }
    for role_id in tech_roles:
        tax = TaxonomyRegistry.get_taxonomy(role_id)
        if tax:
            for kw in tax.get("keywords", []):
                terms.add(kw.lower())

    # 3. Additional prominent frameworks, databases, libraries, tools
    extra_techs = [
        "tensorflow", "jax", "mxnet", "onnx", "tensorrt", "tensorrt-llm", "sglang",
        "openvino", "tvm", "ray", "nccl", "mpi", "gloo", "deepspeed", "megatron-lm", "vllm",
        "langchain", "llamaindex", "langgraph", "autogpt", "crewai",
        "huggingface", "transformers", "diffusers", "peft", "lora", "qlora",
        "redis", "mysql", "postgresql", "postgres", "sqlite", "mongodb", "elasticsearch",
        "clickhouse", "hbase", "cassandra", "neo4j", "starrocks", "doris",
        "kafka", "rabbitmq", "rocketmq", "pulsar",
        "flink", "spark", "hadoop", "hive", "presto", "trino", "iceberg", "hudi",
        "kubernetes", "k8s", "docker", "slurm", "ebpf", "prometheus", "rdma",
        "fastapi", "flask", "django", "spring", "springboot", "gin", "echo",
        "react", "vue", "angular", "next.js", "nuxt", "vite", "typescript", "javascript",
        "python", "c++", "rust", "go", "golang", "java", "swift", "kotlin", "triton", "cuda",
        "faiss", "milvus", "chroma", "qdrant", "weaviate",
        "openai", "anthropic", "claude", "gemini", "llama", "qwen", "mistral", "deepseek",
    ]
    for t in extra_techs:
        terms.add(t.lower())

    return terms


KNOWN_TECH_TERMS: Set[str] = _build_known_tech_terms()

KNOWN_METHOD_TERMS: Set[str] = {
    # 算子与内核级别优化
    "通信算子重构", "通信算子", "算子重构", "算子融合", "算子优化", "算子开发", "算子定制", "自定义算子",
    "算子加速", "算子实现", "通信算子优化", "通信算子融合",
    # 并行与分布式训练
    "并行训练", "模型并行", "张量并行", "流水线并行", "序列并行", "上下文并行", "数据并行", "混合并行",
    "3d并行", "4d并行", "3d parallel", "4d parallel", "sequence parallel", "context parallel",
    "tensor parallel", "pipeline parallel", "data parallel", "hybrid parallel",
    # 推理加速与调度
    "投机采样", "连续批处理", "分块预填充", "chunked prefill", "continuous batching", "speculative decoding",
    # 集群治理与容灾
    "慢卡隔离", "心跳插桩", "慢节点剔除", "慢卡检测",
    # 强化对齐与训练算法
    "强化对齐", "过程奖励模型", "组内相对优势策略优化", "直接偏好优化",
    # 存储与分布式后端
    "分布式事务", "分库分表", "读写分离", "缓存穿透", "缓存雪崩", "微服务架构", "服务网格", "链路追踪",
    # 大数据湖仓
    "数据血缘", "湖仓一体", "实时计算", "离线计算",
}

EXCLUDED_ENGLISH_WORDS: Set[str] = {
    # Common prepositions, conjunctions, pronouns, articles, auxiliary verbs
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "down", "into", "over", "after", "before", "under", "between",
    "through", "during", "without", "again", "further", "then", "once", "here", "there",
    "all", "any", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "can", "will", "just", "should", "now", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "as", "via", "based", "etc",
    "this", "that", "these", "those", "we", "our", "us", "he", "she", "it", "they",
    # Common action verbs
    "led", "lead", "built", "build", "optimized", "optimize", "designed", "design",
    "developed", "develop", "implemented", "implement", "deployed", "deploy",
    "scaled", "scale", "architected", "architect", "engineered", "engineer",
    "spearheaded", "shipped", "delivered", "authored", "slashed", "boosted",
    "reduced", "reducing", "increasing", "slashing", "boosting", "improving",
    "completed", "achieved", "driving", "driven",
    # Metrics & units
    "ms", "s", "sec", "second", "seconds", "min", "minute", "minutes",
    "h", "hr", "hrs", "hour", "hours", "day", "days", "week", "weeks",
    "month", "months", "year", "years", "yoe",
    "k", "m", "b", "t", "w", "wan", "rmb", "usd",
    "gb", "tb", "pb", "mb", "kb", "gpu", "gpus", "cpu", "cpus",
    "card", "cards", "node", "nodes", "cluster", "clusters",
    "tps", "qps", "token", "tokens", "star", "stars", "citation", "citations",
    "x", "p99", "p95", "p90", "ttft", "mfu", "flops", "vram", "loss", "acc",
    # Generic computing / architecture nouns
    "ai", "llm", "ml", "nlp", "cv", "model", "models", "pipeline", "pipelines",
    "system", "systems", "platform", "platforms", "service", "services",
    "engine", "engines", "framework", "frameworks", "project", "projects",
    "task", "tasks", "code", "data", "dataset", "datasets", "api", "apis",
    "sdk", "sdks", "app", "apps", "web", "dense", "moe", "benchmark", "benchmarks",
    "eval", "evaluation", "baseline", "baselines", "end-to-end", "e2e",
    "http", "https", "json", "sql", "rest", "restful", "crud", "ui",
    "p7", "p8", "l5", "l6", "exp", "rfc", "git", "linux", "shell",
}



# ---------------------------------------------------------------------------
# FactVerificationGuard Class
# ---------------------------------------------------------------------------

class FactVerificationGuard:
    """
    Fact Verification Guard for tailored resume bullets.
    Anchors claims against SSOT master profile (candidate_profile.json) to detect:
      - METRIC_INFLATION_DRIFT: Claimed number exceeds verified SSOT baseline.
      - UNVERIFIED_NUMERICAL_CLAIM: Number has no factual anchor in SSOT.
    """

    def __init__(self, master_profile: Optional[Union[dict, str, Path, Any]] = None):
        """Initialize the guard with an optional master profile."""
        self.master_profile: Optional[dict] = None
        self.evidence_index: Optional[ProfileEvidenceIndex] = None
        self.profile_context: Optional[Any] = None
        self.baseline_anchors: List[Dict[str, Any]] = []
        self.all_verified_numbers: Set[float] = set()
        self.profile_all_text: str = ""
        self._experience_texts: List[str] = []
        self._project_texts: List[str] = []
        self._scope_to_text: Dict[str, str] = {}
        self._claim_id_to_scope: Dict[str, str] = {}
        self._company_to_exp_idx: Dict[str, int] = {}
        self._project_name_to_proj_idx: Dict[str, int] = {}

        if master_profile is not None:
            self.load_profile(master_profile)

    def load_profile(self, master_profile: Union[dict, str, Path, Any]) -> None:
        """Loads and indexes the candidate's Single Source of Truth (SSOT) profile."""
        from core.profile_adapter import ProfileContext, build_profile_context

        if isinstance(master_profile, ProfileContext):
            self.profile_context = master_profile
            self.master_profile = master_profile.normalized_profile
            self.evidence_index = master_profile.evidence_index
        elif isinstance(master_profile, ProfileEvidenceIndex):
            self.profile_context = None
            self.evidence_index = master_profile
            self.master_profile = master_profile.profile
        elif isinstance(master_profile, (str, Path)):
            is_file = False
            try:
                path = Path(master_profile)
                if path.exists() and path.is_file():
                    is_file = True
            except (OSError, ValueError):
                is_file = False

            if is_file:
                with open(path, "r", encoding="utf-8") as f:
                    raw_dict = json.load(f)
            else:
                raw_dict = json.loads(str(master_profile))
            self.profile_context = build_profile_context(raw_dict)
            self.master_profile = self.profile_context.normalized_profile
            self.evidence_index = self.profile_context.evidence_index
        elif isinstance(master_profile, dict):
            self.profile_context = build_profile_context(master_profile)
            self.master_profile = self.profile_context.normalized_profile
            self.evidence_index = self.profile_context.evidence_index
        else:
            raise TypeError(f"Expected dict, str, Path, or ProfileContext, got {type(master_profile).__name__}")

        self._index_master_profile()

    def _extract_all_profile_text(self) -> str:
        """Recursively extracts all text from the master profile and evidence index as a unified grounding baseline."""
        if not self.master_profile:
            return ""
        texts: List[str] = []

        def _collect(val: Any) -> None:
            if val is None:
                return
            if isinstance(val, str):
                texts.append(val)
            elif isinstance(val, (int, float, bool)):
                texts.append(str(val))
            elif isinstance(val, dict):
                for k, v in val.items():
                    texts.append(str(k))
                    _collect(v)
            elif isinstance(val, (list, tuple, set)):
                for item in val:
                    _collect(item)

        _collect(self.master_profile)

        if self.evidence_index:
            for c in self.evidence_index.claims:
                texts.append(c.text)
            for s in self.evidence_index.skills:
                texts.append(s)
            for b in self.evidence_index.bullets:
                texts.append(b)

        return " ".join(texts)

    def _index_master_profile(self) -> None:
        """Extracts structured metric anchors and verified baseline numbers from SSOT."""
        self.baseline_anchors = []
        self.all_verified_numbers = set()
        self.profile_all_text = self._extract_all_profile_text().lower()
        self._experience_texts = []
        self._project_texts = []
        self._scope_to_text = {}
        self._claim_id_to_scope = {}
        self._company_to_exp_idx = {}
        self._project_name_to_proj_idx = {}
        self._baseline_roles = {}

        if not self.master_profile:
            return

        # 1. Build immutable ProfileEvidenceIndex if not already provided
        if self.evidence_index is None:
            self.evidence_index = build_profile_evidence_index(self.master_profile)
        norm_profile = self.evidence_index.profile

        # Candidate metadata
        cand = norm_profile.get("candidate", {})
        if isinstance(cand, dict):
            yoe = cand.get("years_of_experience")
            if yoe is not None:
                try:
                    yoe_val = float(yoe)
                    self.baseline_anchors.append({
                        "anchor_id": "candidate:years_of_experience",
                        "topic": "experience_years",
                        "keywords": ["年", "years", "经验", "yoe", "研发经验", "工作经验"],
                        "baseline_value": yoe_val,
                        "baseline_raw": f"{int(yoe_val)}年",
                        "unit": "年",
                        "metric_type": "years"
                    })
                    self.all_verified_numbers.add(yoe_val)
                except (ValueError, TypeError):
                    pass

        # 2. Narrative summaries
        narrative = norm_profile.get("narrative", {})
        narrative_texts: List[str] = []
        if isinstance(narrative, dict):
            for text_key in ["summary_zh", "summary_en"]:
                text = narrative.get(text_key, "")
                if text:
                    narrative_texts.append(text)
                    self._extract_and_index_text_metrics(text, f"narrative:{text_key}")
        if narrative_texts:
            self._scope_to_text["narrative"] = " ".join(narrative_texts)

        # 3. Experience Highlights & Verified Metrics
        exp_list = norm_profile.get("experience")
        if exp_list is None and "internships" in norm_profile:
            exp_list = norm_profile.get("internships")
        if not isinstance(exp_list, list):
            exp_list = []

        for exp_idx, exp in enumerate(exp_list):
            if not isinstance(exp, dict):
                continue
            company = exp.get("company") or exp.get("org") or ""
            role = exp.get("role") or ""
            base_kw = self._extract_keywords(f"{company} {role}")

            if company:
                self._company_to_exp_idx[company.lower()] = exp_idx
                self._baseline_roles[company.lower()] = role
            self._baseline_roles[f"experience[{exp_idx}]"] = role

            exp_text_parts = [company, role]

            for h in exp.get("highlights", []):
                if not isinstance(h, dict):
                    continue
                claim_id = h.get("claim_id", f"EXP-{exp_idx}")
                claim_zh = h.get("claim_zh", "")
                claim_en = h.get("claim_en", "")
                verified_metrics = h.get("verified_metrics", {})

                self._claim_id_to_scope[claim_id] = f"experience[{exp_idx}]"
                if claim_zh:
                    exp_text_parts.append(claim_zh)
                if claim_en:
                    exp_text_parts.append(claim_en)

                context_words = base_kw | self._extract_keywords(f"{claim_zh} {claim_en}")

                # Index explicit verified_metrics dict
                if isinstance(verified_metrics, dict):
                    self._index_verified_metrics_dict(verified_metrics, claim_id, context_words)

                # Index text metrics
                if claim_zh:
                    self._extract_and_index_text_metrics(claim_zh, f"{claim_id}:claim_zh", context_words)
                if claim_en:
                    self._extract_and_index_text_metrics(claim_en, f"{claim_id}:claim_en", context_words)

            for b_idx, b in enumerate(exp.get("bullets", [])):
                b_text = b.get("text") or b.get("claim_zh") or b.get("claim_en") if isinstance(b, dict) else str(b)
                b_cid = f"experience[{exp_idx}].bullets[{b_idx}]"
                self._claim_id_to_scope[b_cid] = f"experience[{exp_idx}]"
                if b_text:
                    exp_text_parts.append(b_text)
                    b_kw = base_kw | self._extract_keywords(b_text)
                    self._extract_and_index_text_metrics(b_text, b_cid, b_kw)

            exp_full_text = " ".join(t for t in exp_text_parts if t)
            self._experience_texts.append(exp_full_text)
            self._scope_to_text[f"experience[{exp_idx}]"] = exp_full_text
            if company:
                self._scope_to_text[company.lower()] = exp_full_text

        # 4. Projects
        for p_idx, proj in enumerate(norm_profile.get("projects", [])):
            if not isinstance(proj, dict):
                continue
            proj_name = proj.get("name", "Project")
            proj_role = proj.get("role", "")
            p_kw = self._extract_keywords(proj_name)
            if proj_name:
                self._project_name_to_proj_idx[proj_name.lower()] = p_idx
                self._baseline_roles[proj_name.lower()] = proj_role
            self._baseline_roles[f"projects[{p_idx}]"] = proj_role

            p_text_parts = [proj_name, proj_role]

            stars = proj.get("stars")
            if stars is not None:
                try:
                    s_val = float(stars)
                    self.baseline_anchors.append({
                        "anchor_id": f"{proj_name}:stars",
                        "topic": "stars",
                        "keywords": list(p_kw | {"star", "stars", "星", "关注", "标星"}),
                        "baseline_value": s_val,
                        "baseline_raw": f"{int(s_val)} stars",
                        "unit": "stars",
                        "metric_type": "stars"
                    })
                    self.all_verified_numbers.add(s_val)
                except (ValueError, TypeError):
                    pass

            for desc_k in ["description", "description_zh", "description_en"]:
                d_text = proj.get(desc_k, "")
                if d_text:
                    p_text_parts.append(d_text)
                    self._extract_and_index_text_metrics(d_text, f"{proj_name}:{desc_k}", p_kw)

            for b_idx, b in enumerate(proj.get("bullets", [])):
                b_text = b.get("text") or b.get("claim_zh") or b.get("claim_en") if isinstance(b, dict) else str(b)
                b_cid = f"projects[{p_idx}].bullets[{b_idx}]"
                self._claim_id_to_scope[b_cid] = f"projects[{p_idx}]"
                if b_text:
                    p_text_parts.append(b_text)
                    self._extract_and_index_text_metrics(b_text, b_cid, p_kw | self._extract_keywords(b_text))

            proj_full_text = " ".join(t for t in p_text_parts if t)
            self._project_texts.append(proj_full_text)
            self._scope_to_text[f"projects[{p_idx}]"] = proj_full_text
            if proj_name:
                self._scope_to_text[proj_name.lower()] = proj_full_text

        # 5. Competencies & Skills
        comp_text_parts: List[str] = []
        comp = norm_profile.get("competencies")
        if isinstance(comp, dict):
            for k, v in comp.items():
                if isinstance(v, list):
                    comp_text_parts.extend(str(item) for item in v)
                elif v:
                    comp_text_parts.append(str(v))
        sk = norm_profile.get("skills")
        if isinstance(sk, list):
            comp_text_parts.extend(str(item) for item in sk)
        elif isinstance(sk, dict):
            for k, v in sk.items():
                if isinstance(v, list):
                    comp_text_parts.extend(str(item) for item in v)
                elif v:
                    comp_text_parts.append(str(v))
        comp_full_text = " ".join(comp_text_parts)
        self._scope_to_text["competencies"] = comp_full_text
        self._scope_to_text["skills"] = comp_full_text

        # Map claims from evidence_index if available
        if self.evidence_index:
            for c in self.evidence_index.claims:
                if c.claim_id:
                    if c.source_path.startswith("experience["):
                        m_idx = re.search(r"experience\[(\d+)\]", c.source_path)
                        if m_idx:
                            exp_scope_key = f"experience[{m_idx.group(1)}]"
                            self._claim_id_to_scope[c.claim_id] = exp_scope_key
                            if exp_scope_key in self._scope_to_text and c.text not in self._scope_to_text[exp_scope_key]:
                                self._scope_to_text[exp_scope_key] += " " + c.text
                    elif c.source_path.startswith("projects["):
                        m_idx = re.search(r"projects\[(\d+)\]", c.source_path)
                        if m_idx:
                            proj_scope_key = f"projects[{m_idx.group(1)}]"
                            self._claim_id_to_scope[c.claim_id] = proj_scope_key
                            if proj_scope_key in self._scope_to_text and c.text not in self._scope_to_text[proj_scope_key]:
                                self._scope_to_text[proj_scope_key] += " " + c.text
                    elif c.source_path.startswith("competencies") or c.source_path.startswith("skills"):
                        self._claim_id_to_scope[c.claim_id] = "competencies"

        # 6. Publications
        for pub in norm_profile.get("publications", []):
            if isinstance(pub, dict):
                p_text = f"{pub.get('title', '')} {pub.get('highlight', '')}"
                self._extract_and_index_text_metrics(p_text, "publications")

        # 7. Constraints / Compute Floor
        constraints = self.master_profile.get("constraints_and_assumptions", {}) or norm_profile.get("constraints_and_assumptions", {})

        if isinstance(constraints, dict):
            compute_floor = constraints.get("compute_floor", "")
            if compute_floor:
                self._extract_and_index_text_metrics(compute_floor, "constraints:compute_floor")

    def _extract_keywords(self, text: str) -> Set[str]:
        """Extracts searchable tokens from text."""
        tokens = set(re.findall(r"[A-Za-z0-9_+-]+|[\u4e00-\u9fa5]{2,4}", text))
        return {t.lower() for t in tokens if len(t) > 1}

    def _index_verified_metrics_dict(
        self, verified_metrics: Dict[str, Any], claim_id: str, context_keywords: Set[str]
    ) -> None:
        """Indexes explicit verified_metrics key-values into structured anchors using declarative pattern matching."""
        pct_rule_topics = [
            ("mfu", "mfu", {"mfu", "flops", "utilization", "利用率", "算力利用率"}),
            ("uptime", "uptime", {"uptime", "可用率", "训练可用率", "在线率"}),
            ("availability", "uptime", {"uptime", "可用率", "训练可用率", "在线率"}),
            ("cost", "cost_reduction", {"成本", "降本", "cost", "单token"}),
            ("latency", "latency_reduction", {"延迟", "latency", "p99", "p99延迟"}),
            ("vram", "vram_reduction", {"显存", "vram", "显存消耗", "memory"}),
            ("memory", "vram_reduction", {"显存", "vram", "显存消耗", "memory"}),
            ("gsm8k", "gsm8k_gain", {"gsm8k", "数学", "推理", "准确率"}),
            ("math", "math_gain", {"math", "代码推理", "准确率"}),
        ]

        for key, val in verified_metrics.items():
            val_str = str(val).strip()

            # Cluster size
            if "cluster" in key or key == "cluster_size":
                m = re.search(r"(\d+)", val_str)
                if m:
                    num = float(m.group(1))
                    self._add_anchor(claim_id, key, "cluster_size", context_keywords | {"卡", "gpu", "gpus", "h800", "h100", "集群", "cluster", "node", "节点"}, num, f"{int(num)} 卡", "卡", "cluster_size")

            # Downtime
            elif "downtime" in key:
                if "before" in key:
                    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:小时|h|hours?)", val_str, re.IGNORECASE)
                    if m:
                        num = float(m.group(1))
                        self._add_anchor(claim_id, key, "downtime_before", context_keywords | {"downtime", "中断", "故障", "有效中断", "日均中断", "慢卡", "慢节点"}, num, f"{num} 小时", "小时", "time_hours")
                else:
                    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:分钟|min|minutes?)", val_str, re.IGNORECASE)
                    if m:
                        num = float(m.group(1))
                        self._add_anchor(claim_id, key, "downtime_after", context_keywords | {"downtime", "中断", "故障", "压减至", "以内"}, num, f"{num} 分钟", "分钟", "time_minutes")

            # Currency savings
            elif "savings" in key or "annual_savings" in key:
                raw_num = val_str.replace(",", "").strip()
                m_curr = re.search(r"(\d+(?:\.\d+)?)\s*(万元|万|亿元|M\s*RMB|m\s*rmb|million\s*rmb|RMB|usd|美元)?", raw_num, re.IGNORECASE)
                if m_curr:
                    amount = float(m_curr.group(1))
                    curr_unit = (m_curr.group(2) or "").strip().lower()
                    if "亿" in curr_unit:
                        baseline_wan = amount * 10000.0
                    elif "million" in curr_unit or "m rmb" in curr_unit or curr_unit.startswith("m"):
                        baseline_wan = amount * 100.0
                    elif "万" in curr_unit:
                        baseline_wan = amount
                    elif amount >= 10000.0:
                        baseline_wan = amount / 10000.0
                    else:
                        baseline_wan = amount

                    self._add_anchor(claim_id, key, "savings", context_keywords | {"节省", "降本", "成本", "开销", "savings", "cost", "算力开销", "云算力", "万元"}, baseline_wan, f"{int(baseline_wan) if baseline_wan.is_integer() else baseline_wan} 万元", "万元", "currency")
                    self.all_verified_numbers.add(amount)
                    if baseline_wan > 0:
                        self.all_verified_numbers.add(baseline_wan * 10000.0)
                        self.all_verified_numbers.add(baseline_wan / 100.0)

            # TTFT
            elif "ttft" in key:
                if "before" in key:
                    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:秒|s|sec)", val_str, re.IGNORECASE)
                    if m:
                        num = float(m.group(1))
                        self._add_anchor(claim_id, key, "ttft_before", context_keywords | {"ttft", "首字", "首字响应", "首字延迟"}, num, f"{num}s", "s", "time_s")
                else:
                    m = re.search(r"(\d+(?:\.\d+)?)\s*ms", val_str, re.IGNORECASE)
                    if m:
                        num = float(m.group(1))
                        self._add_anchor(claim_id, key, "ttft_after", context_keywords | {"ttft", "首字", "首字响应", "首字延迟"}, num, f"{int(num)}ms", "ms", "time_ms")

            # Time saved
            elif "time" in key:
                m = re.search(r"(\d+)\s*(?:周|weeks?)", val_str, re.IGNORECASE)
                if m:
                    num = float(m.group(1))
                    self._add_anchor(claim_id, key, "time_saved", context_keywords | {"提前", "节省时间", "周", "weeks", "里程碑"}, num, f"{int(num)} 周", "周", "time_weeks")

            # Model params
            elif "model_params" in key or "params" in key:
                for pm in re.finditer(r"(\d+)\s*[bB]", val_str):
                    p_num = float(pm.group(1))
                    self._add_anchor(claim_id, f"model_param_{int(p_num)}B", "model_params", context_keywords | {"参数", "dense", "moe", "基座大模型"}, p_num, f"{int(p_num)}B", "B", "model_param")

            # General percentage metrics
            else:
                for trigger_key, topic, kw in pct_rule_topics:
                    if trigger_key in key:
                        m = re.search(r"(\d+(?:\.\d+)?)\s*%", val_str)
                        if m:
                            num = float(m.group(1))
                            subtopic = f"{topic}_{'before' if 'before' in key else 'after'}" if "before" in key or "after" in key else None
                            self._add_anchor(claim_id, key, topic, context_keywords | kw, num, f"{num}%", "%", "percentage", subtopic=subtopic)
                            break

    def _add_anchor(
        self,
        claim_id: str,
        key: str,
        topic: str,
        keywords: Set[str],
        baseline_value: float,
        baseline_raw: str,
        unit: str,
        metric_type: str,
        subtopic: Optional[str] = None,
    ) -> None:
        anchor: Dict[str, Any] = {
            "anchor_id": f"{claim_id}:{key}",
            "topic": topic,
            "keywords": list(keywords),
            "baseline_value": baseline_value,
            "baseline_raw": baseline_raw,
            "unit": unit,
            "metric_type": metric_type,
        }
        if subtopic:
            anchor["subtopic"] = subtopic
        self.baseline_anchors.append(anchor)
        self.all_verified_numbers.add(baseline_value)

    def _extract_and_index_text_metrics(
        self, text: str, source_id: str, extra_keywords: Optional[Set[str]] = None
    ) -> None:
        """Scans arbitrary narrative or description text to index all verified numbers."""
        kw = self._extract_keywords(text)
        if extra_keywords:
            kw.update(extra_keywords)

        extracted = self._extract_raw_metrics_from_text(text)
        for m in extracted:
            self.all_verified_numbers.add(m["value"])
            if m.get("type") == "currency":
                unit_l = (m.get("unit") or "").lower()
                if "万" in unit_l:
                    self.all_verified_numbers.add(m["value"] * 10000.0)
                elif "亿" in unit_l:
                    self.all_verified_numbers.add(m["value"] * 100000000.0)
            self.baseline_anchors.append({
                "anchor_id": f"{source_id}:{m['raw']}",
                "topic": m.get("type", "generic"),
                "keywords": list(kw),
                "baseline_value": m["value"],
                "baseline_raw": m["raw"],
                "unit": m.get("unit", ""),
                "metric_type": m.get("type", "generic")
            })

    def _extract_raw_metrics_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts all quantified numerical metrics from a text string using regex.
        Filters out non-metric technical identifiers (C++20, FlashAttention-2, ZeRO-3, etc.).
        Delegates to MetricPatternRegistry.extract_raw_metrics (SSOT).
        """
        return MetricPatternRegistry.extract_raw_metrics(text)


    def _resolve_scope_key(
        self,
        target_scope: Optional[Union[str, dict, int]] = None,
        target_claim_id: Optional[str] = None,
    ) -> Optional[str]:
        """Resolves target_scope or target_claim_id to a canonical scope key (e.g. 'experience[0]', 'projects[1]')."""
        if target_scope is not None:
            if isinstance(target_scope, int):
                return f"experience[{target_scope}]"
            if isinstance(target_scope, str):
                ts = target_scope.strip()
                m_exp = re.match(r"^experience\[(\d+)\]", ts)
                m_proj = re.match(r"^projects\[(\d+)\]", ts)
                if m_exp:
                    return f"experience[{m_exp.group(1)}]"
                if m_proj:
                    return f"projects[{m_proj.group(1)}]"
                if ts.lower() in self._company_to_exp_idx:
                    return f"experience[{self._company_to_exp_idx[ts.lower()]}]"
                if ts.lower() in self._project_name_to_proj_idx:
                    return f"projects[{self._project_name_to_proj_idx[ts.lower()]}]"
                if ts in self._claim_id_to_scope:
                    return self._claim_id_to_scope[ts]
            elif isinstance(target_scope, dict):
                sub_scope = target_scope.get("target_scope")
                if sub_scope:
                    return self._resolve_scope_key(sub_scope, target_claim_id)
                sp = target_scope.get("source_path", "")
                m_exp = re.search(r"experience\[(\d+)\]", sp)
                m_proj = re.search(r"projects\[(\d+)\]", sp)
                if m_exp:
                    return f"experience[{m_exp.group(1)}]"
                if m_proj:
                    return f"projects[{m_proj.group(1)}]"
                comp = target_scope.get("company") or target_scope.get("org")
                if comp and comp.lower() in self._company_to_exp_idx:
                    return f"experience[{self._company_to_exp_idx[comp.lower()]}]"
                pname = target_scope.get("name")
                if pname and pname.lower() in self._project_name_to_proj_idx:
                    return f"projects[{self._project_name_to_proj_idx[pname.lower()]}]"
                cid = target_scope.get("claim_id")
                if cid and cid in self._claim_id_to_scope:
                    return self._claim_id_to_scope[cid]

        if target_claim_id and target_claim_id in self._claim_id_to_scope:
            return self._claim_id_to_scope[target_claim_id]

        return None

    def _resolve_scope_text(
        self,
        target_scope: Optional[Union[str, dict, int]] = None,
        target_claim_id: Optional[str] = None,
        target_excerpt: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolves the textual scope for fact verification.
        Returns None if no scope restriction is specified (signaling global fallback).
        Returns the resolved scope text (which may be empty) when a scope is specified.
        """
        if target_scope is None and target_claim_id is None and target_excerpt is None:
            return None

        scope_key = self._resolve_scope_key(target_scope, target_claim_id)
        extra_texts: List[str] = []

        if target_excerpt:
            extra_texts.append(target_excerpt)

        # Handle dict target_scope extra info
        if isinstance(target_scope, dict):
            exc = target_scope.get("excerpt", "")
            if exc:
                extra_texts.append(exc)
            if not target_claim_id and target_scope.get("claim_id"):
                target_claim_id = target_scope.get("claim_id")

        # Resolve from target_claim_id if scope_key still not found
        if not scope_key and target_claim_id:
            if self.evidence_index and target_claim_id in self.evidence_index.claim_by_id:
                c = self.evidence_index.claim_by_id[target_claim_id]
                extra_texts.append(c.text)
                if c.source_path.startswith("experience["):
                    m = re.search(r"experience\[(\d+)\]", c.source_path)
                    if m:
                        scope_key = f"experience[{m.group(1)}]"
                elif c.source_path.startswith("projects["):
                    m = re.search(r"projects\[(\d+)\]", c.source_path)
                    if m:
                        scope_key = f"projects[{m.group(1)}]"

        # Resolve from target_excerpt if scope_key still not found
        if not scope_key and target_excerpt and self.evidence_index:
            for c in self.evidence_index.claims:
                if target_excerpt in c.text or c.text in target_excerpt:
                    if c.source_path.startswith("experience["):
                        m = re.search(r"experience\[(\d+)\]", c.source_path)
                        if m:
                            scope_key = f"experience[{m.group(1)}]"
                            break
                    elif c.source_path.startswith("projects["):
                        m = re.search(r"projects\[(\d+)\]", c.source_path)
                        if m:
                            scope_key = f"projects[{m.group(1)}]"
                            break

        # Fallback if target_scope was a raw descriptive string not matching any key
        if not scope_key and isinstance(target_scope, str) and target_scope:
            if target_scope not in extra_texts:
                extra_texts.append(target_scope)

        scoped_parts: List[str] = []
        if scope_key and scope_key in self._scope_to_text:
            scoped_parts.append(self._scope_to_text[scope_key])

        scoped_parts.extend(extra_texts)

        return " ".join(scoped_parts)

    def _is_term_negated_or_planned(self, term: str, text: str) -> bool:
        """
        Checks whether all occurrences of a term in text appear within
        negation or planning/hypothetical contexts.
        Returns True if the term ONLY appears in negated/planned contexts.
        Returns False if there is at least one positive, non-negated, non-planned occurrence.
        """
        if not text or not term:
            return False

        term_lower = term.lower()
        text_lower = text.lower()

        # Find all occurrences of term in text_lower
        matches: List[Tuple[int, int]] = []
        if re.search(r"^[a-z0-9_+#.-]+$", term_lower):
            for m in re.finditer(r"(?<![a-z0-9_])" + re.escape(term_lower) + r"(?![a-z0-9_])", text_lower):
                matches.append((m.start(), m.end()))
            if not matches and term_lower.startswith("c++"):
                idx = 0
                while True:
                    found = text_lower.find("c++", idx)
                    if found == -1:
                        break
                    matches.append((found, found + 3))
                    idx = found + 3
        else:
            idx = 0
            while True:
                found = text_lower.find(term_lower, idx)
                if found == -1:
                    break
                matches.append((found, found + len(term_lower)))
                idx = found + len(term_lower)

        if not matches:
            return False

        neg_prefixes = [
            r"(?:未|并未|未曾|不|没有|未能|放弃|放弃了|暂未|尚未|未考虑|未引入|未采用|未使用|不涉及)\s*$",
            r"(?:not|did\s+not|didn't|never|abandoned|without)\s+(?:use|using|adopt|adopting)?\s*$",
        ]
        neg_suffixes = [
            r"^\s*(?:[，,]?\s*(?:但|却|最终|经过评估)?(?:未|并未|没有|放弃)(?:采用|引入|使用|落地|上线|实现|通过|支持))",
            r"^\s*(?:但|却|并未|并无|并没)?(?:未采用|未引入|未使用|未落地|未上线|未考虑|未实现|未涉及|放弃|未通过|暂未|尚未)",
        ]
        plan_prefixes = [
            r"(?:计划|拟|规划|预计|待|后续计划|未来计划|计划后续|拟在|拟于|后续拟|下一阶段计划)(?:采用|引入|使用|落地|上线|实现)?\s*$",
            r"(?:plan|planned|planning|intend|intended|intending)\s+to\s+(?:use|adopt)?\s*$",
        ]
        plan_suffixes = [
            r"^\s*(?:仍在调研中|待调研|待引入|待采用|待评估|后续评估)",
        ]

        has_positive = False

        for start, end in matches:
            window_before = text_lower[max(0, start - 40):start]
            window_after = text_lower[end:min(len(text_lower), end + 40)]
            window_full = text_lower[max(0, start - 40):min(len(text_lower), end + 40)]

            is_neg_or_plan = False

            # Check prefixes
            for pat in neg_prefixes + plan_prefixes:
                if re.search(pat, window_before):
                    is_neg_or_plan = True
                    break

            # Check suffixes
            if not is_neg_or_plan:
                for pat in neg_suffixes + plan_suffixes:
                    if re.search(pat, window_after):
                        is_neg_or_plan = True
                        break

            # Check full window complex patterns
            if not is_neg_or_plan:
                if re.search(r"调研(?:了)?\s*" + re.escape(term_lower) + r"\s*[，,]?\s*(?:但|却|最终)?(?:未|并未|没有|放弃)(?:采用|引入|使用)", window_full):
                    is_neg_or_plan = True
                elif re.search(r"(?:对|针对)\s*" + re.escape(term_lower) + r"\s*(?:进行调研|进行了调研|做调研)[，,]?\s*(?:但|却)?(?:未|没有|并未)(?:采用|引入|使用)", window_full):
                    is_neg_or_plan = True

            if not is_neg_or_plan:
                has_positive = True
                break

        return not has_positive

    def verify_facts(
        self,
        tailored_text_or_dict: Union[str, dict, list],
        master_profile: Optional[dict] = None,
        target_scope: Optional[Union[str, dict, int]] = None,
        target_claim_id: Optional[str] = None,
        target_excerpt: Optional[str] = None,
    ) -> dict:
        """
        Inspects tailored resume bullets or text against master profile.

        Returns:
            dict containing:
              - passed: bool (True if zero drifts and zero ungrounded metrics)
              - score: float (0 - 100)
              - drifts: list of detected metric exaggerations (bullet, claimed_metric, verified_baseline)
              - unverified_claims: list of ungrounded numbers
              - verified_bullets: list of bullets that passed verification
              - verdict: 'FACT_CHECK_PASSED' or 'FACT_DRIFT_DETECTED'
        """
        if master_profile is not None:
            self.load_profile(master_profile)

        if not self.master_profile:
            raise ValueError("Master profile is required for fact verification.")

        drifts: List[Dict[str, Any]] = []
        unverified_claims: List[Dict[str, Any]] = []
        role_inflations: List[Dict[str, Any]] = []
        verified_bullets: List[str] = []
        total_bullets = 0

        # Structured dict input handling (when target_scope is not explicitly overriding)
        if (
            isinstance(tailored_text_or_dict, dict)
            and target_scope is None
            and target_claim_id is None
            and target_excerpt is None
            and ("experience" in tailored_text_or_dict or "projects" in tailored_text_or_dict)
        ):
            for exp_idx, exp in enumerate(tailored_text_or_dict.get("experience", [])):
                if not isinstance(exp, dict):
                    continue
                exp_scope = f"experience[{exp_idx}]"
                company = exp.get("company") or exp.get("org")
                if company and company.lower() in self._company_to_exp_idx:
                    exp_scope = f"experience[{self._company_to_exp_idx[company.lower()]}]"

                # Role hierarchy audit
                claimed_exp_role = exp.get("role") or ""
                baseline_exp_role = self._baseline_roles.get(exp_scope) or self._baseline_roles.get(company.lower() if company else "", "")
                if claimed_exp_role and baseline_exp_role:
                    r_esc = QualityRuleRegistry.check_role_escalation(claimed_exp_role, baseline_exp_role)
                    if r_esc:
                        r_esc["scope"] = exp_scope
                        r_esc["organization"] = company
                        role_inflations.append(r_esc)

                exp_bullets: List[Tuple[str, Optional[str]]] = []
                for h in exp.get("highlights", []):
                    if isinstance(h, dict):
                        if h.get("claim_zh"):
                            exp_bullets.append((h["claim_zh"], h.get("claim_id")))
                        if h.get("claim_en"):
                            exp_bullets.append((h["claim_en"], h.get("claim_id")))
                    elif isinstance(h, str):
                        exp_bullets.append((h, None))
                for b in exp.get("bullets", []):
                    b_text = b.get("text") or b.get("claim_zh") or b.get("claim_en") if isinstance(b, dict) else str(b)
                    if b_text:
                        exp_bullets.append((b_text, None))

                for b_text, cid in exp_bullets:
                    b_clean = b_text.strip()
                    if not b_clean:
                        continue
                    total_bullets += 1
                    b_drifts, b_unverified = self._verify_single_bullet(
                        b_clean,
                        target_scope=exp_scope,
                        target_claim_id=cid,
                    )
                    if b_drifts:
                        drifts.extend(b_drifts)
                    if b_unverified:
                        unverified_claims.extend(b_unverified)
                    if not b_drifts and not b_unverified:
                        verified_bullets.append(b_clean)

            for p_idx, proj in enumerate(tailored_text_or_dict.get("projects", [])):
                if not isinstance(proj, dict):
                    continue
                proj_scope = f"projects[{p_idx}]"
                p_name = proj.get("name")
                if p_name and p_name.lower() in self._project_name_to_proj_idx:
                    proj_scope = f"projects[{self._project_name_to_proj_idx[p_name.lower()]}]"

                # Role hierarchy audit
                claimed_proj_role = proj.get("role") or ""
                baseline_proj_role = self._baseline_roles.get(proj_scope) or self._baseline_roles.get(p_name.lower() if p_name else "", "")
                if claimed_proj_role and baseline_proj_role:
                    p_esc = QualityRuleRegistry.check_role_escalation(claimed_proj_role, baseline_proj_role)
                    if p_esc:
                        p_esc["scope"] = proj_scope
                        p_esc["project"] = p_name
                        role_inflations.append(p_esc)

                p_bullets: List[str] = []
                for k in ["description_zh", "description_en", "description"]:
                    if proj.get(k):
                        p_bullets.append(proj[k])
                for b in proj.get("bullets", []):
                    b_text = b.get("text") or b.get("claim_zh") if isinstance(b, dict) else str(b)
                    if b_text:
                        p_bullets.append(b_text)

                for b_text in p_bullets:
                    b_clean = b_text.strip()
                    if not b_clean:
                        continue
                    total_bullets += 1
                    b_drifts, b_unverified = self._verify_single_bullet(
                        b_clean,
                        target_scope=proj_scope,
                    )
                    if b_drifts:
                        drifts.extend(b_drifts)
                    if b_unverified:
                        unverified_claims.extend(b_unverified)
                    if not b_drifts and not b_unverified:
                        verified_bullets.append(b_clean)

            narrative = tailored_text_or_dict.get("narrative", {})
            if isinstance(narrative, dict):
                for k in ["summary_zh", "summary_en"]:
                    if narrative.get(k):
                        total_bullets += 1
                        b_clean = narrative[k].strip()
                        b_drifts, b_unverified = self._verify_single_bullet(
                            b_clean,
                            target_scope="narrative",
                        )
                        if b_drifts:
                            drifts.extend(b_drifts)
                        if b_unverified:
                            unverified_claims.extend(b_unverified)
                        if not b_drifts and not b_unverified:
                            verified_bullets.append(b_clean)

            passed = (len(drifts) == 0 and len(unverified_claims) == 0 and len(role_inflations) == 0)
            verdict = "FACT_CHECK_PASSED" if passed else "FACT_DRIFT_DETECTED"
            score = 100.0
            if not passed:
                penalty = len(drifts) * 25.0 + len(unverified_claims) * 15.0 + len(role_inflations) * 20.0
                score = max(0.0, round(100.0 - penalty, 1))

            return {
                "passed": passed,
                "score": score,
                "drifts": drifts,
                "unverified_claims": unverified_claims,
                "role_inflations": role_inflations,
                "verified_bullets": verified_bullets,
                "verdict": verdict,
                "summary": {
                    "total_bullets_checked": total_bullets,
                    "verified_bullets_count": len(verified_bullets),
                    "drift_count": len(drifts),
                    "unverified_claims_count": len(unverified_claims),
                    "role_inflation_count": len(role_inflations),
                }
            }

        bullets = self._extract_bullets(tailored_text_or_dict)

        for bullet in bullets:
            bullet_clean = bullet.strip()
            if not bullet_clean:
                continue

            bullet_drifts, bullet_unverified = self._verify_single_bullet(
                bullet_clean,
                target_scope=target_scope,
                target_claim_id=target_claim_id,
                target_excerpt=target_excerpt,
            )

            if bullet_drifts:
                drifts.extend(bullet_drifts)
            if bullet_unverified:
                unverified_claims.extend(bullet_unverified)

            if not bullet_drifts and not bullet_unverified:
                verified_bullets.append(bullet_clean)

        passed = (len(drifts) == 0 and len(unverified_claims) == 0 and len(role_inflations) == 0)
        verdict = "FACT_CHECK_PASSED" if passed else "FACT_DRIFT_DETECTED"

        score = 100.0
        if not passed:
            penalty = len(drifts) * 25.0 + len(unverified_claims) * 15.0 + len(role_inflations) * 20.0
            score = max(0.0, round(100.0 - penalty, 1))

        return {
            "passed": passed,
            "score": score,
            "drifts": drifts,
            "unverified_claims": unverified_claims,
            "role_inflations": role_inflations,
            "verified_bullets": verified_bullets,
            "verdict": verdict,
            "summary": {
                "total_bullets_checked": len(bullets),
                "verified_bullets_count": len(verified_bullets),
                "drift_count": len(drifts),
                "unverified_claims_count": len(unverified_claims),
                "role_inflation_count": len(role_inflations),
            }
        }

    def verify_role_hierarchy(self, claimed_role: str, baseline_role: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Verifies whether a claimed job/project role title suffers from title inflation,
        tier escalation, or domain drift relative to the baseline role.
        """
        if not baseline_role:
            return None
        return QualityRuleRegistry.check_role_escalation(claimed_role, baseline_role)

    def verify_metric_scope(self, claimed_text: str, baseline_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Verifies whether quantified metrics in claimed_text suffer from scope drift,
        entity substitution, ungrounded currency conversion, or unanchored denominators
        relative to baseline_text.
        """
        if baseline_text is None:
            baseline_text = getattr(self, "profile_all_text", "")
        return QualityRuleRegistry.check_metric_scope_drift(claimed_text, baseline_text)

    def verify_bullet(
        self,
        bullet: str,
        target_scope: Optional[Union[str, dict, int]] = None,
        target_claim_id: Optional[str] = None,
        target_excerpt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verifies a single bullet point with optional scope restriction.

        Args:
            bullet: The bullet point text to verify.
            target_scope: Scope identifier (e.g. 'experience[0]', 'projects[1]', company name, project name, or dict).
            target_claim_id: Target claim ID (e.g. 'EXP-0', 'experience[0].bullets[0]').
            target_excerpt: Target excerpt from profile baseline.

        Returns:
            dict containing:
              - passed: bool
              - score: float
              - drifts: list of metric drifts
              - unverified_claims: list of ungrounded metrics or tech/method claims
              - bullet: str
              - verdict: 'FACT_CHECK_PASSED' or 'FACT_DRIFT_DETECTED'
        """
        bullet_clean = bullet.strip()
        drifts, unverified = self._verify_single_bullet(
            bullet_clean,
            target_scope=target_scope,
            target_claim_id=target_claim_id,
            target_excerpt=target_excerpt,
        )
        passed = (len(drifts) == 0 and len(unverified) == 0)
        verdict = "FACT_CHECK_PASSED" if passed else "FACT_DRIFT_DETECTED"
        score = 100.0
        if not passed:
            penalty = len(drifts) * 25.0 + len(unverified) * 15.0
            score = max(0.0, round(100.0 - penalty, 1))

        return {
            "passed": passed,
            "score": score,
            "drifts": drifts,
            "unverified_claims": unverified,
            "bullet": bullet_clean,
            "verdict": verdict,
        }

    def _verify_single_bullet(
        self,
        bullet: str,
        target_scope: Optional[Union[str, dict, int]] = None,
        target_claim_id: Optional[str] = None,
        target_excerpt: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Verifies all numerical assertions and tech/method grounding in a single bullet point against SSOT baseline."""
        bullet_drifts: List[Dict[str, Any]] = []
        bullet_unverified: List[Dict[str, Any]] = []

        # 1. Numerical metrics verification
        metrics = self._extract_raw_metrics_from_text(bullet)
        for met in metrics:
            val = met["value"]
            raw_str = met["raw"]
            met_type = met.get("type", "")

            anchor = self._find_matching_anchor(
                met,
                bullet,
                target_scope=target_scope,
                target_claim_id=target_claim_id,
                target_excerpt=target_excerpt,
            )

            if anchor is not None:
                is_drift, baseline_str = self._check_metric_drift(met, anchor)
                if is_drift:
                    bullet_drifts.append({
                        "bullet": bullet,
                        "claimed_metric": raw_str,
                        "verified_baseline": baseline_str,
                        "metric_type": anchor.get("topic", met_type)
                    })
            else:
                # No anchored baseline found for this metric -> UNVERIFIED_NUMERICAL_CLAIM
                bullet_unverified.append({
                    "bullet": bullet,
                    "claimed_metric": raw_str,
                    "reason": "Numerical metric has no corresponding anchor in SSOT profile"
                })

        # 2. Non-metric tech & method grounding verification
        tech_method_drifts = self._verify_tech_and_method_grounding(
            bullet,
            target_scope=target_scope,
            target_claim_id=target_claim_id,
            target_excerpt=target_excerpt,
        )
        if tech_method_drifts:
            bullet_unverified.extend(tech_method_drifts)

        # 3. Metric scope, entity & dimension drift verification
        b_scope_text = ""
        if target_scope is not None or target_claim_id is not None or target_excerpt is not None:
            resolved = self._resolve_scope_text(target_scope, target_claim_id, target_excerpt)
            b_scope_text = resolved or ""
        if not b_scope_text:
            b_scope_text = getattr(self, "profile_all_text", "")

        scope_drifts = QualityRuleRegistry.check_metric_scope_drift(bullet, b_scope_text)
        if scope_drifts:
            for s in scope_drifts:
                bullet_drifts.append({
                    "bullet": bullet,
                    "claimed_metric": s.get("claimed_snippet") or s.get("number") or "scope_drift",
                    "verified_baseline": s.get("reason", "Metric scope drift"),
                    "metric_type": s.get("type", "METRIC_SCOPE_DRIFT"),
                    "rule_id": s.get("rule_id", "SCOPE_DRIFT"),
                    "fix_suggestion": s.get("fix_suggestion", "")
                })

        return bullet_drifts, bullet_unverified

    def _extract_tech_and_method_terms(self, bullet: str) -> List[str]:
        """
        Extracts technical stack names and method/technique terms from a bullet.
        """
        extracted: List[str] = []
        bullet_lower = bullet.lower()

        # 1. Match from KNOWN_METHOD_TERMS (sort by length descending to prioritize longer phrases)
        sorted_methods = sorted(KNOWN_METHOD_TERMS, key=len, reverse=True)
        for method in sorted_methods:
            if re.search(r"[\u4e00-\u9fa5]", method):
                if method in bullet_lower:
                    idx = bullet_lower.find(method)
                    extracted.append(bullet[idx:idx + len(method)])
            else:
                m = re.search(r"(?<![a-z0-9_])" + re.escape(method) + r"(?![a-z0-9_])", bullet_lower)
                if m:
                    extracted.append(bullet[m.start():m.end()])

        # 2. Match from KNOWN_TECH_TERMS
        sorted_techs = sorted(KNOWN_TECH_TERMS, key=len, reverse=True)
        for tech in sorted_techs:
            if re.search(r"[\u4e00-\u9fa5]", tech):
                if tech in bullet_lower:
                    idx = bullet_lower.find(tech)
                    extracted.append(bullet[idx:idx + len(tech)])
            else:
                m = re.search(r"(?<![a-z0-9_])" + re.escape(tech) + r"(?![a-z0-9_])", bullet_lower)
                if m:
                    extracted.append(bullet[m.start():m.end()])

        # 3. Extract English / alphanumeric technical identifiers
        # For Chinese bullets with embedded English tech words, extract candidate tokens.
        # For pure English bullets, only extract known tech terms, uppercase acronyms (>=2 caps), or PascalCase/CamelCase identifiers.
        is_chinese_bullet = bool(re.search(r"[\u4e00-\u9fa5]", bullet))
        for m in re.finditer(r"\b[A-Za-z][A-Za-z0-9_+#.-]*[A-Za-z0-9+#]\b", bullet):
            raw = m.group(0)
            raw_l = raw.lower()
            if raw_l in EXCLUDED_ENGLISH_WORDS:
                continue
            if is_chinese_bullet:
                extracted.append(raw)
            else:
                if (raw_l in KNOWN_TECH_TERMS or raw_l in KNOWN_METHOD_TERMS or
                    (len(raw) >= 2 and raw.isupper()) or
                    (re.match(r"^[A-Z][a-z]+[A-Z]", raw)) or
                    any(c in raw for c in ["+", "#", "."])):
                    extracted.append(raw)

        # 4. Deduplicate terms (case-insensitive, prefer longer terms over their substrings)
        deduped: List[str] = []
        extracted_sorted = sorted(set(extracted), key=lambda x: len(x), reverse=True)
        for term in extracted_sorted:
            term_l = term.lower()
            if any(term_l in d.lower() and term_l != d.lower() for d in deduped):
                continue
            deduped.append(term)

        return deduped

    def _is_term_grounded(
        self,
        term: str,
        target_scope: Optional[Union[str, dict, int]] = None,
        target_claim_id: Optional[str] = None,
        target_excerpt: Optional[str] = None,
        scope_text: Optional[str] = None,
    ) -> bool:
        """
        Checks if a technology or method term is grounded in candidate SSOT profile.
        When target_scope, target_claim_id, target_excerpt, or scope_text is provided,
        verification is strictly restricted to that scope.
        When no scope is specified, falls back to global profile_all_text.
        Negated or planned-only terms are rejected.
        """
        if not self.master_profile:
            return False

        if scope_text is not None:
            profile_text = scope_text.lower()
        elif target_scope is not None or target_claim_id is not None or target_excerpt is not None:
            resolved = self._resolve_scope_text(target_scope, target_claim_id, target_excerpt)
            profile_text = (resolved or "").lower()
        else:
            profile_text = getattr(self, "profile_all_text", "")

        if not profile_text:
            return False

        term_lower = term.lower()
        matched = False

        # 1. Check via AliasRegistry
        canonical = AliasRegistry.get_canonical(term_lower)
        aliases = AliasRegistry.get_aliases(canonical) | {canonical, term_lower}
        for a in aliases:
            if re.search(r"(?<![a-z0-9_])" + re.escape(a) + r"(?![a-z0-9_])", profile_text):
                matched = True
                break
            if re.search(r"[\u4e00-\u9fa5]", a) and a in profile_text:
                matched = True
                break

        # 2. Check general word boundary for English/alphanumeric terms
        if not matched:
            if re.search(r"^[a-z0-9_+#.-]+$", term_lower):
                if re.search(r"(?<![a-z0-9_])" + re.escape(term_lower) + r"(?![a-z0-9_])", profile_text):
                    matched = True
                elif term_lower.startswith("c++") and "c++" in profile_text:
                    matched = True

        # 3. Check substring for Chinese terms
        if not matched:
            if re.search(r"[\u4e00-\u9fa5]", term_lower) and term_lower in profile_text:
                matched = True

        if not matched:
            return False

        # 4. Ensure term is not purely in a negated or planning/hypothetical context
        if self._is_term_negated_or_planned(term_lower, profile_text):
            return False

        return True

    def _verify_tech_and_method_grounding(
        self,
        bullet: str,
        target_scope: Optional[Union[str, dict, int]] = None,
        target_claim_id: Optional[str] = None,
        target_excerpt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extracts technology and method terms from bullet and verifies they exist in SSOT profile.
        Returns a list of ungrounded tech/method claims.
        """
        ungrounded: List[Dict[str, Any]] = []
        extracted_terms = self._extract_tech_and_method_terms(bullet)

        for term in extracted_terms:
            if not self._is_term_grounded(
                term,
                target_scope=target_scope,
                target_claim_id=target_claim_id,
                target_excerpt=target_excerpt,
            ):
                ungrounded.append({
                    "bullet": bullet,
                    "claimed_metric": term,
                    "claimed_fact": term,
                    "claim_type": "tech_method",
                    "reason": f"Technology or method '{term}' has no factual anchor in candidate SSOT profile",
                })
        return ungrounded

    def _find_matching_anchor(
        self,
        metric: Dict[str, Any],
        bullet_text: str,
        target_scope: Optional[Union[str, dict, int]] = None,
        target_claim_id: Optional[str] = None,
        target_excerpt: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the corresponding SSOT anchor for a metric using local window context and type checking.
        When target_scope or target_claim_id is provided, restricts anchors to the specified scope.
        """
        met_type = metric.get("type", "")
        allowed_topics = METRIC_TYPE_TO_TOPICS.get(met_type, set())
        if not allowed_topics:
            return None

        # Resolve scope_key if provided
        scope_key = self._resolve_scope_key(target_scope, target_claim_id)

        # Extract local context around metric
        start = metric.get("start", 0)
        end = metric.get("end", len(bullet_text))
        window_start = max(0, start - 30)
        window_end = min(len(bullet_text), end + 30)
        local_window = bullet_text[window_start:window_end].lower()
        bullet_lower = bullet_text.lower()

        # Immediate prefix window (preceding 15 chars) to determine before vs after direction
        prefix_window = bullet_text[max(0, start - 15):start].lower()

        is_before_context = bool(re.search(r"(?:从|起始|from)\s*$", prefix_window))
        is_after_context = bool(re.search(r"(?:至|到|压减至|优化至|提升至|达到|下降至|boost|to)\s*$", prefix_window))

        best_anchor = None
        best_score = 0

        for anchor in self.baseline_anchors:
            topic = anchor.get("topic", "")
            if topic not in allowed_topics:
                continue

            # Scope filtering: if scope_key is set, restrict non-candidate anchors to that scope
            if scope_key:
                anchor_id = anchor.get("anchor_id", "")
                is_cand = (
                    anchor_id.startswith("candidate:")
                    or anchor_id.startswith("constraints:")
                    or anchor.get("topic") == "experience_years"
                )
                if not is_cand:
                    if scope_key.startswith("experience["):
                        m_exp = re.search(r"experience\[(\d+)\]", scope_key)
                        if m_exp:
                            exp_idx = m_exp.group(1)
                            exp_patterns = [f"experience[{exp_idx}]", f"EXP-{exp_idx}"]
                            if not any(p in anchor_id for p in exp_patterns):
                                continue
                    elif scope_key.startswith("projects["):
                        m_proj = re.search(r"projects\[(\d+)\]", scope_key)
                        if m_proj:
                            p_idx = int(m_proj.group(1))
                            p_patterns = [f"projects[{p_idx}]"]
                            if self.master_profile and "projects" in self.master_profile:
                                projs = self.master_profile["projects"]
                                if 0 <= p_idx < len(projs) and isinstance(projs[p_idx], dict):
                                    p_name = projs[p_idx].get("name")
                                    if p_name:
                                        p_patterns.append(p_name)
                            if not any(p in anchor_id for p in p_patterns):
                                continue

            score = 1  # Base score for matching type

            # Keyword matching in local window and full bullet
            anchor_kw = anchor.get("keywords", [])
            for kw in anchor_kw:
                kw_l = kw.lower()
                if kw_l in local_window:
                    score += 5
                elif kw_l in bullet_lower:
                    score += 2

            # Subtopic discrimination for before vs after
            subtopic = anchor.get("subtopic")
            if subtopic == "mfu_before":
                if is_before_context:
                    score += 15
                elif is_after_context:
                    score -= 10
            elif subtopic == "mfu_after":
                if is_after_context:
                    score += 15
                elif is_before_context:
                    score -= 10
            elif topic == "downtime_before":
                if is_before_context:
                    score += 15
                elif is_after_context:
                    score -= 10
            elif topic == "downtime_after":
                if is_after_context:
                    score += 15
                elif is_before_context:
                    score -= 10
            elif topic == "ttft_before":
                if is_before_context:
                    score += 15
                elif is_after_context:
                    score -= 10
            elif topic == "ttft_after":
                if is_after_context:
                    score += 15
                elif is_before_context:
                    score -= 10

            # Specific topic keywords affinity
            if met_type == "percentage":
                if "gsm8k" in local_window and topic == "gsm8k_gain":
                    score += 20
                elif "math" in local_window and topic == "math_gain":
                    score += 20
                elif ("显存" in local_window or "vram" in local_window) and topic == "vram_reduction":
                    score += 20
                elif ("p99" in local_window or "延迟" in local_window) and topic == "latency_reduction":
                    score += 20
                elif ("单token" in local_window or "成本" in local_window) and topic == "cost_reduction":
                    score += 20
                elif ("可用率" in local_window or "uptime" in local_window) and topic == "uptime":
                    score += 20
                elif "mfu" in local_window and topic == "mfu":
                    score += 20

            # Unit match bonus
            if metric.get("unit") and metric.get("unit") == anchor.get("unit"):
                score += 3

            if score > best_score:
                best_score = score
                best_anchor = anchor

        return best_anchor if best_score >= 3 else None

    def _check_metric_drift(
        self, claimed_metric: Dict[str, Any], anchor: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Determines whether claimed metric represents an inflation drift."""
        claimed_val = claimed_metric["value"]
        baseline_val = anchor["baseline_value"]
        baseline_raw = anchor.get("baseline_raw", str(baseline_val))
        topic = anchor.get("topic", "")

        # Currency unit normalization
        c_unit = (claimed_metric.get("unit") or "").lower()
        b_unit = (anchor.get("unit") or "").lower()

        b_is_wan = ("万" in b_unit)
        c_is_wan = ("万" in c_unit)
        b_is_yi = ("亿" in b_unit)
        c_is_yi = ("亿" in c_unit)

        if b_is_wan and not c_is_wan and not c_is_yi:
            # baseline is 万元, claimed is raw RMB / 元
            baseline_comp = baseline_val * 10000.0
            claimed_comp = claimed_val
        elif c_is_wan and not b_is_wan and not b_is_yi:
            # claimed is 万元, baseline is raw RMB / 元
            baseline_comp = baseline_val
            claimed_comp = claimed_val * 10000.0
        elif b_is_yi and not c_is_yi:
            # baseline is 亿元
            baseline_comp = baseline_val * 100000000.0
            claimed_comp = claimed_val if not c_is_wan else claimed_val * 10000.0
        elif c_is_yi and not b_is_yi:
            # claimed is 亿元
            baseline_comp = baseline_val if not b_is_wan else baseline_val * 10000.0
            claimed_comp = claimed_val * 100000000.0
        else:
            baseline_comp = baseline_val
            claimed_comp = claimed_val

        # Allow small floating point rounding tolerance
        if abs(claimed_comp - baseline_comp) < 0.2:
            return False, baseline_raw

        # Model params: check if exact match or exceeding verified max
        if topic == "model_params":
            if abs(claimed_comp - baseline_comp) < 0.2:
                return False, baseline_raw
            matched_param = any(
                a.get("topic") == "model_params" and abs(a.get("baseline_value", 0) - claimed_comp) < 0.2
                for a in self.baseline_anchors
            )
            if matched_param:
                return False, baseline_raw
            if claimed_comp > baseline_comp:
                return True, baseline_raw

        # MFU
        elif topic == "mfu":
            if claimed_comp > baseline_comp + 0.2:
                return True, baseline_raw

        # Cluster size
        elif topic == "cluster_size":
            if claimed_comp > baseline_comp:
                return True, baseline_raw

        # Downtime before
        elif topic == "downtime_before":
            if claimed_comp > baseline_comp:
                return True, baseline_raw

        # Downtime after
        elif topic == "downtime_after":
            # If claimed downtime after is worse than baseline (e.g. baseline 8 min, claimed 20 min)
            if claimed_comp > baseline_comp:
                return True, baseline_raw

        # Annual Savings
        elif topic == "savings":
            if claimed_comp > baseline_comp:
                return True, baseline_raw

        # Percentage reductions / gains
        elif topic in ("latency_reduction", "cost_reduction", "vram_reduction", "gsm8k_gain", "math_gain", "uptime", "percentage", "generic"):
            if claimed_comp > baseline_comp + 0.2:
                return True, baseline_raw

        # Experience years & stars
        elif topic in ("experience_years", "stars"):
            if claimed_comp > baseline_comp:
                return True, baseline_raw

        elif claimed_comp > baseline_comp:
            return True, baseline_raw

        return False, baseline_raw

    def _extract_bullets(self, tailored_text_or_dict: Union[str, dict, list]) -> List[str]:
        """Extracts individual bullet lines from string, dict, or list input."""
        bullets: List[str] = []

        if isinstance(tailored_text_or_dict, list):
            for item in tailored_text_or_dict:
                bullets.extend(self._extract_bullets(item))
            return bullets

        if isinstance(tailored_text_or_dict, dict):
            if "bullets" in tailored_text_or_dict and isinstance(tailored_text_or_dict["bullets"], list):
                return self._extract_bullets(tailored_text_or_dict["bullets"])

            for exp in tailored_text_or_dict.get("experience", []):
                if isinstance(exp, dict):
                    for h in exp.get("highlights", []):
                        if isinstance(h, dict):
                            if h.get("claim_zh"):
                                bullets.append(h["claim_zh"])
                            if h.get("claim_en"):
                                bullets.append(h["claim_en"])
                        elif isinstance(h, str):
                            bullets.append(h)

            narrative = tailored_text_or_dict.get("narrative", {})
            if isinstance(narrative, dict):
                for k in ["summary_zh", "summary_en"]:
                    if narrative.get(k):
                        bullets.append(narrative[k])

            for p in tailored_text_or_dict.get("projects", []):
                if isinstance(p, dict):
                    for k in ["description_zh", "description_en"]:
                        if p.get(k):
                            bullets.append(p[k])

            return bullets

        # Plain text or markdown
        text = str(tailored_text_or_dict).strip()
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            clean = re.sub(r"^[-*•·▪▫►✔✓\d\.\)]+\s*", "", s).strip()
            if clean:
                bullets.append(clean)

        return bullets

    def audit_claims(
        self,
        tailored_text_or_dict: Union[str, dict, list],
        subject_name: Optional[str] = None,
    ) -> Any:
        """
        Audits resume text or dictionary into a schema-compliant typed AuditReport.
        Reuses existing SSOT profile / ProfileContext without secondary normalization.
        """
        from core.evidence.auditor import EvidenceAuditor

        auditor = EvidenceAuditor(self.profile_context or self.evidence_index or self.master_profile)
        return auditor.audit(tailored_text_or_dict, subject_name=subject_name)

    def generate_audit_report(
        self,
        tailored_text_or_dict: Union[str, dict, list],
        subject_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Audits resume text or dictionary and returns a JSON-serializable report dictionary
        strictly complying with OfferGet report schema.
        """
        report = self.audit_claims(tailored_text_or_dict, subject_name=subject_name)
        return report.to_dict()

    def generate_audit_report_html(
        self,
        tailored_text_or_dict: Union[str, dict, list],
        subject_name: Optional[str] = None,
        template_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Audits resume text or dictionary and returns an interactive, styled HTML audit report string.
        """
        from core.evidence.report_renderer import render_audit_report_html

        report = self.audit_claims(tailored_text_or_dict, subject_name=subject_name)
        return render_audit_report_html(report, template_path=template_path)

    def save_audit_report_html(
        self,
        tailored_text_or_dict: Union[str, dict, list],
        output_path: Union[str, Path],
        subject_name: Optional[str] = None,
        template_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Audits resume text or dictionary, renders HTML, and saves to output_path.
        """
        from core.evidence.report_renderer import save_audit_report_html

        report = self.audit_claims(tailored_text_or_dict, subject_name=subject_name)
        return save_audit_report_html(report, output_path=output_path, template_path=template_path)


# ---------------------------------------------------------------------------
# Top-Level Convenience Functions
# ---------------------------------------------------------------------------

def verify_resume_facts(
    tailored_text_or_dict: Union[str, dict, list],
    master_profile: Union[dict, str, Path],
    target_scope: Optional[Union[str, dict, int]] = None,
    target_claim_id: Optional[str] = None,
    target_excerpt: Optional[str] = None,
) -> dict:
    """
    Convenience function to verify tailored resume bullets against SSOT master profile.

    Args:
        tailored_text_or_dict: Resume text, list of bullets, or resume profile dictionary.
        master_profile: SSOT candidate_profile.json dictionary or filepath.
        target_scope: Optional scope restriction (e.g. 'experience[0]', 'projects[1]').
        target_claim_id: Optional target claim ID.
        target_excerpt: Optional target excerpt.

    Returns:
        dict with verification report: passed, score, drifts, unverified_claims, verified_bullets, verdict.
    """
    guard = FactVerificationGuard(master_profile)
    return guard.verify_facts(
        tailored_text_or_dict,
        target_scope=target_scope,
        target_claim_id=target_claim_id,
        target_excerpt=target_excerpt,
    )


def audit_resume_evidence(
    tailored_text_or_dict: Union[str, dict, list],
    master_profile: Union[dict, str, Path, Any],
    subject_name: Optional[str] = None,
) -> dict:
    """
    Convenience function to generate a schema-compliant evidence audit report.

    Args:
        tailored_text_or_dict: Resume text, list of bullets, or resume profile dictionary.
        master_profile: SSOT candidate_profile.json dictionary or filepath.
        subject_name: Optional subject candidate name.

    Returns:
        dict with OfferGet schema-compliant audit report.
    """
    guard = FactVerificationGuard(master_profile)
    return guard.generate_audit_report(tailored_text_or_dict, subject_name=subject_name)
