"""
Data models and type definitions for JD Analyst subsystem.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class ThresholdType(str, Enum):
    EDUCATION = "EDUCATION"
    EXPERIENCE_YEARS = "EXPERIENCE_YEARS"
    MAJOR = "MAJOR"
    LOCATION = "LOCATION"
    CERTIFICATION = "CERTIFICATION"
    OTHER = "OTHER"


@dataclass
class HardThreshold:
    category: str
    requirement: str
    is_mandatory: bool = True
    min_degree: Optional[str] = None
    min_years: Optional[float] = None
    required_majors: List[str] = field(default_factory=list)


class SkillImportance(str, Enum):
    MUST_HAVE = "MUST_HAVE"
    NICE_TO_HAVE = "NICE_TO_HAVE"


class TechDomain(str, Enum):
    COMPUTE_INFRA = "算力基础设施"
    TRAINING_COMM = "训练通信优化"
    ALIGNMENT_EVAL = "评测对齐"
    LONG_CONTEXT = "长上下文"
    INFERENCE_ACCEL = "推理加速"
    AGENT_WORKFLOW = "Agent与工作流"
    GENERAL_ML = "通用机器学习"
    SOFTWARE_ENG = "软件工程与基础架构"


@dataclass
class CoreSkill:
    name: str
    category: str  # language, framework, tool, theory, hardware
    importance: str  # must_have or nice_to_have
    domain: str
    context: str = ""


@dataclass
class CoreResponsibility:
    title: str
    description: str
    domain: str
    weight: float = 1.0


@dataclass
class ImplicitSignal:
    original_text: str
    translated_meaning: str
    underlying_risk: str
    candidate_countermeasure: str


@dataclass
class BusinessPainPoint:
    aspect: str
    description: str
    evaluation_metric: str


@dataclass
class BoilerplateFiltered:
    text: str
    reason: str


@dataclass
class DecodedJD:
    raw_text: str
    job_title: str
    company_or_dept: str
    hard_thresholds: List[HardThreshold] = field(default_factory=list)
    core_responsibilities: List[CoreResponsibility] = field(default_factory=list)
    core_skills: List[CoreSkill] = field(default_factory=list)
    implicit_signals: List[ImplicitSignal] = field(default_factory=list)
    business_pain_points: List[BusinessPainPoint] = field(default_factory=list)
    filtered_boilerplates: List[BoilerplateFiltered] = field(default_factory=list)
    clean_text: str = ""
    tech_domains: List[str] = field(default_factory=list)


class GapState(str, Enum):
    MATCHED = "MATCHED"
    EXPRESSION_GAP = "EXPRESSION_GAP"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REAL_GAP = "REAL_GAP"
    TO_BE_CONFIRMED = "TO_BE_CONFIRMED"

    @property
    def label_cn(self) -> str:
        mapping = {
            "MATCHED": "已匹配",
            "EXPRESSION_GAP": "表达缺口",
            "INSUFFICIENT_EVIDENCE": "证据不足",
            "REAL_GAP": "真实缺口",
            "TO_BE_CONFIRMED": "待确认",
        }
        return mapping.get(self.value, self.value)

    @property
    def label_en(self) -> str:
        mapping = {
            "MATCHED": "Matched",
            "EXPRESSION_GAP": "Expression Gap",
            "INSUFFICIENT_EVIDENCE": "Insufficient Evidence",
            "REAL_GAP": "Real Gap",
            "TO_BE_CONFIRMED": "To Be Confirmed",
        }
        return mapping.get(self.value, self.value)


@dataclass
class GapItem:
    requirement_name: str
    category: str  # skill, responsibility, threshold, signal
    importance: str  # must_have, nice_to_have, mandatory, implicit
    state: GapState
    score: float  # 1.0, 0.5, 0.0
    candidate_evidence: str
    gap_explanation: str
    actionable_advice: str


@dataclass
class CandidateProfile:
    name: str = "候选人"
    education_level: str = "硕士"  # 博士, 硕士, 本科, 大专
    degree_school: str = ""
    major: str = "计算机科学与技术"
    years_of_experience: float = 3.0
    skills: List[str] = field(default_factory=list)
    project_descriptions: List[str] = field(default_factory=list)
    raw_resume_text: str = ""


@dataclass
class MatcherResult:
    must_have_score: float
    nice_to_have_score: float
    hidden_signal_fit: float
    raw_match_score: float  # 0.6 * must + 0.2 * nice + 0.2 * hidden
    final_match_score: float
    is_hard_vetoed: bool
    hard_veto_reasons: List[str] = field(default_factory=list)
    breakthrough_advice: List[str] = field(default_factory=list)
    gap_matrix: List[GapItem] = field(default_factory=list)
    matched_count: int = 0
    expression_gap_count: int = 0
    insufficient_evidence_count: int = 0
    real_gap_count: int = 0
    to_be_confirmed_count: int = 0


class RedFlagType(str, Enum):
    DEPARTMENT_DISCONNECT = "DEPARTMENT_DISCONNECT"
    ARCHITECTURE_REGRESSION = "ARCHITECTURE_REGRESSION"
    ONE_MAN_FULLSTACK = "ONE_MAN_FULLSTACK"
    INFINITE_EQUITY_PIE = "INFINITE_EQUITY_PIE"
    COMPUTE_SHORTAGE = "COMPUTE_SHORTAGE"
    PSEUDO_LLM_WRAPPER = "PSEUDO_LLM_WRAPPER"
    UNBOUNDED_OVERTIME = "UNBOUNDED_OVERTIME"


@dataclass
class RedFlagItem:
    flag_type: RedFlagType
    title_cn: str
    title_en: str
    severity: str  # HIGH, MEDIUM, LOW
    trigger_snippet: str
    risk_analysis: str
    interview_defense: str


@dataclass
class RedFlagReport:
    flags: List[RedFlagItem] = field(default_factory=list)
    overall_risk_level: str = "LOW"  # LOW, MODERATE, HIGH, SEVERE
    risk_score: int = 0  # 0-100
    summary: str = ""


class ChannelType(str, Enum):
    INTERNAL_REFERRAL = "INTERNAL_REFERRAL"
    RECRUITER_DIRECT = "RECRUITER_DIRECT"
    COLD_APPLICATION = "COLD_APPLICATION"
    HEADHUNTER = "HEADHUNTER"


@dataclass
class ChannelProbability:
    channel_name_cn: str
    channel_name_en: str
    channel_type: ChannelType
    multiplier: float
    min_prob: float
    max_prob: float


@dataclass
class ProbabilityForecast:
    base_min_prob: float
    base_max_prob: float
    listing_age_days: int
    age_decay_multiplier: float
    is_ghost_job_risk: bool
    channel_forecasts: Dict[str, ChannelProbability] = field(default_factory=dict)
    recommended_channel: str = ""
    strategic_summary: str = ""


class QuestionCategory(str, Enum):
    ARCHITECTURE = "ARCHITECTURE"
    PRINCIPLES = "PRINCIPLES"
    BQ = "BQ"
    REVERSE = "REVERSE"


@dataclass
class InterviewQuestion:
    question_id: int
    category_cn: str
    category_en: str
    category_type: QuestionCategory
    question_cn: str
    question_en: str
    jd_signal: str
    interviewer_intent: str
    prep_keypoints: str


@dataclass
class PredictionResult:
    probability_forecast: ProbabilityForecast
    top20_questions: List[InterviewQuestion] = field(default_factory=list)
