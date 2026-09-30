"""
OfferGet Defense Question Chain Generator.
OfferGet native multi-layer follow-up questioning and cross-examination engine.
Provides universal 2-4 layer follow-up chains across 5 critical dimensions
and role-adapted phrasing (interviewer, mentor, instructor, judge).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from core.defense.rubrics import DefenseWeaknessDimension


class QuestionChainType(str, Enum):
    DATA_AUTHENTICITY = "data_authenticity"        # 数据真实性与来源链路
    PERSONAL_CONTRIBUTION = "personal_contribution" # 个人贡献与职责边界
    PROJECT_BOUNDARY = "project_boundary"          # 项目定位与系统边界
    RESULT_RELIABILITY = "result_reliability"      # 结果可靠性与指标口径
    INNOVATION = "innovation"                      # 创新点与差异化定位


class DefenseRole(str, Enum):
    TECH_INTERVIEWER = "tech_interviewer"      # 技术面试官: 关注数据流、工程实现与异常处理
    COURSE_INSTRUCTOR = "course_instructor"    # 课程老师: 关注计算依据与任务书对应
    BAOYAN_MENTOR = "baoyan_mentor"            # 保研导师: 关注学术潜质与真实贡献
    COMPETITION_JUDGE = "competition_judge"    # 竞赛评委: 关注对比优势与壁垒
    MATERIAL_REVIEWER = "material_reviewer"    # 答辩审查者: 关注材料依据与闭环


@dataclass
class DefenseQuestion:
    """A single defense question in a follow-up chain."""
    layer: int  # 1 to 4
    chain_type: QuestionChainType
    question_text: str
    target_dimension: DefenseWeaknessDimension
    intent: str
    danger_level: str = "medium"  # low, medium, high


@dataclass
class FollowUpChain:
    """A 2-4 layer progression of defense questions."""
    chain_type: QuestionChainType
    title: str
    questions: List[DefenseQuestion] = field(default_factory=list)
    role: DefenseRole = DefenseRole.TECH_INTERVIEWER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain_type": self.chain_type.value,
            "title": self.title,
            "role": self.role.value,
            "questions": [
                {
                    "layer": q.layer,
                    "question": q.question_text,
                    "dimension": q.target_dimension.value,
                    "intent": q.intent,
                    "danger_level": q.danger_level,
                }
                for q in self.questions
            ],
        }


class DefenseQuestionChain:
    """
    Constructs role-aware follow-up chains from claims, materials, and identified weakness dimensions.
    """

    ROLE_PREFIXES = {
        DefenseRole.TECH_INTERVIEWER: "【技术面试官】",
        DefenseRole.COURSE_INSTRUCTOR: "【任课教师】",
        DefenseRole.BAOYAN_MENTOR: "【保研面试导师】",
        DefenseRole.COMPETITION_JUDGE: "【评委专家】",
        DefenseRole.MATERIAL_REVIEWER: "【材料合规审查者】",
    }

    @classmethod
    def generate_chain(
        cls,
        chain_type: QuestionChainType,
        context_text: str = "",
        role: DefenseRole = DefenseRole.TECH_INTERVIEWER,
        num_layers: int = 3,
    ) -> FollowUpChain:
        """
        Generates a 2-4 layer question chain for the specified dimension.
        """
        layers = min(max(2, num_layers), 4)

        if chain_type == QuestionChainType.DATA_AUTHENTICITY:
            title = "数据真实性与验证口径追问链"
            raw_qs = [
                (1, "该数据是实测、公开数据集、模拟生成、还是课程假设？材料哪一处说明了数据来源？", DefenseWeaknessDimension.DATA_PROVENANCE, "澄清数据来源属性与可查证依据", "high"),
                (2, "如果不是全量真实业务数据，哪些实验结论只能视为原型验证或趋势展示？", DefenseWeaknessDimension.RESULTS_PRESENTATION, "确认结论适用边界，防止过度断言", "medium"),
                (3, "若将现有模块切换到生产级复杂场景，需要重新计算哪些关键参数？底层能否直接平滑接入？", DefenseWeaknessDimension.TECHNICAL_DEPTH, "考察工程实现灵活性与真实架构深度", "high"),
                (4, "面对数据脏乱、缺失或网络抖动等异常，现有算法是如何进行防御性降级的？", DefenseWeaknessDimension.DEFENSE_SAFETY, "压测极限容灾与边界处理", "high"),
            ]
        elif chain_type == QuestionChainType.PERSONAL_CONTRIBUTION:
            title = "个人贡献与职责边界追问链"
            raw_qs = [
                (1, "在这段经历/项目中，你本人独立完成的核心产物是什么？与团队其他人是如何切分工界面的？", DefenseWeaknessDimension.PERSONAL_CONTRIBUTION, "明确本人实际交付物，剥离团队与开源背景", "high"),
                (2, "所涉及的核心算法、模型或框架中，哪些是完全自主研发，哪些是基于成熟开源方案进行二次集成？", DefenseWeaknessDimension.TECHNICAL_DEPTH, "区分开源复用与个人原创贡献", "high"),
                (3, "如果现场要求你对关键业务逻辑或配置做一处改动，你能够独立修改哪一层代码？", DefenseWeaknessDimension.REPRODUCIBILITY, "验证候选人代码级掌控力", "medium"),
                (4, "如果完全剥离团队基础平台与外部辅助工具，你独立贡献的技术壁垒体现在哪里？", DefenseWeaknessDimension.DEFENSE_SAFETY, "终极压力测试个人不可替代性", "high"),
            ]
        elif chain_type == QuestionChainType.PROJECT_BOUNDARY:
            title = "项目定位与系统边界追问链"
            raw_qs = [
                (1, "你所说的“平台/系统/架构重构”，底层是有真实的服务集群与动态计算，还是以原型展示为主？", DefenseWeaknessDimension.PROJECT_POSITIONING, "挤压宏观用词水分，核准真实系统形态", "high"),
                (2, "整个链路中，哪些计算属于离线预计算或静态规则，哪些属于运行时的实时调度？", DefenseWeaknessDimension.TECHNICAL_DEPTH, "探查实时性与技术深度的真实边界", "medium"),
                (3, "当前版本如果面对 10 倍并发或海量数据吞吐，哪个环节会最先成为瓶颈？", DefenseWeaknessDimension.DEFENSE_SAFETY, "压测系统瓶颈认知与架构大局观", "high"),
                (4, "要将当前项目演进为高可用生产系统，下一步最关键必须重构哪一部分？", DefenseWeaknessDimension.PROJECT_POSITIONING, "考察技术演进路径规划能力", "medium"),
            ]
        elif chain_type == QuestionChainType.RESULT_RELIABILITY:
            title = "结果可靠性与指标评估追问链"
            raw_qs = [
                (1, "简历中所陈述的核心收益指标（如耗时降低、准确率提升），其计算公式与基线（Baseline）是什么？", DefenseWeaknessDimension.DATA_PROVENANCE, "核准指标计算口径与基准对比", "high"),
                (2, "评估结果是否包含严格的对比实验、消融实验（Ablation Study）或第三方基准测试？", DefenseWeaknessDimension.RESULTS_PRESENTATION, "检验实验设计的科学性与自洽度", "high"),
                (3, "展示的提升效果是否存在特定工况或样本倾斜？在长尾偶发场景下的表现如何？", DefenseWeaknessDimension.RISK_PHRASING, "探寻局部最优陷阱与泛化短板", "medium"),
                (4, "面对评委对指标合理性的深度质疑，材料中最无可辩驳的一手证据是什么？", DefenseWeaknessDimension.DEFENSE_SAFETY, "寻找最坚实的事实锚点", "high"),
            ]
        else:  # INNOVATION
            title = "技术创新与差异化价值追问链"
            raw_qs = [
                (1, "你所声称的创新点，主要体现在算法模型、工程集成、应用场景还是工作流优化？", DefenseWeaknessDimension.INNOVATION_FRAMING, "引导合理定位创新类型，避免好高骛远", "medium"),
                (2, "与常规开源 Baseline 或业内成熟通用方案相比，你的核心差异化机制体现在哪里？", DefenseWeaknessDimension.TECHNICAL_DEPTH, "考察方案独特性与技术权衡逻辑", "high"),
                (3, "如果评委认为这仅仅是已有工具的组合拼装，你将如何阐述该工程落地的独特价值与复杂度？", DefenseWeaknessDimension.DEFENSE_SAFETY, "演练创新受挫时的稳妥防守策略", "high"),
                (4, "这项工作沉淀出了哪些可复用的代码库、工具脚本或工程设计经验？", DefenseWeaknessDimension.REPRODUCIBILITY, "考察成果沉淀与外溢价值", "medium"),
            ]

        questions: List[DefenseQuestion] = []
        for l_idx in range(layers):
            layer, q_text, dim, intent, danger = raw_qs[l_idx]
            if context_text:
                q_text = f"针对材料中的“{context_text[:30]}”：{q_text}"
            questions.append(
                DefenseQuestion(
                    layer=layer,
                    chain_type=chain_type,
                    question_text=q_text,
                    target_dimension=dim,
                    intent=intent,
                    danger_level=danger,
                )
            )

        return FollowUpChain(
            chain_type=chain_type,
            title=title,
            questions=questions,
            role=role,
        )

    @classmethod
    def get_role_phrasing(cls, question_text: str, role: DefenseRole) -> str:
        """Prefaces question with role-specific tone marker."""
        prefix = cls.ROLE_PREFIXES.get(role, "")
        return f"{prefix} {question_text}".strip()
