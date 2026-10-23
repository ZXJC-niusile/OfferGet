"""
OfferGet Evidence Auditor.
OfferGet native evidence auditing and consistency verification engine.
Synthesizes ProfileContext SSOT evidence, ClaimExtractor, MetricRecalculator,
and Inflation Patterns to generate self-contained, schema-compliant AuditReports.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional, Union

from core.evidence.extractor import ClaimExtractor
from core.evidence.metrics import MetricRecalculator
from core.evidence.models import (
    AuditClaim,
    AuditPattern,
    AuditReport,
    AuditSource,
    AuditTimelineItem,
)
from core.evidence.open_source import OpenSourceAuditor
from core.profile_adapter import (
    ProfileContext,
    ProfileEvidenceIndex,
    build_profile_context,
)


class EvidenceAuditor:
    """
    Synthesizes SSOT facts and resume claims into structured OfferGet audit reports.
    """

    def __init__(
        self,
        profile: Optional[Union[dict, ProfileContext, ProfileEvidenceIndex]] = None,
    ):
        self.profile_context: Optional[ProfileContext] = None
        self.evidence_index: Optional[ProfileEvidenceIndex] = None
        self.raw_profile: Dict[str, Any] = {}

        if profile is not None:
            self.load_profile(profile)

    def load_profile(self, profile: Union[dict, ProfileContext, ProfileEvidenceIndex]) -> None:
        """Loads and indexes SSOT profile."""
        if isinstance(profile, ProfileContext):
            self.profile_context = profile
            self.evidence_index = profile.evidence_index
            self.raw_profile = profile.normalized_profile
        elif isinstance(profile, ProfileEvidenceIndex):
            self.profile_context = None
            self.evidence_index = profile
            self.raw_profile = profile.profile
        elif isinstance(profile, dict):
            self.profile_context = build_profile_context(profile)
            self.evidence_index = self.profile_context.evidence_index
            self.raw_profile = self.profile_context.normalized_profile
        else:
            raise TypeError(f"Unsupported profile type: {type(profile).__name__}")

    def audit(
        self,
        resume_data_or_text: Union[dict, list, str],
        subject_name: Optional[str] = None,
    ) -> AuditReport:
        """
        Performs full evidence audit and returns a schema-compliant AuditReport.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
        subject = subject_name or self._resolve_subject_name()

        # 1. Build Sources
        sources = self._build_sources()
        primary_source_id = sources[0].id if sources else "S-001"

        # 2. Extract Claims
        claims: List[AuditClaim] = []
        if isinstance(resume_data_or_text, dict):
            claims = ClaimExtractor.extract_from_resume_dict(resume_data_or_text)
        elif isinstance(resume_data_or_text, list):
            for idx, item in enumerate(resume_data_or_text):
                b_text = str(item).strip()
                if b_text:
                    claims.extend(ClaimExtractor.extract_claims_from_bullet(b_text, f"C-{idx+1:03d}"))
        elif isinstance(resume_data_or_text, str):
            lines = [l.strip() for l in resume_data_or_text.splitlines() if l.strip()]
            for idx, line in enumerate(lines):
                claims.extend(ClaimExtractor.extract_claims_from_bullet(line, f"C-{idx+1:03d}"))

        if not claims:
            claims.append(AuditClaim(
                id="C-001",
                category="general",
                resume_text="未提供具体主张文本",
                normalized_claim="空主张",
                status="unverifiable",
                risk="low",
                confidence="high",
                analysis="输入未包含可被审计的履历主张。",
                verification_steps=["请提供待审计的履历内容。"],
            ))

        # 3. Audit each claim against SSOT facts
        patterns_map: Dict[str, AuditPattern] = {}
        for claim in claims:
            self._audit_single_claim(claim, primary_source_id, patterns_map)

        # 4. Synthesize Summary & Limitations
        highest_risk_ids = [c.id for c in claims if c.risk in ("high", "critical")]
        conclusion = self._generate_conclusion(claims)
        limitations = [
            "审计结论基于当前已加载的候选人档案与已核验证据。",
            "无法直接取得未经披露的私有雇佣、保密项目或内部绩效评级记录。",
        ]

        # 5. Build Timeline
        timeline = self._build_timeline(sources)

        # 6. Build Next Steps
        next_steps = self._generate_next_steps(claims, patterns_map)

        report = AuditReport(
            metadata={
                "title": "简历主张真实性审计报告",
                "subject": subject,
                "generated_at": now_iso,
                "scope": "简历主张真实性与夸大模式审计",
                "analyst": "OfferGet Evidence Auditor",
                "disclaimer": "结论描述现有证据，不评价人格，也不构成法律认定。",
            },
            summary={
                "conclusion": conclusion,
                "highest_risk": highest_risk_ids,
                "limitations": limitations,
            },
            sources=sources,
            claims=claims,
            patterns=list(patterns_map.values()),
            timeline=timeline,
            next_steps=next_steps,
        )

        return report

    def _resolve_subject_name(self) -> str:
        """Extracts candidate name from SSOT profile."""
        if self.raw_profile:
            cand = self.raw_profile.get("candidate", {})
            if isinstance(cand, dict) and cand.get("name"):
                return str(cand["name"])
            prof = self.raw_profile.get("profile", {})
            if isinstance(prof, dict) and prof.get("name"):
                return str(prof["name"])
        return "候选人"

    def _build_sources(self) -> List[AuditSource]:
        """Constructs evidence source hierarchy from SSOT profile."""
        sources: List[AuditSource] = [
            AuditSource(
                id="S-001",
                title="候选人底稿档案 (candidate_profile.json)",
                type="official_record",
                publisher="OfferGet SSOT",
                reliability="A",
                notes="官方且同期的直接记录，包含经历、学历、已核验指标与技能清单。",
            )
        ]

        if self.raw_profile:
            # Check for GitHub / Open source
            cand = self.raw_profile.get("candidate", {})
            if isinstance(cand, dict) and cand.get("github"):
                sources.append(AuditSource(
                    id="S-002",
                    title="GitHub 公开主页与仓库贡献记录",
                    url=f"https://github.com/{cand['github'].lstrip('@')}",
                    type="public_record",
                    publisher="GitHub",
                    reliability="B",
                    notes="可复现的公开一手记录，用于核验开源贡献、PR 合并与角色。",
                ))

            # Check for Publications
            pubs = self.raw_profile.get("publications", [])
            if pubs:
                sources.append(AuditSource(
                    id="S-003",
                    title="学术出版物与专利名册",
                    type="official_record",
                    publisher="学术检索与官方会议/期刊",
                    reliability="A",
                    notes="已发表论文、专利署名与排序记录。",
                ))

        return sources

    def _audit_single_claim(
        self,
        claim: AuditClaim,
        primary_source_id: str,
        patterns_map: Dict[str, AuditPattern],
    ) -> None:
        """Audits an individual claim, setting status, risk, confidence, analysis, and patterns."""

        # 1. Metric check validation
        if claim.metric:
            errors = MetricRecalculator.validate_metric(claim.metric.to_dict(), claim_id=claim.id)
            if errors:
                claim.status = "contradicted"
                claim.risk = "critical"
                claim.confidence = "high"
                claim.evidence_against = [primary_source_id]
                claim.analysis = f"指标数值存在内部冲突或无法计算：{'; '.join(errors)}。"
                self._record_pattern(
                    patterns_map,
                    name="伪精确",
                    description="看似精确的百分比或指标与显式分子分母或基线结果自相矛盾。",
                    signals=["指标复算不一致", claim.resume_text],
                    claim_id=claim.id,
                    confidence="high",
                )
                return

        # 2. Superlative check
        if claim.category == "superlative":
            claim.status = "unsupported"
            claim.risk = "high"
            claim.confidence = "high"
            claim.evidence_against = [primary_source_id]
            self._record_pattern(
                patterns_map,
                name="没有比较全集的最高级",
                description="使用最高级或排他性措辞，但缺乏公开界定的比较全集或权威第三方数据支持。",
                signals=["最高级措辞", claim.normalized_claim],
                claim_id=claim.id,
                confidence="high",
            )
            return

        # 3. Scope inflation check
        if claim.category == "scope_inflation":
            claim.status = "partially_corroborated"
            claim.risk = "high"
            claim.confidence = "medium"
            claim.evidence_for = [primary_source_id]
            claim.evidence_against = [primary_source_id]
            self._record_pattern(
                patterns_map,
                name="全系统叙事 / 范围漂白",
                description="用宏观全系统的架构链或所有权描述局部个人贡献。",
                signals=["全系统措辞", claim.normalized_claim],
                claim_id=claim.id,
                confidence="medium",
            )
            return

        # 4. Role boundary check
        if claim.category == "role_boundary":
            # Compare with SSOT roles
            verified_roles = self._get_verified_roles()
            strong_claimed = any(w in claim.normalized_claim for w in ["核心作者", "owner", "Owner", "架构师", "全面负责", "主导者"])
            has_strong_in_ssot = any(w in " ".join(verified_roles).lower() for w in ["owner", "架构师", "lead", "负责", "主导"])

            if strong_claimed and not has_strong_in_ssot:
                claim.status = "partially_corroborated"
                claim.risk = "high"
                claim.confidence = "high"
                claim.evidence_for = [primary_source_id]
                claim.evidence_against = [primary_source_id]
                claim.analysis = (
                    f"底稿正式角色为 [{', '.join(verified_roles) or '未明确'}]，"
                    f"简历声称 [{claim.normalized_claim}]，存在角色升格与职责放大。"
                )
                self._record_pattern(
                    patterns_map,
                    name="角色升格",
                    description="将 Contributor 或局部参与者活动升格为 Owner、核心作者或架构师身份。",
                    signals=["强角色措辞与底稿正式职称不符", claim.normalized_claim],
                    claim_id=claim.id,
                    confidence="high",
                )
                return

        # 5. Open source contribution & depth check
        if claim.category == "open_source" or OpenSourceAuditor.is_open_source_claim(claim.resume_text):
            os_patterns = OpenSourceAuditor.audit_claim(claim.resume_text, claim.id, self.raw_profile)
            for p in os_patterns:
                self._record_pattern(
                    patterns_map,
                    name=p.name,
                    description=p.description,
                    signals=p.signals,
                    claim_id=claim.id,
                    confidence=p.confidence,
                )
                if p.name in ("官网到核心引擎歧义", "角色升格"):
                    claim.status = "partially_corroborated"
                    claim.risk = "high"
                    claim.evidence_against = [primary_source_id]
                elif p.name == "品牌或 Star 迁移":
                    if claim.risk != "critical":
                        claim.risk = "high"
            if claim.category == "open_source":
                claim.evidence_for = [primary_source_id]
                return

        # 6. General experience / fact check against SSOT text & anchors
        if not self.raw_profile:
            claim.status = "unverifiable"
            claim.risk = "medium"
            claim.confidence = "low"
            claim.analysis = "未加载底稿档案，无法完成事实比对。"
            return

        from core.fact_guard import FactVerificationGuard
        guard = FactVerificationGuard(self.profile_context or self.evidence_index or self.raw_profile)
        v_res = guard.verify_bullet(claim.resume_text)

        if v_res.get("passed"):
            claim.status = "corroborated"
            claim.risk = "low"
            claim.confidence = "high"
            claim.evidence_for = [primary_source_id]
            claim.analysis = "主张的关键事实、技术栈及数值指标均与底稿官方记录完全吻合。"
        else:
            drifts = v_res.get("drifts", [])
            unverified = v_res.get("unverified_claims", [])

            if drifts:
                claim.status = "contradicted"
                claim.risk = "critical"
                claim.confidence = "high"
                claim.evidence_for = [primary_source_id]
                claim.evidence_against = [primary_source_id]
                drift_msgs = [f"声称 {d.get('claimed_metric')} 超过底稿基线 {d.get('verified_baseline')}" for d in drifts]
                claim.analysis = f"数值指标夸大漂移：{'; '.join(drift_msgs)}。"
            elif unverified:
                unv_reasons = [u.get("reason", "") for u in unverified]
                claim.status = "unsupported"
                claim.risk = "high"
                claim.confidence = "medium"
                claim.evidence_against = [primary_source_id]
                claim.analysis = f"部分技术栈或数值缺少底稿事实依据：{'; '.join(set(unv_reasons))}。"
            else:
                claim.status = "unverifiable"
                claim.risk = "medium"
                claim.confidence = "low"
                claim.analysis = "底稿中未发现直接印证证据，建议由候选人补充内部材料。"

        # 7. Additional Deep Inflation Patterns Check
        c_text = claim.resume_text
        if re.search(r"(?:ai\s*infra|算法中台|模型内核|大模型架构)", c_text, re.I) and re.search(r"(?:前端|页面|表单|css|html|导表|清洗数据|埋点)", c_text, re.I):
            self._record_pattern(
                patterns_map,
                name="术语邻接",
                description="因工作发生在 AI/模型团队附近，把外围前端/页面/数据处理等基础任务表述为 AI Infra 或模型核心架构。",
                signals=["AI 核心词汇与外围界面/数据清洗词汇同屏出现", c_text],
                claim_id=claim.id,
                confidence="medium",
            )
            if claim.risk != "critical":
                claim.risk = "high"

        if re.search(r"(?:融资\s*\d+|数千万|数亿|千万级\s*(?:dau|mau|日活|用户)|千万级流水|大盘日活)", c_text, re.I):
            if not re.search(r"(?:本人负责|独立交付|个人负责|贡献了|由我|其中我)", c_text):
                self._record_pattern(
                    patterns_map,
                    name="团队结果个人化",
                    description="将整个项目/团队宏观业务大盘规模或融资成果展示在个人经历旁，缺乏明确的个人增量归因机制与负责链路。",
                    signals=["宏观大盘规模指标缺少个人归因限定", c_text],
                    claim_id=claim.id,
                    confidence="medium",
                )

        if re.search(r"(?:与.*(?:探讨|交流|互动)|获得.*(?:赞赏|点赞|认可|肯定|回复)|与.*共同讨论)", c_text):
            self._record_pattern(
                patterns_map,
                name="社交邻接转技术授权",
                description="将与核心作者或知名专家的社交互动、点赞、提问回复，包装为联合开发或技术权威背书。",
                signals=["社交互动用语出现在技术产物主张中", c_text],
                claim_id=claim.id,
                confidence="medium",
            )

    def _record_pattern(
        self,
        patterns_map: Dict[str, AuditPattern],
        name: str,
        description: str,
        signals: List[str],
        claim_id: str,
        confidence: str,
    ) -> None:
        """Records or updates an inflation pattern."""
        if name not in patterns_map:
            patterns_map[name] = AuditPattern(
                name=name,
                description=description,
                signals=list(signals),
                claim_ids=[claim_id],
                confidence=confidence,
            )
        else:
            p = patterns_map[name]
            for sig in signals:
                if sig not in p.signals:
                    p.signals.append(sig)
            if claim_id not in p.claim_ids:
                p.claim_ids.append(claim_id)

    def _get_verified_roles(self) -> List[str]:
        """Extracts list of verified role names from SSOT profile."""
        roles: List[str] = []
        if not self.raw_profile:
            return roles

        for exp in self.raw_profile.get("experience", []):
            if isinstance(exp, dict) and exp.get("role"):
                roles.append(str(exp["role"]))
        for exp in self.raw_profile.get("internships", []):
            if isinstance(exp, dict) and exp.get("role"):
                roles.append(str(exp["role"]))
        for proj in self.raw_profile.get("projects", []):
            if isinstance(proj, dict) and proj.get("role"):
                roles.append(str(proj["role"]))

        return roles

    def _generate_conclusion(self, claims: List[AuditClaim]) -> str:
        """Generates concise calibrated summary conclusion."""
        total = len(claims)
        corroborated = sum(1 for c in claims if c.status == "corroborated")
        partially = sum(1 for c in claims if c.status == "partially_corroborated")
        contradicted = sum(1 for c in claims if c.status == "contradicted")
        unsupported = sum(1 for c in claims if c.status == "unsupported")

        if contradicted > 0:
            return (
                f"本次审计共检验 {total} 条原子主张，发现 {contradicted} 条存在直接矛盾或严重指标漂移，"
                f"{partially} 条存在角色升格或全系统叙事放大。建议立即依据底稿基线纠偏。"
            )
        elif partially > 0 or unsupported > 0:
            return (
                f"本次审计共检验 {total} 条原子主张，其中 {corroborated} 条已证实，"
                f"{partially} 条部分证实（存在职责边界扩大），{unsupported} 条缺乏充分证据支持。"
            )
        else:
            return f"本次审计共检验 {total} 条原子主张，全部主张与底稿事实记录一致，无夸大或漂移。"

    def _build_timeline(self, sources: List[AuditSource]) -> List[AuditTimelineItem]:
        """Builds contemporaneous timeline from profile experiences."""
        timeline: List[AuditTimelineItem] = []
        primary_sid = sources[0].id if sources else "S-001"

        if not self.raw_profile:
            return timeline

        for exp in self.raw_profile.get("experience", []):
            if isinstance(exp, dict) and exp.get("dates"):
                company = exp.get("company", "机构")
                role = exp.get("role", "岗位")
                timeline.append(AuditTimelineItem(
                    date=str(exp["dates"]),
                    title=f"{company} · {role}",
                    detail=f"在 {company} 担任 {role}，开展相关研发工作。",
                    source_ids=[primary_sid],
                ))

        for proj in self.raw_profile.get("projects", []):
            if isinstance(proj, dict) and proj.get("dates"):
                pname = proj.get("name", "项目")
                timeline.append(AuditTimelineItem(
                    date=str(proj["dates"]),
                    title=f"项目交付 · {pname}",
                    detail=str(proj.get("description", "") or proj.get("role", "")),
                    source_ids=[primary_sid],
                ))

        return timeline

    def _generate_next_steps(
        self, claims: List[AuditClaim], patterns_map: Dict[str, AuditPattern]
    ) -> List[str]:
        """Generates actionable next steps for verification."""
        steps: List[str] = []
        if "角色升格" in patterns_map:
            steps.append("要求候选人提供针对争议角色的正式任命、Release Note 或代码提交评审记录。")
        if "伪精确" in patterns_map:
            steps.append("核实同屏展示的指标口径，要求提供未经截断的基线数据与统计时间窗口。")
        if "没有比较全集的最高级" in patterns_map:
            steps.append("要求候选人给出最高级（如“最年轻”、“首个”）的公开权威定义与完整对比名册。")
        if "品牌或 Star 迁移" in patterns_map:
            steps.append("要求候选人提供针对开源项目 Star 数或品牌影响力的个人实质增量归因与 PR 链接。")
        if "官网到核心引擎歧义" in patterns_map:
            steps.append("核验候选人已合并的代码 Commit 列表，区分外围文档/官网与底层运行时架构。")
        if "贡献数量漂白" in patterns_map:
            steps.append("区分已合入 (merged) 与关闭未合入 (closed) 的 PR，核实公开仓库提交工件。")
        if "术语邻接" in patterns_map:
            steps.append("分别明确团队业务背景与个人实际技术栈，区分 AI Infra 平台层与业务胶水层。")
        if "团队结果个人化" in patterns_map:
            steps.append("要求候选人提供针对大盘宏观指标（如 DAU/流水）的个人增量贡献说明与归因时间窗口。")
        if "社交邻接转技术授权" in patterns_map:
            steps.append("核验正式角色与已合并代码工件，将社交互动与实际研发产物解耦。")
        if not steps:
            steps.append("主张真实度良好，建议按正常流程进入技术深度答辩环节。")
        return steps
