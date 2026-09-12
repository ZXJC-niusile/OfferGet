"""
OfferGet Skill Gap ROI Engine (core.gap_roi)
===========================================
Analyzes candidate profile against Job Descriptions in the 50% - 80% near-miss zone.
Computes learning difficulty, market frequency, unlock potential, and calculates ROI
to recommend the top 5 highest-leverage skills to acquire.

Skill ROI Formula:
    ROI_score = (jobs_unlocked * market_frequency * priority_weight) / (difficulty_factor * rampup_time_factor)
"""

from __future__ import annotations

import os
import sys
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure OfferGet root is in sys.path
_CORE_DIR = Path(__file__).resolve().parent
_OFFERGET_ROOT = _CORE_DIR.parent
if str(_OFFERGET_ROOT) not in sys.path:
    sys.path.insert(0, str(_OFFERGET_ROOT))

from modules.jd_analyst.decoder import JDDecoder
from modules.jd_analyst.matcher import JDMatcher
from modules.jd_analyst.models import (
    DecodedJD,
    CandidateProfile,
    GapState,
    GapItem,
    SkillImportance,
    TechDomain,
)


# ---------------------------------------------------------------------------
# Comprehensive Domain Skill Knowledge Base
# ---------------------------------------------------------------------------
SKILL_KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
    "vllm": {
        "canonical_name": "vLLM",
        "aliases": ["vllm", "vllm serving", "vllm调度"],
        "domain": "推理加速",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "3-5 天 (精读源码与跑通 Demo)",
        "rampup_time_factor": 2.0,
        "priority_weight": 2.4,
        "actionable_plan": "复刻 vLLM PagedAttention 最小实现并在 GitHub 开源，对比标准 MHA 压测 KV-Cache 显存与吞吐优化",
    },
    "pagedattention": {
        "canonical_name": "PagedAttention",
        "aliases": ["pagedattention", "paged attention", "kv cache pagedattention"],
        "domain": "推理加速与显存管理",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "3-5 天 (手撕分页显存块管理逻辑并跑通压测)",
        "rampup_time_factor": 2.0,
        "priority_weight": 2.3,
        "actionable_plan": "基于 PyTorch/C++ 实现虚拟显存页表物理映射与 BlockTable 调度器，验证并发吞吐翻倍效果",
    },
    "triton": {
        "canonical_name": "Triton",
        "aliases": ["openai triton", "triton算子", "triton kernel"],
        "domain": "底层算子编程",
        "difficulty": "High",
        "difficulty_factor": 3.5,
        "rampup_estimate": "10-14 天 (手撕 FlashAttention/Softmax 算子与 Profiling)",
        "rampup_time_factor": 3.5,
        "priority_weight": 2.5,
        "actionable_plan": "使用 OpenAI Triton 手写融合 Attention 与 Fused CrossEntropy Kernel，对比 PyTorch 原生算子测试显存与带宽提升",
    },
    "cuda": {
        "canonical_name": "CUDA/C++",
        "aliases": ["cuda", "cuda c++", "cuda算子", "c++", "c++17", "c++20"],
        "domain": "底层高性能编程",
        "difficulty": "High",
        "difficulty_factor": 3.5,
        "rampup_estimate": "14-21 天 (手写 GEMM 共享内存分块与 Warp 级调优)",
        "rampup_time_factor": 3.5,
        "priority_weight": 2.5,
        "actionable_plan": "在 CUDA 中实现 SGEMM 共享内存分块与 Double Buffering 优化，利用 Nsight Compute 分析计算带宽饱和度",
    },
    "grpo": {
        "canonical_name": "GRPO (组内相对优势策略优化)",
        "aliases": ["grpo", "group relative policy optimization"],
        "domain": "后训练强化学习对齐",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "5-7 天 (单机多卡跑通无 Critic 强化学习对齐实验)",
        "rampup_time_factor": 2.0,
        "priority_weight": 2.5,
        "actionable_plan": "基于 TRL / OpenRLHF 在多卡环境复现 DeepSeek-R1 风格的纯 GRPO 推理奖励对齐，输出 GSM8K 评测提升曲线",
    },
    "rlhf": {
        "canonical_name": "RLHF/DPO",
        "aliases": ["rlhf", "dpo", "ppo", "kto", "强化学习", "对齐"],
        "domain": "后训练对齐",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "4-6 天 (构建偏好对数据集并跑通 DPO 训练流水线)",
        "rampup_time_factor": 2.0,
        "priority_weight": 2.2,
        "actionable_plan": "使用 LLaMA-Factory 或 TRL 在开源基座上微调 DPO 偏好对齐模型，设计 Reward 评估验证胜率 (Win Rate)",
    },
    "megatron-lm": {
        "canonical_name": "Megatron-LM",
        "aliases": ["megatron-lm", "megatron", "3d并行", "4d并行"],
        "domain": "分布式预训练工程",
        "difficulty": "High",
        "difficulty_factor": 3.5,
        "rampup_estimate": "14-21 天 (多节点并行通信推导与源码二次开发)",
        "rampup_time_factor": 3.5,
        "priority_weight": 2.6,
        "actionable_plan": "搭建虚拟集群调试 Megatron-LM 源码，推导并实现 TP/PP/SP 混合切分显存预算表，开源工程解读博客",
    },
    "deepspeed": {
        "canonical_name": "DeepSpeed (ZeRO-1/2/3)",
        "aliases": ["deepspeed", "zero", "zero-3", "zero-offload"],
        "domain": "分布式训练与推理",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "4-6 天 (配置微调 70B 模型并调优 Offload 吞吐)",
        "rampup_time_factor": 2.0,
        "priority_weight": 2.0,
        "actionable_plan": "基于 DeepSpeed ZeRO-3 搭建 70B 模型多卡 LoRA/全量微调工作流，形成显存显卡配比标准化脚本",
    },
    "nccl": {
        "canonical_name": "NCCL 通信与故障治理",
        "aliases": ["nccl", "infiniband", "roce", "rdma", "通信优化", "慢卡排查", "straggler"],
        "domain": "算力基础设施与网络通信",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "4-6 天 (插桩探针与慢卡诊断排查实战)",
        "rampup_time_factor": 2.0,
        "priority_weight": 2.2,
        "actionable_plan": "编写 NCCL 通信心跳与 ECC 探针脚本，在多卡多机环境模拟 Straggler 慢卡注入并跑通秒级熔断告警",
    },
    "graphrag": {
        "canonical_name": "GraphRAG & 混合检索",
        "aliases": ["graphrag", "hybrid rag", "知识图谱", "向量检索", "rag"],
        "domain": "知识库与企业搜索",
        "difficulty": "Low",
        "difficulty_factor": 1.0,
        "rampup_estimate": "2-4 天 (实体抽取与混合检索管线落地)",
        "rampup_time_factor": 1.0,
        "priority_weight": 1.8,
        "actionable_plan": "基于 Neo4j 与 LlamaIndex 搭建领域 GraphRAG 增强问答系统，集成 BM25 + Dense 双路召回与 Cross-Encoder Rerank",
    },
    "mcp": {
        "canonical_name": "Model Context Protocol (MCP)",
        "aliases": ["mcp", "model context protocol", "mcp server", "mcp client"],
        "domain": "Agent 基础设施与工具协议",
        "difficulty": "Low",
        "difficulty_factor": 1.0,
        "rampup_estimate": "2-3 天 (实现标准 MCP Server/Client 并集成工具链)",
        "rampup_time_factor": 1.0,
        "priority_weight": 2.1,
        "actionable_plan": "基于 Python MCP SDK 编写企业私有数据连接器与代码沙箱，实现与 Claude/开源大模型标准工具调用闭环并在 GitHub 开源",
    },
    "fp8": {
        "canonical_name": "FP8 量化与混合精度",
        "aliases": ["fp8", "e4m3", "e5m2", "fp8量化", "混合精度"],
        "domain": "量化与推理优化",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "4-6 天 (权重/KV-Cache 动态量化与精度损失压测)",
        "rampup_time_factor": 2.0,
        "priority_weight": 2.1,
        "actionable_plan": "在 vLLM/SGLang 中启用 FP8 (E4M3) 权重与 KV-Cache 动态缩放，评测 MMLU 精度保留率与首字生成延迟 (TTFT)",
    },
    "awq": {
        "canonical_name": "AWQ/GPTQ 离线量化",
        "aliases": ["awq", "gptq", "int4", "int8", "量化压缩"],
        "domain": "模型压缩与轻量化",
        "difficulty": "Low",
        "difficulty_factor": 1.0,
        "rampup_estimate": "2-4 天 (构建校准集并跑通 4-bit 权重压缩)",
        "rampup_time_factor": 1.0,
        "priority_weight": 1.7,
        "actionable_plan": "使用 AutoAWQ 对 14B/32B 开源模型实施激活感知权重量化，生成并验证量化模型与部署说明",
    },
    "mlx": {
        "canonical_name": "端侧 NPU / MLX 轻量部署",
        "aliases": ["mlx", "apple mlx", "端侧部署", "npu", "移动端大模型"],
        "domain": "端侧算力与边缘计算",
        "difficulty": "Low",
        "difficulty_factor": 1.0,
        "rampup_estimate": "3-5 天 (Apple Silicon / 端侧 NPU 运行轻量模型)",
        "rampup_time_factor": 1.0,
        "priority_weight": 1.6,
        "actionable_plan": "使用 Apple MLX 框架量化部署 2B-7B 蒸馏基座，实现端侧离线极速推理，录制演示 Demo 并开源工程代码",
    },
    "synthetic_data": {
        "canonical_name": "合成数据与 Evol-Instruct",
        "aliases": ["synthetic data", "evol-instruct", "合成数据", "数据飞轮", "数据清洗"],
        "domain": "数据工程与数据飞轮",
        "difficulty": "Low",
        "difficulty_factor": 1.0,
        "rampup_estimate": "2-3 天 (设计多轮演进 Prompt 与自动化语法校验器)",
        "rampup_time_factor": 1.0,
        "priority_weight": 1.7,
        "actionable_plan": "设计垂直业务领域 Evol-Instruct 合成数据管道，引入 Python AST 校验器自动化去噪，输出 10k 高质语料",
    },
    "langgraph": {
        "canonical_name": "LangGraph 多智能体编排",
        "aliases": ["langgraph", "multi-agent", "多智能体", "agent orchestration"],
        "domain": "智能体系统",
        "difficulty": "Low",
        "difficulty_factor": 1.0,
        "rampup_estimate": "2-4 天 (状态机编排与自省反思循环构建)",
        "rampup_time_factor": 1.0,
        "priority_weight": 1.8,
        "actionable_plan": "使用 LangGraph 构建包含 Plan-and-Solve、代码编写、沙箱测试与自主报错反思修复的四节点智能体流水线",
    },
    "sglang": {
        "canonical_name": "SGLang (RadixAttention)",
        "aliases": ["sglang", "radixattention", "prefix caching"],
        "domain": "高性能推理服务",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "3-5 天 (RadixTree 源码阅读与复杂结构化解码压测)",
        "rampup_time_factor": 2.0,
        "priority_weight": 2.0,
        "actionable_plan": "在复杂多轮问答与固定 Prefix 场景下对比 SGLang RadixAttention 与标准 vLLM 的首字延迟，撰写 Benchmark 报告",
    },
    "moe": {
        "canonical_name": "MoE 路由与负载均衡",
        "aliases": ["moe", "mixture of experts", "mla", "gqa", "稀疏专家架构"],
        "domain": "前沿模型架构",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "5-7 天 (MoE Gate 路由损失推导与小模型跑通)",
        "rampup_time_factor": 2.0,
        "priority_weight": 2.2,
        "actionable_plan": "推导 Expert Routing Auxiliary Loss，基于小型 Transformer 从头训练一个 8x1B 混合专家玩具模型并分析负载分布",
    },
    "slurm": {
        "canonical_name": "Slurm / K8s 集群调度",
        "aliases": ["slurm", "kubernetes", "ks8", "集群调度", "gpu调度"],
        "domain": "算力基础设施与调度",
        "difficulty": "Low",
        "difficulty_factor": 1.0,
        "rampup_estimate": "2-3 天 (编写作业提交脚本与拓扑感知配置)",
        "rampup_time_factor": 1.0,
        "priority_weight": 1.5,
        "actionable_plan": "编写支持容错重试的 Slurm 分布式提交脚本，集成 NCCL 环境变量与 IB 网卡拓扑感知亲和性调度",
    },
    "speculative_decoding": {
        "canonical_name": "投机采样 (Speculative Decoding)",
        "aliases": ["投机采样", "speculative decoding", "草稿模型", "draft model", "medusa"],
        "domain": "推理加速",
        "difficulty": "Medium",
        "difficulty_factor": 2.0,
        "rampup_estimate": "4-6 天 (构建 Draft Model 并验证加速比)",
        "rampup_time_factor": 2.0,
        "priority_weight": 1.9,
        "actionable_plan": "基于 1B Draft Model 与 7B 目标模型落地投机采样，针对代码和数学任务测算端到端推理加速比与 Token 接受率",
    },
}


class SkillGapROIEngine:
    """
    Skill Gap ROI Engine for Near-Miss Job Target Opportunities (50% - 80% match).
    
    Formula:
        ROI_score = (jobs_unlocked * market_frequency * priority_weight) / (difficulty_factor * rampup_time_factor)
    """

    def __init__(self):
        self.decoder = JDDecoder()
        self.matcher = JDMatcher()

    def _normalize_profile(self, candidate_profile: Union[Dict[str, Any], CandidateProfile]) -> CandidateProfile:
        """Converts raw candidate profile dict or instance into CandidateProfile dataclass."""
        if isinstance(candidate_profile, CandidateProfile):
            return candidate_profile

        cand_data = candidate_profile.get("candidate", {}) if "candidate" in candidate_profile else candidate_profile
        name = cand_data.get("name") or cand_data.get("en_name") or "候选人"
        
        # Education
        degree_raw = str(cand_data.get("degree") or cand_data.get("education_level") or "硕士")
        if "博士" in degree_raw:
            edu_level = "博士"
        elif "硕士" in degree_raw:
            edu_level = "硕士"
        elif "大专" in degree_raw or "专科" in degree_raw:
            edu_level = "大专"
        else:
            edu_level = "本科"

        years_exp = float(cand_data.get("years_of_experience") or cand_data.get("experience_years") or 3.0)
        school = str(cand_data.get("institution") or cand_data.get("school") or "")
        major = str(cand_data.get("major") or "计算机科学与技术")

        # Collect skills
        all_skills: List[str] = []
        if "competencies" in candidate_profile and isinstance(candidate_profile["competencies"], dict):
            for group_skills in candidate_profile["competencies"].values():
                if isinstance(group_skills, list):
                    all_skills.extend([str(s) for s in group_skills])
        if "skills" in candidate_profile and isinstance(candidate_profile["skills"], list):
            all_skills.extend([str(s) for s in candidate_profile["skills"]])

        # Collect project descriptions
        project_desc: List[str] = []
        if "projects" in candidate_profile and isinstance(candidate_profile["projects"], list):
            for p in candidate_profile["projects"]:
                if isinstance(p, dict):
                    desc = p.get("description_zh") or p.get("description") or p.get("summary") or ""
                    if desc:
                        project_desc.append(str(desc))

        # Collect experience highlights
        if "experience" in candidate_profile and isinstance(candidate_profile["experience"], list):
            for exp in candidate_profile["experience"]:
                if isinstance(exp, dict) and "highlights" in exp and isinstance(exp["highlights"], list):
                    for hl in exp["highlights"]:
                        if isinstance(hl, dict):
                            claim = hl.get("claim_zh") or hl.get("claim") or ""
                            if claim:
                                project_desc.append(str(claim))

        # Build raw text
        narrative_zh = candidate_profile.get("narrative", {}).get("summary_zh", "")
        raw_text = f"{name} {edu_level} {school} {major} 工作{years_exp}年。\n{narrative_zh}\n" + "\n".join(project_desc)

        return CandidateProfile(
            name=name,
            education_level=edu_level,
            degree_school=school,
            major=major,
            years_of_experience=years_exp,
            skills=all_skills,
            project_descriptions=project_desc,
            raw_resume_text=raw_text,
        )

    def _canonicalize_skill(self, raw_skill_name: str) -> Tuple[str, Dict[str, Any]]:
        """Maps a raw skill name or gap requirement to standard canonical name and metadata."""
        cleaned = re.sub(r"^(技能|核心技能|门槛要求|硬门槛)[\-_：:\s]*", "", raw_skill_name).strip()
        cleaned_lower = cleaned.lower()

        # Check knowledge base direct match or alias
        for key, meta in SKILL_KNOWLEDGE_BASE.items():
            if cleaned_lower == key or cleaned_lower == meta["canonical_name"].lower():
                return meta["canonical_name"], meta
            if any(alias in cleaned_lower for alias in meta.get("aliases", [])):
                return meta["canonical_name"], meta

        # Heuristic fallback for non-cataloged skills
        diff: str = "Medium"
        diff_factor: float = 2.0
        rampup_est: str = "5-7 天 (源码调试与单卡复现核心流程)"
        rampup_factor: float = 2.0
        prio_weight: float = 1.8

        if any(w in cleaned_lower for w in ["cuda", "c++", "kernel", "算子", "万卡", "底层", "分布式并行", "compiler"]):
            diff = "High"
            diff_factor = 3.5
            rampup_est = "14-21 天 (多节点并行调优与底层算子级编写)"
            rampup_factor = 3.5
            prio_weight = 2.4
        elif any(w in cleaned_lower for w in ["rag", "agent", "prompt", "eval", "mcp", "python", "git", "linux", "api", "sft"]):
            diff = "Low"
            diff_factor = 1.0
            rampup_est = "2-3 天 (精读官方文档并构建快速验证 Demo)"
            rampup_factor = 1.0
            prio_weight = 1.6

        fallback_meta = {
            "canonical_name": cleaned,
            "domain": "算法与工程应用",
            "difficulty": diff,
            "difficulty_factor": diff_factor,
            "rampup_estimate": rampup_est,
            "rampup_time_factor": rampup_factor,
            "priority_weight": prio_weight,
            "actionable_plan": f"针对【{cleaned}】在 GitHub 构建最小可复现验证工程，设计 Benchmark 压测对比并输出技术复盘文档与架构图",
        }
        return cleaned, fallback_meta

    def analyze_gap_roi(
        self,
        candidate_profile: Union[Dict[str, Any], CandidateProfile],
        jd_texts_or_list: Union[List[Union[str, Dict[str, Any]]], str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Main analysis method:
        Filters near-miss jobs (50% - 80% match), identifies missing skills,
        computes ROI score according to the formula:
            ROI_score = (jobs_unlocked * market_frequency * priority_weight) / (difficulty_factor * rampup_time_factor)
        and ranks high-leverage recommendations.
        """
        # Ensure list of JDs
        if isinstance(jd_texts_or_list, (str, dict)):
            raw_jds: List[Any] = [jd_texts_or_list]
        else:
            raw_jds = list(jd_texts_or_list)

        candidate = self._normalize_profile(candidate_profile)

        # 1. Match each JD and identify near-miss jobs
        near_miss_jobs: List[Dict[str, Any]] = []
        all_job_evaluations: List[Dict[str, Any]] = []

        for idx, item in enumerate(raw_jds):
            # Parse text from file path or raw string
            jd_text = ""
            company_hint = f"公司_{idx+1}"
            title_hint = f"岗位_{idx+1}"

            if isinstance(item, str):
                if os.path.exists(item) and os.path.isfile(item):
                    try:
                        with open(item, "r", encoding="utf-8") as f:
                            jd_text = f.read()
                    except Exception:
                        jd_text = item
                else:
                    jd_text = item
            elif isinstance(item, dict):
                jd_text = item.get("raw_text") or item.get("text") or item.get("content") or json.dumps(item, ensure_ascii=False)
                company_hint = item.get("company") or company_hint
                title_hint = item.get("job_title") or item.get("role") or title_hint

            decoded_jd = self.decoder.decode(jd_text, job_title_hint=title_hint, company_hint=company_hint)
            match_res = self.matcher.match(decoded_jd, candidate)
            
            # Score as percentage (0.0 - 100.0)
            score_pct = round(match_res.final_match_score * 100, 2)
            
            eval_record = {
                "index": idx,
                "job_title": decoded_jd.job_title,
                "company": decoded_jd.company_or_dept,
                "score_pct": score_pct,
                "raw_match_score": match_res.final_match_score,
                "decoded_jd": decoded_jd,
                "matcher_result": match_res,
            }
            all_job_evaluations.append(eval_record)

            # Near-miss definition: 50% - 80% match
            if 50.0 <= score_pct <= 80.0:
                near_miss_jobs.append(eval_record)

        total_near_miss = len(near_miss_jobs)

        # If no jobs fell strictly into 50-80%, but there are jobs available,
        # inspect jobs in 40-85% to ensure strategic guidance is provided
        evaluation_cohort = near_miss_jobs if near_miss_jobs else [
            j for j in all_job_evaluations if 40.0 <= j["score_pct"] < 90.0
        ]

        # 2. Extract missing skills across near-miss cohort
        # Track: skill_key -> {meta, frequency, jobs_where_missing: list, must_have_count: int}
        missing_skills_map: Dict[str, Dict[str, Any]] = {}

        for job in evaluation_cohort:
            match_res = job["matcher_result"]
            job_score = job["score_pct"]
            
            # Look at gaps in gap_matrix
            for gap in match_res.gap_matrix:
                if gap.category == "skill" and gap.state in (
                    GapState.REAL_GAP,
                    GapState.INSUFFICIENT_EVIDENCE,
                    GapState.TO_BE_CONFIRMED,
                    GapState.EXPRESSION_GAP,
                ):
                    canonical_name, meta = self._canonicalize_skill(gap.requirement_name)
                    if canonical_name not in missing_skills_map:
                        missing_skills_map[canonical_name] = {
                            "canonical_name": canonical_name,
                            "meta": meta,
                            "frequency": 0,
                            "jobs": [],
                            "must_have_count": 0,
                            "nice_have_count": 0,
                        }

                    is_must = (gap.importance == "must_have" or str(gap.importance).upper() == "MUST_HAVE")
                    missing_skills_map[canonical_name]["frequency"] += 1
                    missing_skills_map[canonical_name]["jobs"].append({
                        "job_title": job["job_title"],
                        "company": job["company"],
                        "current_score": job_score,
                        "is_must_have": is_must,
                    })
                    if is_must:
                        missing_skills_map[canonical_name]["must_have_count"] += 1
                    else:
                        missing_skills_map[canonical_name]["nice_have_count"] += 1

            # Also check any core_skills in decoded_jd that candidate text completely missed
            cand_skills_lower = {s.lower() for s in candidate.skills}
            cand_text_lower = candidate.raw_resume_text.lower()
            for c_skill in job["decoded_jd"].core_skills:
                sk_name = c_skill.name
                if sk_name.lower() not in cand_skills_lower and sk_name.lower() not in cand_text_lower:
                    canonical_name, meta = self._canonicalize_skill(sk_name)
                    if canonical_name not in missing_skills_map:
                        missing_skills_map[canonical_name] = {
                            "canonical_name": canonical_name,
                            "meta": meta,
                            "frequency": 0,
                            "jobs": [],
                            "must_have_count": 0,
                            "nice_have_count": 0,
                        }
                    # avoid duplicate counting within same job
                    already_in_job = any(j["job_title"] == job["job_title"] and j["company"] == job["company"] for j in missing_skills_map[canonical_name]["jobs"])
                    if not already_in_job:
                        is_must = (c_skill.importance == SkillImportance.MUST_HAVE.value or c_skill.importance == "must_have")
                        missing_skills_map[canonical_name]["frequency"] += 1
                        missing_skills_map[canonical_name]["jobs"].append({
                            "job_title": job["job_title"],
                            "company": job["company"],
                            "current_score": job_score,
                            "is_must_have": is_must,
                        })
                        if is_must:
                            missing_skills_map[canonical_name]["must_have_count"] += 1
                        else:
                            missing_skills_map[canonical_name]["nice_have_count"] += 1

        # 3. Calculate ROI score for each missing skill
        # Formula: ROI_score = (jobs_unlocked * market_frequency * priority_weight) / (difficulty_factor * rampup_time_factor)
        missing_skills_ranking: List[Dict[str, Any]] = []

        for skill_name, data in missing_skills_map.items():
            meta = data["meta"]
            market_freq = data["frequency"]

            # Estimate jobs unlocked:
            # Acquiring this skill adds estimated 10-15% to match score.
            # Count how many near-miss jobs would reach >= 80% (or qualify for interview)
            jobs_unlocked = 0
            for j in data["jobs"]:
                boost = 14.0 if j["is_must_have"] else 8.0
                projected_score = j["current_score"] + boost
                if projected_score >= 80.0:
                    jobs_unlocked += 1

            # At least 1 job is unlocked/substantially boosted if frequency >= 1
            jobs_unlocked = max(jobs_unlocked, 1 if market_freq > 0 else 0)

            # Priority weight calculation:
            # Must-have jobs carry heavier weight (2.2) than nice-to-have (1.2)
            if market_freq > 0:
                must_ratio = data["must_have_count"] / market_freq
                priority_weight = round(1.2 + 1.2 * must_ratio, 2)
            else:
                priority_weight = float(meta.get("priority_weight", 1.8))

            diff = meta["difficulty"]
            diff_factor = float(meta["difficulty_factor"])
            rampup_est = meta["rampup_estimate"]
            rampup_factor = float(meta["rampup_time_factor"])
            action_plan = meta["actionable_plan"]

            # Compute ROI
            denominator = max(diff_factor * rampup_factor, 0.5)
            numerator = jobs_unlocked * market_freq * priority_weight
            roi_score = round(numerator / denominator, 2)

            missing_skills_ranking.append({
                "skill": skill_name,
                "frequency_in_near_miss": market_freq,
                "jobs_unlocked_estimate": jobs_unlocked,
                "difficulty": diff,
                "rampup_estimate": rampup_est,
                "roi_score": roi_score,
                "actionable_plan": action_plan,
            })

        # Sort by ROI score descending
        missing_skills_ranking.sort(key=lambda x: (x["roi_score"], x["jobs_unlocked_estimate"], x["frequency_in_near_miss"]), reverse=True)

        top_recommendations = missing_skills_ranking[:5]

        # 4. Generate strategic narrative summary
        strategic_summary = self._generate_strategic_summary(
            total_near_miss=total_near_miss,
            total_jobs_scanned=len(raw_jds),
            top_skills=top_recommendations,
        )

        return {
            "total_near_miss_jobs": total_near_miss,
            "missing_skills_ranking": missing_skills_ranking,
            "top_recommendations": top_recommendations,
            "strategic_summary": strategic_summary,
        }

    def _generate_strategic_summary(
        self,
        total_near_miss: int,
        total_jobs_scanned: int,
        top_skills: List[Dict[str, Any]],
    ) -> str:
        """Generates clear, executive-grade narrative advice for career positioning."""
        if not top_skills:
            return (
                f"本次共扫描 {total_jobs_scanned} 个职位，其中临界区岗位 (50%-80% 匹配度) 共 {total_near_miss} 个。"
                "候选人技术栈与目标岗位高度吻合，未发现显著技术短板，建议直接进入高定级与薪酬谈判阶段。"
            )

        top_skill_names = [s["skill"] for s in top_skills[:3]]
        quick_wins = [s for s in top_skills if s["difficulty"] == "Low"]
        deep_moats = [s for s in top_skills if s["difficulty"] in ("Medium", "High")]

        narrative_lines = [
            f"【战局洞察】在扫描的 {total_jobs_scanned} 个职位中，精准锁定 {total_near_miss} 个处于 50%-80% 斩获区边缘的“临界岗位 (Near-Miss Zone)”。",
            f"数据表明，补齐高 ROI 核心短板后，预计可将多达 {sum(s['jobs_unlocked_estimate'] for s in top_skills[:3])} 个岗位从“擦肩而过”转化为“高概率面邀 (Strong Go)”。",
            "",
            "【最高杠杆突破路线建议】",
        ]

        if quick_wins:
            qw_names = "、".join([s["skill"] for s in quick_wins[:2]])
            narrative_lines.append(
                f"1. 极速破局项（1周内见效）：重点攻坚【{qw_names}】。由于上手门槛为 Low，建议按照行动方案（2-3天跑通最小开源验证并同步至 GitHub），以最小时间成本迅速扩大初筛命中面。"
            )

        if deep_moats:
            dm_names = "、".join([s["skill"] for s in deep_moats[:2]])
            narrative_lines.append(
                f"2. 架构护城河项（2-3周攻坚）：重点突破【{dm_names}】。此项为高定级（P8/Staff）技术终面的必考项与硬核防御堡垒，结合源码推导与实操踩坑复盘，可彻底建立面试壁垒。"
            )

        narrative_lines.append("")
        narrative_lines.append(f"【核心优先级排序】：{' > '.join(top_skill_names)}。建议立即按照输出的行动规划 (Actionable Plan) 落地代码与实验成果。")

        return "\n".join(narrative_lines)


def calculate_gap_roi(
    candidate_profile: Union[Dict[str, Any], CandidateProfile],
    jd_texts_or_list: Union[List[Union[str, Dict[str, Any]]], str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Top-level convenience function for calculating skill gap ROI.
    """
    engine = SkillGapROIEngine()
    return engine.analyze_gap_roi(candidate_profile, jd_texts_or_list)
