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
        "data_analyst": {
            "title": "数据分析与商业智能 (BI)",
            "keywords": ["数据分析", "数据分析师", "商业智能", "BI", "Tableau", "PowerBI", "看板", "A/B测试", "漏斗分析", "归因分析", "SQL取数"],
            "dimensions": [("指标体系", 0.25), ("取数与工程", 0.25), ("业务洞察", 0.25), ("实验与归因", 0.15), ("交付呈现", 0.10)],
        },
        "ai_product": {
            "title": "AI 产品经理 / 智能体与大模型产品",
            "keywords": ["AI产品", "AI产品经理", "大模型产品", "LLM", "Prompt", "Agent", "智能体", "模型评测", "RAG架构", "落地场景"],
            "dimensions": [("场景定义", 0.25), ("模型边界与评测", 0.25), ("方案设计", 0.20), ("工程协同", 0.15), ("业务指标", 0.15)],
        },
        "qa_test_engineer": {
            "title": "测试开发与质量保障 (QA)",
            "keywords": ["测试开发", "质量保障", "QA", "自动化测试", "接口测试", "性能测试", "压测", "JMeter", "Selenium", "Pytest", "漏测率"],
            "dimensions": [("测试方案", 0.30), ("自动化工程", 0.25), ("性能压测", 0.20), ("缺陷定位", 0.15), ("质量体系", 0.10)],
        },
        "ui_ux_design": {
            "title": "UI/UX 设计 / 交互与体验设计",
            "keywords": ["UI", "UX", "UI/UX", "交互设计", "视觉设计", "体验设计", "设计系统", "Figma", "Sketch", "用户研究", "原型设计"],
            "dimensions": [("用户洞察", 0.25), ("交互与架构", 0.25), ("设计系统", 0.20), ("工程协同", 0.15), ("体验指标", 0.15)],
        },
        "growth_strategy": {
            "title": "用户增长 / 策略运营与转化",
            "keywords": ["用户增长", "增长黑客", "转化漏斗", "裂变", "用户召回", "CAC", "LTV", "A/B实验", "生命周期运营"],
            "dimensions": [("增长模型", 0.30), ("漏斗与转化", 0.25), ("实验驱动", 0.20), ("渠道策略", 0.15), ("复盘归因", 0.10)],
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
        "percentage": {"mfu", "uptime", "latency_reduction", "cost_reduction", "vram_reduction", "gsm8k_gain", "math_gain", "percentage", "generic"},
        "currency": {"savings", "currency", "generic"},
        "time_hours": {"downtime_before", "time_hours", "generic"},
        "time_minutes": {"downtime_after", "time_minutes", "generic"},
        "time_ms": {"ttft_after", "time_ms", "generic"},
        "time_s": {"ttft_before", "time_s", "generic"},
        "time_weeks": {"time_saved", "time_weeks", "generic"},
        "years": {"experience_years", "years", "generic"},
        "cluster_size": {"cluster_size", "generic"},
        "model_param": {"model_params", "model_param", "generic"},
        "stars": {"stars", "generic"},
        "multiplier": {"multiplier", "generic"},
        "count": {"count", "generic"},
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

    # -------------------------------------------------------------------------
    # ApexResume Decision, Depth, and Evidence Standards
    # -------------------------------------------------------------------------
    DECISION_PLANNING_KEYWORDS: List[str] = [
        "选型", "技术路线", "架构设计", "方案决策", "规划", "制定", "技术决策",
        "重构方案", "标准制定", "规范制定", "rfc", "决策", "调研论证", "技术评审"
    ]

    DATA_DEPTH_LEVELS: Dict[str, str] = {
        "D0": "描述性统计 (Descriptive: 计数、均值、汇总)",
        "D1": "诊断性归因 (Diagnostic: 细分下钻、漏斗、同比环比)",
        "D2": "探索性关联 (Exploratory: 相关性分析、特征重要度、切片对比)",
        "D3": "预测性建模 (Predictive/Causal: 趋势预估、因果推断、PSM、DID)",
        "D4": "规范性自适应 (Prescriptive: 运筹优化、强化学习闭环、动态调度)",
    }

    RESULT_EVIDENCE_LEVELS: Dict[str, str] = {
        "R0": "理论预估 (Theoretical: 纯假定、无外部验证)",
        "R1": "离线基准 (Offline Benchmark: 实验室评测、公开数据集静态分)",
        "R2": "灰度验证 (Gray-scale / A/B Test: 准生产、小流量实验验证)",
        "R3": "生产实效 (Production Impact: 全量生产稳定运行与宏观商业价值)",
    }

    # -------------------------------------------------------------------------
    # Role-Specific KPI Metric Lexicon
    # -------------------------------------------------------------------------
    ROLE_KPI_LEXICON: Dict[str, List[str]] = {
        "product": ["DAU", "MAU", "留存率", "转化率", "点击率", "付费率", "NPS", "需求上线数", "GMV"],
        "ai_product": ["任务成功率", "准确率", "采纳率", "响应时间", "调用成本", "Token消耗", "人工兜底率"],
        "operations": ["拉新数", "活跃率", "复购率", "社群人数", "活动参与率", "GMV", "ROI", "履约率"],
        "sales": ["线索数", "商机数", "成交率", "回款额", "客单价", "销售周期", "续约率", "签约额"],
        "marketing": ["曝光量", "点击率", "CTR", "CPL", "CPA", "ROI", "获客成本", "线索转化率"],
        "technical": ["QPS", "TPS", "响应时间", "P99延迟", "故障率", "可用性", "SLA", "代码覆盖率", "吞吐量", "成本降低"],
        "data_analyst": ["看板数量", "指标口径", "SQL执行耗时", "预测准确率", "实验显著性", "建议采纳率", "漏斗转化提升"],
        "design": ["交付效率", "组件复用率", "点击率", "转化率", "用户满意度", "改版正向率"],
        "qa": ["用例覆盖率", "自动化率", "缺陷发现率", "漏测率", "压测峰值", "回归耗时"],
        "project_management": ["按期交付率", "需求交付周期", "预算偏差率", "千行代码缺陷率", "里程碑达成率"],
    }

    # -------------------------------------------------------------------------
    # Validator Anti-AI-Slop Patterns
    # -------------------------------------------------------------------------
    BANNED_SLOP_PATTERNS: List[Tuple[str, str]] = [
        (r"[—\u2014\u2013]{1,2}", "Banned Dash/Em-dash syntax (破折号修饰滥用)"),
        (r"不仅.*而且.*更.*", "Banned Rule-of-Three parallelism (排比三段论假大空)"),
        (r"(深度赋能|全面革新|强力驱动|革命性突破|显著提高|大幅优化|卓越成效|无缝打通|全方位重塑)", "Banned hyperbolic buzzword without metric (虚高空洞动词/副词)"),
        (r"作为一名深耕.*的", "Banned empty appositive title (空洞自封同位语)"),
        (r"(delve into|testament to|pivotal role|game-changing transformation|intricate tapestry)", "Banned English AI cliche phrase")
    ]

    # -------------------------------------------------------------------------
    # ATS Formats and Defense Guides
    # -------------------------------------------------------------------------
    STANDARD_SECTIONS: Dict[str, List[str]] = {
        "Experience": [
            "experience", "work experience", "professional experience",
            "employment history", "work history", "工作经历", "工作经验", "职业经历"
        ],
        "Education": [
            "education", "academic background", "educational background",
            "education & credentials", "教育背景", "教育经历", "学历", "教育"
        ],
        "Skills": [
            "skills", "technical skills", "competencies", "core competencies",
            "skillset", "专业技能", "核心技能", "技能清单", "技能专长", "技术栈"
        ],
        "Projects": [
            "projects", "project experience", "key projects", "selected projects",
            "项目经历", "项目经验", "核心项目", "重点项目"
        ],
        "Summary": [
            "summary", "professional summary", "executive summary", "about me",
            "profile", "narrative", "个人总结", "个人评价", "个人简介", "自我评价", "职业概述", "概述"
        ]
    }

    FORMATTING_RISKS: List[Tuple[str, re.Pattern, str]] = [
        ("table", re.compile(r"<table\b|<tr\b|<td\b|<th\b|\|[^\n]+\|\s*\n\s*\|[-:| ]+\|\s*\n|\\begin\{tabular\}", re.IGNORECASE), "Tables in ATS resumes often cause text scrambling or parser failure"),
        ("multi_column", re.compile(r"column-count\s*:|display\s*:\s*(?:flex|grid)|grid-template-columns|class=[\"'][^\"']*(?:col-\d+|two-column|multi-column|sidebar)[^\"']*", re.IGNORECASE), "Multi-column layouts disrupt linear parsing reading order"),
        ("complex_nested_blocks", re.compile(r"<div[^>]*>\s*<div[^>]*>\s*<div[^>]*>\s*<div|<iframe\b|<canvas\b|<script\b|<object\b", re.IGNORECASE), "Complex nested HTML elements or embeds fail in legacy ATS parsers"),
        ("non_standard_symbols", re.compile(r"[★✪❖➔✔►◆■✈✉☎✓✗➤➢✦✧▼▲◀▶]"), "Non-standard decorative symbols confuse character encoders in ATS")
    ]

    DEFENSE_GUIDE_TEMPLATES: Dict[str, str] = {
        "kubernetes": "Acknowledge lack of production K8s cluster maintenance. Pivot to distributed container workload scheduling, GPU node discovery, and Slurm/MPI execution topology understanding.",
        "k8s": "Acknowledge lack of production K8s cluster maintenance. Pivot to distributed container workload scheduling, GPU node discovery, and Slurm/MPI execution topology understanding.",
        "triton": "Be transparent: state that custom kernels were previously written in CUDA/C++ or optimized PyTorch. Highlight strong grasp of GPU SRAM/HBM memory hierarchies and tile-level compilation principles.",
        "rust": "Honestly state no commercial Rust production experience. Emphasize deep mastery of C++17/20 systems programming, explicit memory safety concepts, and ability to read Rust codebases immediately.",
        "megatron-lm": "Clarify that 3D parallelism principles (TP/PP/DP/SP) were mastered conceptually and on DeepSpeed/FSDP; demonstrate exact communication volume equations during interview.",
        "default": "Transparently acknowledge the gap without defensiveness. Pivot to adjacent production architectures, emphasize deep conceptual grasp of the underlying principles, and highlight rapid 48-hour ramp-up history."
    }

    # -------------------------------------------------------------------------
    # Baoyan Academic Integrity & Typography Standards
    # -------------------------------------------------------------------------
    BAOYAN_SPEC_RANGES: Dict[str, Tuple[int, int]] = {
        "摘要版": (40, 60),
        "简历版": (80, 110),
        "陈述版": (150, 220),
    }

    BAOYAN_SPEC_ALIASES: Dict[str, str] = {
        "摘要版": "摘要版",
        "摘要": "摘要版",
        "summary": "摘要版",
        "简历版": "简历版",
        "简历": "简历版",
        "resume": "简历版",
        "陈述版": "陈述版",
        "陈述": "陈述版",
        "个人陈述": "陈述版",
        "statement": "陈述版",
    }

    FORBIDDEN_DASHES: Dict[str, str] = {
        "——": "chinese em dash (——)",
        "\u2014": "em dash (—)",
        "\u2013": "en dash (–)",
        "\u2015": "horizontal bar (―)",
        "\u2212": "minus (−)",
        "\u2e3a": "two-em dash (⸺)",
        "\u2e3b": "three-em dash (⸻)",
    }

    FORBIDDEN_QUOTES: Dict[str, str] = {
        "\u201c": "left double quote (“)",
        "\u201d": "right double quote (”)",
        "\u2018": "left single quote (‘)",
        "\u2019": "right single quote (’)",
    }

    FORBIDDEN_DOUBLE_HYPHEN: str = "--"

    BAOYAN_LEAD_ROLES: Set[str] = {
        "项目负责人", "负责人", "队长", "主持人", "算法链负责人", "模块负责人", "课题组长", "第一完成人"
    }

    BAOYAN_CORE_ROLES: Set[str] = {
        "核心成员", "核心骨干", "核心研发"
    }

    BAOYAN_LEAD_OR_CORE_ROLES: Set[str] = BAOYAN_LEAD_ROLES | BAOYAN_CORE_ROLES

    BAOYAN_NON_LEAD_ROLES: Set[str] = {
        "参赛队员", "队员", "辅助成员", "成员", "团队成员", "组员", "协作者"
    }

    BAOYAN_ESCALATED_VERBS: List[str] = [
        "主导", "负责", "统筹", "独立完成"
    ]

    BAOYAN_LEADER_ONLY_VERBS: List[str] = [
        "主导", "统筹"
    ]

    SIMULATION_TERMS: List[str] = [
        "gazebo", "gym", "pybullet", "toy dataset", "toy-dataset", "toy数据集", "纯仿真",
        "flexsim", "carla", "isaac gym", "isaac-gym", "mujoco", "airsim", "ns-3",
        "matlab仿真", "仿真环境", "模拟环境", "仿真平台", "仿真系统", "仿真测试", "仿真验证", "模拟路网"
    ]

    REAL_CLUSTER_TERMS: List[str] = [
        "万卡集群", "千卡集群", "百卡集群", "物理机", "物理机集群", "物理集群",
        "真实物理机", "真实集群", "实机", "实机部署", "实机测试", "实机验证",
        "实测", "产线实测", "产线部署", "真实产线", "实车", "实车测试", "实车部署",
        "硬件落地", "硬件部署", "端侧实测", "板端实测", "上车实测"
    ]

    EXPECTED_OUTCOME_TERMS: List[str] = [
        "在投", "准备投稿", "拟投稿", "预计录用", "拟发表", "待审", "待评审",
        "审稿中", "拟申请", "拟申报", "预期录用", "预期发表", "under review", "in submission", "submitted"
    ]

    ACQUIRED_OUTCOME_TERMS: List[str] = [
        "已录用", "已见刊", "已发表", "录用待刊", "已出版", "已授权", "accepted", "published"
    ]

    # -------------------------------------------------------------------------
    # Role & Title Hierarchy and Inflation Prevention Lexicon
    # -------------------------------------------------------------------------
    ROLE_HIERARCHY_LEVELS: Dict[str, int] = {
        # Level 0: Volunteer / Student Role / Contributor / Task Support
        "志愿实践成员": 0, "志愿服务成员": 0, "志愿成员": 0, "志愿者": 0, "义工": 0,
        "心理委员": 0, "宣传委员": 0, "组织委员": 0, "生活委员": 0, "文体委员": 0,
        "学习委员": 0, "课代表": 0, "班委": 0, "班级代表": 0,
        "volunteer": 0, "field volunteer": 0, "field research volunteer": 0,
        "student representative": 0, "mental health representative": 0, "class representative": 0,

        # Level 1: Intern / Team Member / Assistant / Editorial Member
        "成员": 1, "推广成员": 1, "编辑部成员": 1, "团队成员": 1, "组员": 1, "部员": 1,
        "队员": 1, "参赛队员": 1, "实习生": 1, "实习": 1, "助理": 1, "助教": 1, "见习生": 1,
        "member": 1, "team member": 1, "promotion member": 1, "editorial member": 1,
        "promotion team member": 1, "editorial team member": 1, "brand promotion team member": 1,
        "intern": 1, "internship": 1, "assistant": 1, "contributor": 1,

        # Level 2: Specialist / Regular Officer / Engineer / Analyst
        "专员": 2, "运营专员": 2, "推广专员": 2, "编辑专员": 2, "品牌专员": 2,
        "工程师": 2, "研发工程师": 2, "分析师": 2, "研究员": 2, "统筹员": 2, "干事": 2,
        "specialist": 2, "operations specialist": 2, "promotion specialist": 2,
        "editorial specialist": 2, "brand promotion specialist": 2, "officer": 2,
        "engineer": 2, "analyst": 2, "researcher": 2, "coordinator": 2,

        # Level 3: Lead / Head / Manager / Director / Founder
        "负责人": 3, "现场负责人": 3, "项目负责人": 3, "业务负责人": 3, "总负责人": 3,
        "主导者": 3, "主管": 3, "经理": 3, "总监": 3, "组长": 3, "部长": 3, "架构师": 3, "创始人": 3,
        "操盘手": 3, "掌盘人": 3, "主操盘手": 3, "主操盘": 3,
        "lead": 3, "field lead": 3, "volunteer field lead": 3, "project lead": 3, "team lead": 3,
        "head": 3, "manager": 3, "director": 3, "chief": 3, "founder": 3
    }

    ROLE_HIERARCHY_NAMES: Dict[int, str] = {
        0: "Volunteer / Student Role (志愿/学生干部/兼职)",
        1: "Member / Intern (成员/实习生/普通组员)",
        2: "Specialist / Officer (正式专员/工程师/干事)",
        3: "Lead / Manager (负责人/组长/总监/主管)",
    }

    ROLE_PROTECTED_DOMAINS: Dict[str, Dict[str, Any]] = {
        "心理委员": {
            "required_keywords": ["心理", "mental health"],
            "forbidden_generalizations": ["student affairs", "cohort representative", "年级代表", "全权负责"],
            "recommended_en": "Class Mental Health Representative"
        },
        "志愿实践成员": {
            "required_keywords": ["志愿", "volunteer"],
            "forbidden_escalations": ["lead", "head", "director", "负责人", "总负责"],
            "recommended_en": "Field Research Volunteer / Volunteer Team Member"
        },
        "推广成员": {
            "required_keywords": ["成员", "member", "team member"],
            "forbidden_escalations": ["specialist", "专员", "lead", "负责人", "chief", "head", "director", "manager", "主管"],
            "recommended_en": "Brand Promotion Team Member"
        },
        "编辑部成员": {
            "required_keywords": ["编辑", "成员", "editorial", "member", "team member"],
            "forbidden_escalations": ["specialist", "专员", "lead", "负责人", "chief", "head", "director", "manager", "主编"],
            "recommended_en": "Editorial Team Member"
        }
    }

    # Safe Read-Only Getters
    @classmethod
    def get_data_depth_levels(cls) -> Dict[str, str]:
        return dict(cls.DATA_DEPTH_LEVELS)

    @classmethod
    def get_result_evidence_levels(cls) -> Dict[str, str]:
        return dict(cls.RESULT_EVIDENCE_LEVELS)

    @classmethod
    def get_decision_planning_keywords(cls) -> List[str]:
        return list(cls.DECISION_PLANNING_KEYWORDS)

    @classmethod
    def get_banned_slop_patterns(cls) -> List[Tuple[str, str]]:
        return list(cls.BANNED_SLOP_PATTERNS)

    @classmethod
    def get_standard_sections(cls) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in cls.STANDARD_SECTIONS.items()}

    @classmethod
    def get_formatting_risks(cls) -> List[Tuple[str, re.Pattern, str]]:
        return list(cls.FORMATTING_RISKS)

    @classmethod
    def get_defense_guide_templates(cls) -> Dict[str, str]:
        return dict(cls.DEFENSE_GUIDE_TEMPLATES)

    @classmethod
    def get_baoyan_spec_ranges(cls) -> Dict[str, Tuple[int, int]]:
        return dict(cls.BAOYAN_SPEC_RANGES)

    @classmethod
    def get_role_kpi_lexicon(cls) -> Dict[str, List[str]]:
        return copy.deepcopy(cls.ROLE_KPI_LEXICON)


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

    @classmethod
    def detect_role_hierarchy_tier(cls, text: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Detects the role hierarchy tier (0-3) using longest-match first.
        Returns (tier, matched_term) or (None, None).
        """
        if not text:
            return None, None
        lower = str(text).strip().lower()
        sorted_terms = sorted(cls.ROLE_HIERARCHY_LEVELS.keys(), key=len, reverse=True)
        for term in sorted_terms:
            if term.lower() in lower:
                return cls.ROLE_HIERARCHY_LEVELS[term], term
        return None, None

    @classmethod
    def check_role_escalation(cls, claimed_role: str, baseline_role: str) -> Optional[Dict[str, Any]]:
        """
        Audits whether a claimed role escalates in tier or drifts in core domain
        relative to baseline role SSOT.
        """
        if not claimed_role or not baseline_role:
            return None

        b_role = baseline_role.strip()
        c_role = claimed_role.strip()
        c_lower = c_role.lower()

        # 1. Protected domain check (e.g. 心理委员 -> Student Affairs, 推广成员 -> Brand Promotion Specialist)
        for prot_key, cfg in cls.ROLE_PROTECTED_DOMAINS.items():
            if prot_key.lower() in b_role.lower():
                forb = cfg.get("forbidden_escalations", [])
                for f_term in forb:
                    pat = r"(?<![a-z0-9_])" + re.escape(f_term.lower()) + r"(?![a-z0-9_])" if re.match(r"^[a-z0-9_]+$", f_term.lower()) else re.escape(f_term.lower())
                    if re.search(pat, c_lower):
                        return {
                            "rule_id": "ROLE_HIERARCHY_INFLATION",
                            "type": "ROLE_HIERARCHY_INFLATION",
                            "claimed_role": c_role,
                            "baseline_role": b_role,
                            "reason": f"Role '{b_role}' was escalated to forbidden term '{f_term}' in '{c_role}'",
                            "fix_suggestion": cfg.get("recommended_en") or "Downgrade role to match baseline tier (e.g. Member / Volunteer)"
                        }
                req_kws = cfg.get("required_keywords", [])
                if req_kws and not any(kw.lower() in c_lower for kw in req_kws):
                    return {
                        "rule_id": "ROLE_DOMAIN_DRIFT",
                        "type": "ROLE_DOMAIN_DRIFT",
                        "claimed_role": c_role,
                        "baseline_role": b_role,
                        "reason": f"Core domain of '{b_role}' was omitted or altered in '{c_role}'",
                        "fix_suggestion": cfg.get("recommended_en") or f"Retain core domain keywords: {req_kws}"
                    }

        # 2. Tier escalation check
        b_tier, b_term = cls.detect_role_hierarchy_tier(b_role)
        c_tier, c_term = cls.detect_role_hierarchy_tier(c_role)

        if b_tier is not None and c_tier is not None and c_tier > b_tier and (c_tier >= 2 and b_tier <= 1 or c_tier >= 3):
            return {
                "rule_id": "ROLE_HIERARCHY_INFLATION",
                "type": "ROLE_HIERARCHY_INFLATION",
                "claimed_role": c_role,
                "claimed_tier": c_tier,
                "claimed_tier_name": cls.ROLE_HIERARCHY_NAMES.get(c_tier, str(c_tier)),
                "baseline_role": b_role,
                "baseline_tier": b_tier,
                "baseline_tier_name": cls.ROLE_HIERARCHY_NAMES.get(b_tier, str(b_tier)),
                "matched_claimed_term": c_term,
                "matched_baseline_term": b_term,
                "reason": f"Role level escalated from {cls.ROLE_HIERARCHY_NAMES.get(b_tier, str(b_tier))} to {cls.ROLE_HIERARCHY_NAMES.get(c_tier, str(c_tier))} without SSOT authorization",
                "fix_suggestion": f"Downgrade role title to match baseline tier (Tier {b_tier})"
            }

        return None

    @classmethod
    def check_metric_scope_drift(cls, claimed_text: str, baseline_text: str) -> List[Dict[str, Any]]:
        """
        Audits whether quantified metrics in claimed_text suffer from scope drift,
        entity substitution, ungrounded currency conversion, or unanchored denominators relative to baseline_text.
        """
        drifts: List[Dict[str, Any]] = []
        if not claimed_text or not baseline_text:
            return drifts

        c_text = claimed_text
        b_text = baseline_text
        c_lower = c_text.lower()
        b_lower = b_text.lower()

        # 1. Currency Conversion Drift ($ / USD introduced without baseline USD)
        has_claimed_usd = bool(re.search(r"(\$|usd|dollar|美元)", c_lower, re.IGNORECASE))
        has_baseline_usd = bool(re.search(r"(\$|usd|dollar|美元)", b_lower, re.IGNORECASE))
        has_baseline_rmb = bool(re.search(r"(¥|￥|rmb|元|万元|cny)", b_lower, re.IGNORECASE))
        if has_claimed_usd and not has_baseline_usd and has_baseline_rmb:
            m_usd = re.search(r"([¥$￥]?\s*~?\s*\$?\s*\d+(?:,\d+)*(?:\.\d+)?\s*(?:k|m|b)?\s*usd|\$[0-9]+[km]?)", c_text, re.IGNORECASE)
            claimed_str = m_usd.group(0) if m_usd else "USD conversion"
            drifts.append({
                "rule_id": "SCOPE_UNAUTHORIZED_CURRENCY",
                "type": "UNAUTHORIZED_CURRENCY_CONVERSION",
                "claimed_text": c_text,
                "claimed_snippet": claimed_str,
                "reason": "Claimed text introduces ungrounded currency conversion ($/USD) not present in SSOT baseline",
                "fix_suggestion": "Preserve original RMB/万元 denomination directly without speculative exchange rate conversion"
            })

        # 2. Scale Denominator Drift (GPA /4.0 or /100 introduced without baseline denominator)
        m_c_gpa = re.search(r"gpa[:\s]*(\d+\.\d+)\s*\/\s*(4(?:\.0)?|100|5)", c_lower)
        if m_c_gpa:
            m_b_denom = re.search(r"gpa[:\s]*(\d+\.\d+)\s*\/\s*(4(?:\.0)?|100|5)", b_lower)
            if not m_b_denom:
                drifts.append({
                    "rule_id": "SCOPE_UNANCHORED_DENOMINATOR",
                    "type": "UNANCHORED_SCALE_DENOMINATOR",
                    "claimed_text": c_text,
                    "claimed_snippet": m_c_gpa.group(0),
                    "reason": f"Claimed text adds ungrounded full scale '/{m_c_gpa.group(2)}' to GPA without official baseline backing",
                    "fix_suggestion": "Preserve baseline GPA value without fabricating denominator (e.g. 'GPA 3.12 (Top 15%)')"
                })

        # 3. Event / Session count to Asset / Artifact count drift
        for m_b in re.finditer(r"(\d+)\s*\+?\s*(?:场|场次|sessions?)", b_lower):
            num = m_b.group(1)
            pat_drift = re.compile(rf"{num}\s*\+?\s*(?:件|个|套|custom\s*promo\s*overlays|promo\s*overlays|kt\s*boards|posters|materials|物料)", re.IGNORECASE)
            if pat_drift.search(c_lower):
                has_session_qualifier = bool(re.search(rf"{num}\s*\+?\s*.*(?:场|session)", c_lower) or re.search(rf"for\s+{num}\s*\+?\s*.*(?:场|session)", c_lower))
                if not has_session_qualifier:
                    drifts.append({
                        "rule_id": "SCOPE_EVENT_TO_ASSET",
                        "type": "METRIC_SCOPE_DRIFT",
                        "number": num,
                        "claimed_text": c_text,
                        "reason": f"Baseline metric measures event/session count ({num}+ 场), but claimed text drifted into artifact/asset quantity ({num}+ items/overlays)",
                        "fix_suggestion": f"Clarify scope as 'for {num}+ livestream sessions' or '为 {num}+ 场直播制作'"
                    })

        # 4. User to Enterprise Lead drift
        for m_b in re.finditer(r"(\d+)\s*\+?\s*(?:人|位|名|潜在用户|用户|fans|users|attendees)", b_lower):
            num = m_b.group(1)
            pat_ent = re.compile(rf"{num}\s*\+?\s*(?:家|个企业|企业客户|企业线索|企业|enterprise\s*clients|business\s*leads|corporate\s*leads|prospects)", re.IGNORECASE)
            if pat_ent.search(c_lower):
                b_has_ent = bool(re.search(rf"{num}\s*\+?\s*(?:家|企业|enterprise|clients|leads)", b_lower))
                if not b_has_ent:
                    drifts.append({
                        "rule_id": "SCOPE_USER_TO_ENTERPRISE",
                        "type": "TARGET_AUDIENCE_DRIFT",
                        "number": num,
                        "claimed_text": c_text,
                        "reason": f"Baseline metric measures C-end prospective individuals/users ({num}+ 人), but claimed text drifted into B-end enterprise leads/clients",
                        "fix_suggestion": f"Retain prospective users/attendees scope ('engaging {num}+ prospective users')"
                    })

        # 5. Peak single-event to Cumulative total drift
        for m_b in re.finditer(r"(?:单篇最高|单场最高|峰值|最高|peak|single[ -]session|single[ -]article)[^0-9\n]{0,15}(\d+(?:,\d+)*(?:\.\d+)?)", b_lower):
            num_str = m_b.group(1)
            num_clean = num_str.replace(",", "")
            # Look for cumulative / total either before or after number (e.g. "total 5,000" or "5,000+ total cumulative")
            pat_cum = re.compile(
                rf"(?:(?:累计|总计|总共|共计|cumulative|total|overall)[^0-9\n]{{0,25}}(?:{re.escape(num_str)}|{re.escape(num_clean)})|(?:{re.escape(num_str)}|{re.escape(num_clean)})[^0-9\n]{{0,25}}(?:累计|总计|总共|共计|cumulative|total|overall))",
                re.IGNORECASE
            )
            if pat_cum.search(c_lower):
                has_peak_qualifier = bool(re.search(r"(?:单篇|单场|峰值|最高|peak|single[ -]session|single[ -]article|per[ -]session)", c_lower))
                if not has_peak_qualifier:
                    drifts.append({
                        "rule_id": "SCOPE_PEAK_TO_CUMULATIVE",
                        "type": "AGGREGATION_DRIFT",
                        "number": num_str,
                        "claimed_text": c_text,
                        "reason": f"Baseline metric '{num_str}' is an isolated single-event peak (单篇/单场最高), but claimed text presents it as cumulative total",
                        "fix_suggestion": "Retain explicit peak qualifier ('peak single-session / peak single-article / 单场最高')"
                    })

        return drifts


__all__ = [
    "AliasRegistry",
    "TaxonomyRegistry",
    "MetricPatternRegistry",
    "QualityRuleRegistry",
]
