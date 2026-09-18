"""
OfferGet Core Registry (core/registry.py)
=========================================
Single Source of Truth (SSOT) static registries with rule IDs, versioning,
and typed accessors.

Registries:
1. AliasRegistry: Skill & technology canonicalization, alias management, and precise word-boundary matching.
2. TaxonomyRegistry: Role capability trees, dimensions, keywords, and role classification.
3. MetricPatternRegistry: Quantified patterns, non-metric technology whitelists, metric-topic mappings, and extraction.
4. QualityRuleRegistry: Linguistic quality rules, verb hierarchy, role ranks, inflation patterns, and forbidden buzzwords.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Set, Tuple


# ============================================================================
# 1. AliasRegistry
# ============================================================================

class AliasRegistry:
    """Static registry for skill & technology aliases and boundary-accurate matching."""

    REGISTRY_ID: str = "REG_SKILL_ALIAS"
    VERSION: str = "1.5.0"
    RULE_ID_PREFIX: str = "ALIAS"

    _ALIASES: Dict[str, Set[str]] = {
        "pytorch": {"pytorch", "torch"},
        "python": {"python"},
        "c++": {"c++", "cpp"},
        "cuda": {"cuda"},
        "triton": {"triton"},
        "megatron-lm": {"megatron-lm", "megatron"},
        "deepspeed": {"deepspeed"},
        "vllm": {"vllm"},
        "tensorrt-llm": {"tensorrt-llm", "tensorrt llm"},
        "sglang": {"sglang"},
        "dpo": {"dpo"},
        "ppo": {"ppo"},
        "grpo": {"grpo"},
        "rlhf": {"rlhf"},
        "mcp": {"mcp", "model context protocol"},
        "graphrag": {"graphrag", "graph rag"},
        "flashattention": {"flashattention", "flashattention-2", "flashattention-3"},
        "pagedattention": {"pagedattention"},
        "awq": {"awq"},
        "gptq": {"gptq"},
        "rope": {"rope"},
        "mla": {"mla", "multi-head latent attention"},
    }

    # Internal reverse index mapping every alias/canonical form to its canonical name
    _REVERSE_MAP: Dict[str, str] = {}
    for _canonical, _forms in _ALIASES.items():
        _REVERSE_MAP[_canonical.lower()] = _canonical
        for _form in _forms:
            _REVERSE_MAP[_form.lower()] = _canonical

    @classmethod
    def get_canonical(cls, term: str) -> str:
        """Returns the canonical form of a term, or the stripped lower-case term if not aliased."""
        if not term:
            return ""
        normalized = str(term).strip().lower()
        return cls._REVERSE_MAP.get(normalized, normalized)

    @classmethod
    def get_aliases(cls, canonical: str) -> Set[str]:
        """Returns a copy of all alias forms for a canonical term (or alias resolved to canonical)."""
        if not canonical:
            return set()
        normalized = str(canonical).strip().lower()
        canon = cls._REVERSE_MAP.get(normalized, normalized)
        if canon in cls._ALIASES:
            return set(cls._ALIASES[canon])
        return set()

    @classmethod
    def get_canonical_terms(cls, term: str) -> Set[str]:
        """Returns all known spellings for a term ({canonical, *forms}) or {normalized} if unknown."""
        if not term:
            return set()
        normalized = str(term).strip().lower()
        aliases = cls.get_aliases(normalized)
        if aliases:
            return aliases
        return {normalized}

    @classmethod
    def claim_matches(cls, term: str, claim_text: str) -> bool:
        """Precise regex matching using word boundary guards without substring collision."""
        if not term or not claim_text:
            return False
        text = str(claim_text).lower()
        candidates = cls.get_canonical_terms(term)
        for candidate in candidates:
            # (?<![a-z0-9_]) and (?![a-z0-9_]) prevent false substring matches (e.g., c++ vs c++20, or vllm inside an identifier)
            if re.search(r"(?<![a-z0-9_])" + re.escape(candidate) + r"(?![a-z0-9_])", text):
                return True
            if re.search(r"[\u4e00-\u9fa5]", candidate) and candidate in text:
                return True
        return False


    @classmethod
    def all_aliases(cls) -> Dict[str, Set[str]]:
        """Returns a deep copy of all canonical-to-aliases mappings ensuring read-only safety."""
        return {k: set(v) for k, v in cls._ALIASES.items()}


# ============================================================================
# 2. TaxonomyRegistry
# ============================================================================

class TaxonomyRegistry:
    """Static registry for enterprise role taxonomies, dimensions, and competencies."""

    REGISTRY_ID: str = "REG_ROLE_TAXONOMY"
    VERSION: str = "1.5.0"
    RULE_ID_PREFIX: str = "TAXONOMY"

    _ROLE_TAXONOMIES: Dict[str, Dict[str, Any]] = {
        "ai_algorithm": {
            "title": "AI / 大模型与算法架构",
            "keywords": ["Transformer", "MoE", "Megatron", "vLLM", "PyTorch", "CUDA", "Triton", "RAG", "Agent"],
            "dimensions": [("算法与模型", 0.25), ("工程与性能", 0.25), ("业务落地", 0.20), ("数据与评测", 0.15), ("研究与生态", 0.15)],
        },
        "backend_distributed": {
            "title": "后端与分布式高并发架构",
            "keywords": ["Java", "Go", "gRPC", "Kafka", "MySQL", "Redis", "微服务", "分布式事务", "DDD"],
            "dimensions": [("系统设计", 0.30), ("存储与一致性", 0.25), ("稳定性", 0.20), ("业务建模", 0.15), ("性能与工程", 0.10)],
        },
        "frontend_fullstack": {
            "title": "前端与 Web 全栈工程",
            "keywords": ["React", "Vue", "TypeScript", "Next.js", "Web Vitals", "SSR", "Vite", "BFF"],
            "dimensions": [("交互架构", 0.25), ("性能治理", 0.25), ("组件工程", 0.20), ("跨端协同", 0.15), ("体验指标", 0.15)],
        },
        "client_mobile": {
            "title": "客户端与移动端工程",
            "keywords": ["iOS", "Android", "Flutter", "Swift", "Kotlin", "ANR", "SQLite", "QUIC"],
            "dimensions": [("端侧架构", 0.25), ("稳定性", 0.25), ("跨端工程", 0.20), ("弱网与存储", 0.15), ("业务交互", 0.15)],
        },
        "bigdata_infra": {
            "title": "大数据开发与实时湖仓",
            "keywords": ["Flink", "Spark", "Iceberg", "Hudi", "ClickHouse", "StarRocks", "Doris", "数据血缘"],
            "dimensions": [("计算引擎", 0.30), ("湖仓建模", 0.25), ("查询与存储", 0.20), ("质量与成本", 0.15), ("业务决策", 0.10)],
        },
        "cloudnative_sre": {
            "title": "系统底层 / 云原生 / SRE",
            "keywords": ["Kubernetes", "K8s", "eBPF", "Prometheus", "Docker", "Slurm", "RDMA", "FinOps"],
            "dimensions": [("平台与调度", 0.25), ("网络与硬件", 0.25), ("稳定性", 0.20), ("系统性能", 0.15), ("成本治理", 0.15)],
        },
        "product": {
            "title": "产品管理与产品策略",
            "keywords": ["产品经理", "产品", "用户研究", "需求分析", "路线图", "PRD", "A/B测试", "用户增长", "留存", "转化"],
            "dimensions": [("问题定义", 0.25), ("用户与需求", 0.25), ("决策与交付", 0.20), ("数据与实验", 0.15), ("业务结果", 0.15)],
        },
        "operations": {
            "title": "运营与业务增长",
            "keywords": ["运营", "增长", "活动", "内容", "用户运营", "产品运营", "流程优化", "转化", "留存", "SLA"],
            "dimensions": [("运营策略", 0.25), ("流程执行", 0.25), ("用户与供给", 0.20), ("数据指标", 0.15), ("协同交付", 0.15)],
        },
        "marketing_sales": {
            "title": "市场、销售与商务拓展",
            "keywords": ["市场", "营销", "销售", "商务", "渠道", "获客", "线索", "客户", "ROI", "CAC", "pipeline"],
            "dimensions": [("市场洞察", 0.25), ("渠道与获客", 0.25), ("客户经营", 0.20), ("转化与收入", 0.20), ("复盘与协同", 0.10)],
        },
        "project_management": {
            "title": "项目管理与交付",
            "keywords": ["项目管理", "项目经理", "PMO", "敏捷", "Scrum", "里程碑", "风险管理", "交付", "干系人"],
            "dimensions": [("目标与范围", 0.25), ("计划与交付", 0.25), ("风险与质量", 0.20), ("干系人协同", 0.20), ("复盘改进", 0.10)],
        },
        "general": {
            "title": "通用岗位能力",
            "keywords": [],
            "dimensions": [("职责匹配", 0.30), ("能力证据", 0.30), ("结果表达", 0.20), ("岗位约束", 0.20)],
        },
    }

    @classmethod
    def get_taxonomy(cls, role_id: str) -> Optional[Dict[str, Any]]:
        """Returns a copy of the taxonomy definition for role_id, or None if not registered."""
        if role_id in cls._ROLE_TAXONOMIES:
            return copy.deepcopy(cls._ROLE_TAXONOMIES[role_id])
        return None

    @classmethod
    def list_taxonomies(cls) -> Dict[str, Dict[str, Any]]:
        """Returns a deep copy of all registered role taxonomies."""
        return copy.deepcopy(cls._ROLE_TAXONOMIES)

    @classmethod
    def classify_role(cls, jd_text: str) -> Dict[str, Any]:
        """Classifies a JD text into the best matching taxonomy category."""
        text = jd_text or ""
        scores = {
            key: sum(1 for keyword in info["keywords"] if keyword.lower() in text.lower())
            for key, info in cls._ROLE_TAXONOMIES.items()
        }
        best_key = max(scores, key=scores.get) if scores and max(scores.values()) else "general"
        info = cls._ROLE_TAXONOMIES[best_key]
        return {"role_key": best_key, "taxonomy": copy.deepcopy(info)}


# ============================================================================
# 3. MetricPatternRegistry
# ============================================================================

class MetricPatternRegistry:
    """Static registry for quantified metrics, non-metric technology whitelists, and topic mappings."""

    REGISTRY_ID: str = "REG_METRIC_PATTERN"
    VERSION: str = "1.5.0"
    RULE_ID_PREFIX: str = "METRIC"

    QUANTIFIED_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b\d+(?:\.\d+)?%"),                                                  # 54.2%, 62%, 100%
        re.compile(r"\b\d+(?:\.\d+)?x\b", re.IGNORECASE),                                  # 2.8x, 3x
        re.compile(r"[$¥￥]\s*\d+(?:,\d+)*(?:\.\d+)?"),                                   # $100k, ￥3800
        re.compile(r"\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:万|亿元|万元|k|m|b|billion|million|rmb|usd)\b", re.IGNORECASE), # 3800 万元, 38M RMB
        re.compile(r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|seconds?|min|minutes?|hours?|h|周|天|小时|分钟|秒|weeks?|days?|months?)\b", re.IGNORECASE), # 320ms, 8 分钟
        re.compile(r"\b\d+(?:,\d+)?\s*(?:卡|gpus?|nodes?|tps|qps|tokens?/s|gb|tb|pb|stars?|citations?|条|篇)\b", re.IGNORECASE), # 1024 卡, 3400 stars
        re.compile(r"\b\d+[bm]\b", re.IGNORECASE),                                         # 230B, 64B
        re.compile(r"[+上下降提升增加缩短减少压减削减]\s*\d+(?:\.\d+)?%?"),                      # 提升 14.2%, 减少 48%
        re.compile(r"\b(?:from|slashing|reducing|increasing|boosting)\b[^\n,;]+?\b\d+"),   # English metric phrasing
    ]

    NON_METRIC_TECH_PATTERNS: List[re.Pattern] = [
        re.compile(r"\bC\+\+[0-9]{2}\b", re.IGNORECASE),                         # C++17, C++20
        re.compile(r"\bFlashAttention-[23](?:/[23])?\b", re.IGNORECASE),        # FlashAttention-2/3
        re.compile(r"\bZeRO-[123]\b", re.IGNORECASE),                           # ZeRO-3
        re.compile(r"\bGPT-[34](?:o|\.5)?\b", re.IGNORECASE),                   # GPT-4o, GPT-3.5
        re.compile(r"\b(?:FP8|INT8|INT4|FP16|BF16)\b", re.IGNORECASE),           # Quantization formats
        re.compile(r"\b(?:E4M3|E5M2)\b", re.IGNORECASE),                        # FP8 sub-types
        re.compile(r"\bGSM8K\b", re.IGNORECASE),                                # Benchmark name
        re.compile(r"\bBM25\b", re.IGNORECASE),                                 # Algorithm name
        re.compile(r"\b[34]D\s*(?:Parallel|并[行度])?\b", re.IGNORECASE),        # 3D/4D Parallel
        re.compile(r"\b(?:P[78]|L[56])\b", re.IGNORECASE),                      # Job grade labels
        re.compile(r"\b(?:H800|H100|A800|A100|V100|RTX\s*4090)\b", re.IGNORECASE), # Accelerator models
        # Realistic calendar date ranges: e.g. 2020.08 - 2023.02, 2020 - 至今
        re.compile(r"\b(?:19[7-9]\d|20[0-2]\d)\s*(?:\.\s*\d{1,2})?\s*[-~–—到至]\s*(?:(?:19[7-9]\d|20[0-2]\d)(?:\.\s*\d{1,2})?|至今|present)\b", re.IGNORECASE),
        # Standalone dates with dot month: e.g. 2023.03
        re.compile(r"\b(?:19[7-9]\d|20[0-2]\d)\.\d{1,2}\b", re.IGNORECASE),
        # Calendar year e.g. 2024年
        re.compile(r"\b(?:19[7-9]\d|20[0-2]\d)\s*年", re.IGNORECASE),
        re.compile(r"\bEXP-\d{2}\b", re.IGNORECASE),                            # Claim IDs
        re.compile(r"\bRFC[-\s]?\d+\b", re.IGNORECASE),                         # RFC IDs
    ]

    METRIC_TYPE_TO_TOPICS: Dict[str, Set[str]] = {
        "percentage": {"mfu", "uptime", "latency_reduction", "cost_reduction", "vram_reduction", "gsm8k_gain", "math_gain"},
        "currency": {"savings"},
        "time_hours": {"downtime_before", "time_hours"},
        "time_minutes": {"downtime_after", "time_minutes"},
        "time_ms": {"ttft_after", "time_ms"},
        "time_s": {"ttft_before", "time_s"},
        "time_weeks": {"time_saved", "time_weeks"},
        "years": {"experience_years"},
        "cluster_size": {"cluster_size"},
        "model_param": {"model_params"},
        "stars": {"stars"},
        "multiplier": {"multiplier"},
        "count": {"count"},
    }

    @classmethod
    def is_bullet_quantified(cls, bullet: str) -> bool:
        """Checks whether a single bullet contains quantified metrics."""
        if not bullet:
            return False
        for pattern in cls.QUANTIFIED_PATTERNS:
            if pattern.search(bullet):
                return True
        return False

    @classmethod
    def get_quantified_patterns(cls) -> List[re.Pattern]:
        return list(cls.QUANTIFIED_PATTERNS)

    @classmethod
    def get_non_metric_tech_patterns(cls) -> List[re.Pattern]:
        return list(cls.NON_METRIC_TECH_PATTERNS)

    @classmethod
    def get_metric_type_to_topics(cls) -> Dict[str, Set[str]]:
        return {k: set(v) for k, v in cls.METRIC_TYPE_TO_TOPICS.items()}

    @classmethod
    def extract_raw_metrics(cls, text: str) -> List[Dict[str, Any]]:
        """
        Extracts all quantified numerical metrics from a text string using regex.
        Filters out non-metric technical identifiers (C++20, FlashAttention-2, ZeRO-3, etc.).
        """
        metrics: List[Dict[str, Any]] = []

        # 1. Mask non-metric tech terms to avoid false extraction
        masked_text = text
        for pat in cls.NON_METRIC_TECH_PATTERNS:
            masked_text = pat.sub(lambda m: "X" * len(m.group(0)), masked_text)

        # 2. Extract Currencies (e.g. 3800 万元, 38M RMB, 38,000,000 RMB)
        curr_pattern = re.compile(
            r"(?:[$¥￥]\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(万元|万|亿元|M\s*RMB|m\s*rmb|million\s*rmb|RMB|usd|美元)",
            re.IGNORECASE
        )
        for m in curr_pattern.finditer(masked_text):
            raw = text[m.start():m.end()]
            val_str = m.group(1).replace(",", "")
            unit = m.group(2).strip()
            num = float(val_str)
            metrics.append({
                "raw": raw,
                "value": num,
                "unit": unit,
                "type": "currency",
                "start": m.start(),
                "end": m.end()
            })

        # 3. Extract Percentages (e.g. 54.2%, 45%, 38.5%)
        pct_pattern = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
        for m in pct_pattern.finditer(masked_text):
            raw = text[m.start():m.end()]
            num = float(m.group(1))
            metrics.append({
                "raw": raw,
                "value": num,
                "unit": "%",
                "type": "percentage",
                "start": m.start(),
                "end": m.end()
            })

        # 4. Extract Multipliers (e.g. 2.8x, 3x, 2.8倍)
        mult_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*([xX倍])(?:\b|[^\w]|$)")
        for m in mult_pattern.finditer(masked_text):
            raw = text[m.start():m.end()]
            num = float(m.group(1))
            metrics.append({
                "raw": raw,
                "value": num,
                "unit": m.group(2),
                "type": "multiplier",
                "start": m.start(),
                "end": m.end()
            })

        # 5. Extract Time Durations
        # Hours
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(小时|个半小时|h\b|hours?\b|hrs?\b)", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            metrics.append({
                "raw": raw,
                "value": float(m.group(1)),
                "unit": "小时",
                "type": "time_hours",
                "start": m.start(),
                "end": m.end()
            })
        # Minutes
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(分钟|分|min\b|minutes?\b|mins?\b)", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            metrics.append({
                "raw": raw,
                "value": float(m.group(1)),
                "unit": "分钟",
                "type": "time_minutes",
                "start": m.start(),
                "end": m.end()
            })
        # Milliseconds
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*ms\b", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            metrics.append({
                "raw": raw,
                "value": float(m.group(1)),
                "unit": "ms",
                "type": "time_ms",
                "start": m.start(),
                "end": m.end()
            })
        # Seconds
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:秒|s\b|sec\b|seconds?\b)", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            metrics.append({
                "raw": raw,
                "value": float(m.group(1)),
                "unit": "s",
                "type": "time_s",
                "start": m.start(),
                "end": m.end()
            })
        # Weeks
        for m in re.finditer(r"(\d+)\s*(周|个星期|weeks?\b|wks?\b)", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            metrics.append({
                "raw": raw,
                "value": float(m.group(1)),
                "unit": "周",
                "type": "time_weeks",
                "start": m.start(),
                "end": m.end()
            })
        # Days
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(天|日|days?\b)", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            metrics.append({
                "raw": raw,
                "value": float(m.group(1)),
                "unit": "天",
                "type": "time_days",
                "start": m.start(),
                "end": m.end()
            })
        # Years of experience (excluding calendar year dates like 2023年)
        for m in re.finditer(r"(?<!\d)(\d{1,2})\+?\s*(年|years?\b)", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            val = float(m.group(1))
            if val < 40:  # Exclude calendar years
                metrics.append({
                    "raw": raw,
                    "value": val,
                    "unit": "年",
                    "type": "years",
                    "start": m.start(),
                    "end": m.end()
                })

        # 6. Extract Hardware / Capacity / Counts
        # Cards / GPUs
        for m in re.finditer(r"(\d+(?:,\d+)?)\s*(卡|张卡|张|gpus?\b|nodes?\b|节点)", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            val = float(m.group(1).replace(",", ""))
            metrics.append({
                "raw": raw,
                "value": val,
                "unit": "卡",
                "type": "cluster_size",
                "start": m.start(),
                "end": m.end()
            })

        # Model Parameters (e.g. 64B, 230B, 32B)
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*([bBmM])\b", masked_text):
            raw = text[m.start():m.end()]
            metrics.append({
                "raw": raw,
                "value": float(m.group(1)),
                "unit": m.group(2).upper(),
                "type": "model_param",
                "start": m.start(),
                "end": m.end()
            })

        # Stars & Citations
        for m in re.finditer(r"(\d+(?:,\d+)?)\+?\s*(stars?\b|citations?\b|星|次引用|引用)", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            val = float(m.group(1).replace(",", ""))
            metrics.append({
                "raw": raw,
                "value": val,
                "unit": m.group(2),
                "type": "stars",
                "start": m.start(),
                "end": m.end()
            })

        # Standalone count units (e.g. 50 人, 50 位, 99999 次)
        for m in re.finditer(r"(\d+(?:,\d+)?)\s*(人|位|名|次|条|篇|款)", masked_text, re.IGNORECASE):
            raw = text[m.start():m.end()]
            val = float(m.group(1).replace(",", ""))
            metrics.append({
                "raw": raw,
                "value": val,
                "unit": m.group(2),
                "type": "count",
                "start": m.start(),
                "end": m.end()
            })

        # Remove duplicate overlaps (prefer longer match)
        deduped: List[Dict[str, Any]] = []
        for met in sorted(metrics, key=lambda x: (x["start"], -(x["end"] - x["start"]))):
            overlap = False
            for d in deduped:
                if not (met["end"] <= d["start"] or met["start"] >= d["end"]):
                    overlap = True
                    break
            if not overlap:
                deduped.append(met)

        return deduped


# ============================================================================
# 4. QualityRuleRegistry
# ============================================================================

class QualityRuleRegistry:
    """Static registry for linguistic rules, verb hierarchy, role ranks, and inflation detection."""

    REGISTRY_ID: str = "REG_QUALITY_RULE"
    VERSION: str = "1.5.0"
    RULE_ID_PREFIX: str = "RULE"

    VERB_HIERARCHY: Dict[str, int] = {
        # Level 1: 支持 / 协助
        "支持": 1, "协助": 1, "配合": 1, "辅助": 1,
        "assisted in": 1, "helped with": 1, "supported": 1, "aided": 1,

        # Level 2: 参与 / 共建
        "参与": 2, "共建": 2, "贡献": 2, "contribute": 2, "contributed to": 2,
        "participated in": 2, "collaborated on": 2, "took part in": 2, "参编": 2,

        # Level 3: 负责 / 研发落地
        "负责": 3, "主要负责": 3, "承担": 3, "落地": 3, "实现": 3, "搭建": 3,
        "开发": 3, "设计并实现": 3, "responsible for": 3, "implemented": 3,
        "built": 3, "engineered": 3, "deployed": 3, "customized": 3,

        # Level 4: 推动 / 牵引
        "推动": 4, "推进": 4, "牵引": 4, "促进": 4, "带动": 4,
        "drove": 4, "accelerated": 4, "streamlined": 4, "scaled": 4, "optimized": 4,

        # Level 5: 主导 / 统筹架构
        "主导": 5, "统筹": 5, "引领": 5, "主持": 5, "从0到1": 5, "独立负责": 5,
        "owner": 5, "architected": 5, "spearheaded": 5, "pioneered": 5, "led": 5,
        "orchestrated": 5, "overhauled": 5, "invented": 5,
    }

    STRONG_VERBS_THRESHOLD: int = 4

    STRONG_ACTION_VERBS_EN: Set[str] = {
        "built", "architected", "engineered", "spearheaded", "shipped", "optimized",
        "deployed", "pioneered", "led", "scaled", "accelerated", "authored",
        "designed", "implemented", "streamlined", "delivered", "orchestrated",
        "formulated", "executed", "overhauled", "customized", "refactored",
        "automated", "established", "invented", "slashed", "drove"
    }

    STRONG_ACTION_VERBS_ZH: Set[str] = {
        "主导", "架构", "研发", "搭建", "攻坚", "优化", "实现", "交付",
        "推进", "开源", "设计", "落地", "首创", "降低", "提升", "节省",
        "自研", "定制", "重构", "重塑", "打通", "构建", "牵引", "主持"
    }

    WEAK_ACTION_VERBS_EN: Set[str] = {
        "responsible for", "assisted in", "helped with", "worked on",
        "participated in", "contributed to", "handled", "involved in",
        "tasked with", "supported", "aided", "collaborated on", "took part in"
    }

    WEAK_ACTION_VERBS_ZH: Set[str] = {
        "负责", "参与", "协助", "配合", "辅助", "支持", "做过", "了解", "接触过", "跟进"
    }

    ROLE_RANKS: Dict[str, int] = {
        # Rank 0: Planning / Exploratory
        "计划": 0, "规划": 0, "探索": 0, "预研": 0, "当前方向": 0, "拟": 0,
        # Rank 1: Contributor / Participant
        "参与": 1, "协助": 1, "支持": 1, "共建者": 1, "配合": 1, "contributor": 1,
        # Rank 2: Lead / Maintainer
        "主导": 2, "主要负责": 2, "策略架构owner": 2, "策略owner": 2, "架构负责人": 2, "maintainer": 2, "方向负责人": 2,
        # Rank 3: Independent Owner
        "独立负责": 3, "从0到1": 3, "端到端负责": 3, "完全负责": 3, "owner": 3,
    }

    ROLE_RANK_NAMES: Dict[int, str] = {
        0: "规划/探索 (Planning / Exploratory)",
        1: "参与/协作 (Contributor / Participant)",
        2: "主导/负责 (Lead / Maintainer)",
        3: "独立Owner (Independent Owner)",
    }

    STRONG_ROLE_TERMS: re.Pattern = re.compile(
        r"核心作者|maintainer|owner|主导|完全负责|总负责人|架构师|committer",
        re.IGNORECASE
    )

    MODULE_QUALIFIERS: re.Pattern = re.compile(
        r"([\u4e00-\u9fa5A-Za-z0-9_]+(?:模块|链路|子系统|组件|策略|引擎))\s*(?:Owner|负责人|主导|开发)",
        re.IGNORECASE
    )

    PLANNED_MARKERS: re.Pattern = re.compile(
        r"计划|规划|当前方向|拟|探索|聚焦|下一阶段|展望",
        re.IGNORECASE
    )

    FORBIDDEN_SUPERLATIVES: re.Pattern = re.compile(
        r"全球最[强快好年轻]|业内首个|第一人|全网最[快强]|绝对最优",
        re.IGNORECASE
    )

    COMPLETED_VERBS_FORBIDDEN_IN_PLANNING: List[str] = [
        "已上线", "已达成", "完成", "实现", "主导", "owner", "核心作者", "提升约", "降低约", "突破"
    ]

    SUPERLATIVES: List[str] = [
        "全网第一", "全国第一", "全球第一", "业界第一", "唯一", "最优", "顶尖", "首个"
    ]

    INFLATION_PATTERNS: Dict[str, Dict[str, Any]] = {
        "P1_SCOPE_INFLATION": {
            "name": "范围与角色夸大 (Scope Inflation / Role Elevation)",
            "pattern_terms": STRONG_ROLE_TERMS,
            "qualifier": MODULE_QUALIFIERS,
            "detail": "使用全盘架构强词（如 Owner/主导/完全负责），但未限定具体闭环模块名称",
            "fix_suggestion": "限定至具体责任单元，改写为 '[具体模块名] Owner' 或 '负责 [具体组件] 研发'",
        },
        "P2_UNBOUNDED_SUPERLATIVE": {
            "name": "排他性最高级 (Unbounded Superlative)",
            "pattern": FORBIDDEN_SUPERLATIVES,
            "superlatives": SUPERLATIVES,
            "detail": "命中排他性最高级词汇，缺乏第三方官方全集背书",
            "fix_suggestion": "删除绝对化最高级，采用限定客观场景或具体指标对比表达",
        },
        "P3_TEMPORAL_CONFUSION": {
            "name": "时态混淆 / 规划期完成态 (Temporal Confusion)",
            "planned_markers": PLANNED_MARKERS,
            "completed_verbs": COMPLETED_VERBS_FORBIDDEN_IN_PLANNING,
            "detail": "处于探索/规划阶段（Planned）却使用了过去完成时强主导动词（如主导/已实现）",
            "fix_suggestion": "保留时态边界，使用 '当前规划'、'重点探索'，禁止声称已产生确定性生产收益",
        },
        "P4_PSEUDO_ZERO_TO_ONE": {
            "name": "伪从0到1 (Pseudo Zero to One)",
            "trigger_term": "从0到1",
            "conflicting_terms": ["重构", "优化", "演进"],
            "detail": "存量系统重构/优化与'从0到1'叙事冲突",
            "fix_suggestion": "改写为 '[原架构] → [新架构] 架构演进' 或 '核心指标跃迁'",
        },
    }

    FORBIDDEN_BUZZWORDS: List[str] = [
        "首创", "颠覆", "国际先进", "世界一流", "填补空白", "独家", "最优解", "全能", "领先"
    ]

    AI_BUZZWORDS_LEXICON: List[str] = [
        # English buzzwords
        "results-driven", "results driven", "dynamic", "synergy", "passionate",
        "proven track record", "deeply passionate", "testament to", "delve into",
        "pivotal role", "game-changing transformation", "intricate tapestry",
        "fast-paced environment", "thought leader", "go-getter", "team player",
        "seasoned professional", "cutting-edge solutions", "groundbreaking",
        "spearheading transformative", "holistic approach", "seamlessly integrate",
        "unwavering commitment", "strategic vision", "value proposition",
        # Chinese buzzwords
        "具有深厚底蕴", "全面赋能", "深度赋能", "全面革新", "强力驱动", "革命性突破",
        "显著提高", "大幅优化", "卓越成效", "顶层设计", "无缝打通", "全方位重塑",
        "作为一名深耕", "深耕.*领域", "不仅.*而且.*更.*"
    ]

    @staticmethod
    def detect_role_rank(text: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Finds role rank using longest-prefix matching to avoid substring collision.
        Returns (rank, matched_term) or (None, None).
        """
        lower = str(text).lower()
        sorted_keys = sorted(QualityRuleRegistry.ROLE_RANKS.keys(), key=lambda k: len(k), reverse=True)
        for k in sorted_keys:
            if k.lower() in lower:
                return QualityRuleRegistry.ROLE_RANKS[k], k
        return None, None

    @staticmethod
    def detect_verb_level(text: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Detects verb level (1~5) using longest-match first.
        Returns (level, matched_verb) or (None, None).
        """
        lower = str(text).lower()
        sorted_verbs = sorted(QualityRuleRegistry.VERB_HIERARCHY.keys(), key=lambda k: len(k), reverse=True)
        for v in sorted_verbs:
            if v.lower() in lower:
                return QualityRuleRegistry.VERB_HIERARCHY[v], v
        return None, None


    @classmethod
    def get_inflation_rule(cls, rule_id: str) -> Optional[Dict[str, Any]]:
        if rule_id in cls.INFLATION_PATTERNS:
            return copy.deepcopy(cls.INFLATION_PATTERNS[rule_id])
        return None

    @classmethod
    def list_inflation_rules(cls) -> Dict[str, Dict[str, Any]]:
        return copy.deepcopy(cls.INFLATION_PATTERNS)

    @classmethod
    def is_forbidden_buzzword(cls, word: str) -> bool:
        w = word.strip().lower()
        return any(b.lower() == w or b.lower() in w for b in cls.FORBIDDEN_BUZZWORDS)


__all__ = [
    "AliasRegistry",
    "TaxonomyRegistry",
    "MetricPatternRegistry",
    "QualityRuleRegistry",
]
