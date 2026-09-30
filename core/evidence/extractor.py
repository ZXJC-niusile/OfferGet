"""
OfferGet Claim Extractor.
Decomposes resume text, bullets, and structured experience into atomic AuditClaims.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.evidence.models import AuditClaim, MetricCheck
from core.evidence.open_source import OpenSourceAuditor
from core.registry import MetricPatternRegistry, QualityRuleRegistry


ROLE_TERMS_PATTERN = re.compile(
    r"(?:作为|担任)?\s*(核心作者|maintainer|owner|架构师|负责人|主导者|committer|lead|tech lead|总指挥|首席)",
    re.I,
)
ACTION_ROLE_PATTERN = re.compile(
    r"(主导|牵头|主持|全面负责|从0到1搭建|自主研发|独立负责|统筹)",
    re.I,
)
SUPERLATIVE_PATTERN = re.compile(
    r"(全球最|世界最|业界最|业内最|国内最|最年轻|首个|首创|第一|No\.1|top\s*1|唯一|最先进)",
    re.I,
)
SCOPE_INFLATION_PATTERN = re.compile(
    r"(负责全系统|主导端到端|负责整个|全链路架构|整体重构|统一全栈|负责公司全部)",
    re.I,
)
PLANNED_PATTERN = re.compile(
    r"(计划|规划|当前方向|拟|探索|聚焦|下一阶段|预研)",
    re.I,
)


class ClaimExtractor:
    """
    Extracts atomic claims and candidates from resume text and bullets.
    """

    @classmethod
    def extract_claims_from_bullet(
        cls,
        bullet: str,
        claim_id: str,
        scope: Optional[str] = None,
    ) -> List[AuditClaim]:
        """
        Extracts one or more atomic claims from a single resume bullet point.
        """
        claims: List[AuditClaim] = []
        clean_bullet = bullet.strip()
        if not clean_bullet:
            return claims

        # 1. Main bullet claim (overall proposition)
        main_claim = AuditClaim(
            id=claim_id,
            category="experience_claim",
            resume_text=clean_bullet,
            normalized_claim=clean_bullet,
            status="unverifiable",
            risk="medium",
            confidence="medium",
            analysis="待结合底层事实核验。",
            verification_steps=["核对经历对应之组织、周期与实际产物。"],
        )

        # Check for explicit ratio or change metrics in bullet
        metric_check = cls._extract_explicit_metric_check(clean_bullet)
        if metric_check:
            main_claim.metric = metric_check
            main_claim.category = "metric"

        claims.append(main_claim)

        # 2. Check for Role escalation claims
        role_matches = list(ROLE_TERMS_PATTERN.finditer(clean_bullet)) + list(ACTION_ROLE_PATTERN.finditer(clean_bullet))
        if role_matches:
            roles = [m.group(1) for m in role_matches]
            sub_id = f"{claim_id}-ROLE"
            claims.append(AuditClaim(
                id=sub_id,
                category="role_boundary",
                resume_text=clean_bullet,
                normalized_claim=f"声称担任或行使角色职责：{'/'.join(set(roles))}",
                status="unverifiable",
                risk="high" if any(r in ["核心作者", "owner", "架构师", "全面负责"] for r in roles) else "medium",
                confidence="medium",
                analysis=f"简历中出现强角色/职责措辞：{', '.join(set(roles))}。需核验正式任命或实际主导边界。",
                verification_steps=["要求提供正式任命通知、Release Note、代码提交评审权限或设计评审记录。"],
            ))

        # 3. Check for Superlative claims
        sup_matches = list(SUPERLATIVE_PATTERN.finditer(clean_bullet))
        if sup_matches:
            sups = [m.group(1) for m in sup_matches]
            sub_id = f"{claim_id}-SUPERLATIVE"
            claims.append(AuditClaim(
                id=sub_id,
                category="superlative",
                resume_text=clean_bullet,
                normalized_claim=f"声称具备最高级或排他性属性：{'/'.join(set(sups))}",
                status="unsupported",
                risk="high",
                confidence="high",
                analysis=f"简历使用了最高级措辞：{', '.join(set(sups))}，缺少公开定义的比较全集或权威第三方佐证。",
                verification_steps=["要求给出比较全集的严格定义、统计时间窗口及第三方排名来源。"],
            ))

        # 4. Check for Scope inflation (全系统叙事)
        scope_matches = list(SCOPE_INFLATION_PATTERN.finditer(clean_bullet))
        if scope_matches:
            scs = [m.group(1) for m in scope_matches]
            sub_id = f"{claim_id}-SCOPE"
            claims.append(AuditClaim(
                id=sub_id,
                category="scope_inflation",
                resume_text=clean_bullet,
                normalized_claim=f"声称具备宏观全系统所有权：{'/'.join(set(scs))}",
                status="unverifiable",
                risk="high",
                confidence="medium",
                analysis=f"简历叙事使用了宏观全系统措辞：{', '.join(set(scs))}，需分离个人实际交付产物与候选人能够解释的整体架构。",
                verification_steps=["核验候选人代码产物目录，区分核心实现者与外围胶水层/参与者。"],
            ))

        # 5. Check for Open Source contribution claims
        if OpenSourceAuditor.is_open_source_claim(clean_bullet):
            lvl, safe_phrase = OpenSourceAuditor.classify_level(clean_bullet)
            sub_id = f"{claim_id}-OS"
            claims.append(AuditClaim(
                id=sub_id,
                category="open_source",
                resume_text=clean_bullet,
                normalized_claim=f"声称开源贡献（分级 {int(lvl)} 级 · {lvl.name}）：{clean_bullet}",
                status="unverifiable",
                risk="high" if lvl >= 3 else "medium",
                confidence="medium",
                analysis=f"开源贡献分级参考：建议安全措辞为「{safe_phrase}」。需进一步核查 PR 合并状态与代码影响区域。",
                verification_steps=[
                    "查验 GitHub PR 记录（绝不能把 closed 当作 merged）。",
                    "核实代码贡献区域（核心运行时、独立功能、前端/官网还是仅文档/配置）。",
                ],
            ))

        return claims

    @classmethod
    def _extract_explicit_metric_check(cls, text: str) -> Optional[MetricCheck]:
        """
        Attempts to extract explicit numerator/denominator or baseline/result from text.
        Only forms a MetricCheck when explicit numbers are present.
        """
        # 1. Pattern: A / B (e.g. 200 / 2000, 200/2000) or A项中的B项 ... C%
        m_ratio = re.search(r"(\d+(?:\.\d+)?)\s*(?:/|／|项中(?:有|的))\s*(\d+(?:\.\d+)?)", text)
        m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", text)

        num = float(m_ratio.group(1)) if m_ratio else None
        den = float(m_ratio.group(2)) if m_ratio else None
        disp_pct = float(m_pct.group(1)) if m_pct else None

        # 2. Pattern: 从 A 到 B (from A to B) or 降低至/提升至
        m_change = re.search(
            r"(?:从|由)\s*(\d+(?:\.\d+)?)\s*(?:[a-zA-Z%ms秒小时]+)?\s*(?:提升至|降至|优化至|减少到|增长到|增加到|变更为|->|→)\s*(\d+(?:\.\d+)?)\s*(%|[a-zA-Z]+)?",
            text,
        )
        m_diff = re.search(
            r"(?:提升|降低|减少|增长|增加|缩短)\s*(?:了)?\s*(\d+(?:\.\d+)?)\s*(%|个?百分点)?",
            text,
        )

        base = float(m_change.group(1)) if m_change else None
        res = float(m_change.group(2)) if m_change else None
        disp_change = float(m_diff.group(1)) if m_diff else None
        change_type = None
        if m_diff:
            unit = m_diff.group(2) or ""
            if "百分点" in unit:
                change_type = "percentage_points"
            elif "%" in unit:
                change_type = "relative_percent"

        if (num is not None and den is not None and disp_pct is not None) or (
            base is not None and res is not None and change_type is not None and disp_change is not None
        ):
            return MetricCheck(
                numerator=num,
                denominator=den,
                displayed_percent=disp_pct,
                baseline=base,
                result=res,
                change_type=change_type,
                displayed_change=disp_change,
            )

        return None

    @classmethod
    def extract_from_resume_dict(cls, data: Dict[str, Any]) -> List[AuditClaim]:
        """
        Walks through a structured resume dictionary and extracts all atomic claims.
        """
        claims: List[AuditClaim] = []
        claim_counter = 1

        # 1. Experience bullets
        for exp_idx, exp in enumerate(data.get("experience", [])):
            if not isinstance(exp, dict):
                continue
            exp_company = exp.get("company", f"Org-{exp_idx}")
            exp_role = exp.get("role") or exp.get("title", "")
            scope_desc = f"experience[{exp_idx}] ({exp_company})"

            for b_idx, b in enumerate(exp.get("bullets", [])):
                b_text = b.get("text") if isinstance(b, dict) else str(b)
                if not b_text:
                    continue
                cid = f"C-{claim_counter:03d}"
                claim_counter += 1
                b_claims = cls.extract_claims_from_bullet(b_text, cid, scope=scope_desc)
                claims.extend(b_claims)

            for h_idx, h in enumerate(exp.get("highlights", [])):
                if isinstance(h, dict):
                    h_text = h.get("claim_zh") or h.get("claim_en") or h.get("text")
                    if h_text:
                        cid = h.get("claim_id") or f"C-{claim_counter:03d}"
                        claim_counter += 1
                        h_claims = cls.extract_claims_from_bullet(h_text, cid, scope=scope_desc)
                        claims.extend(h_claims)

        # 2. Projects bullets
        for p_idx, proj in enumerate(data.get("projects", [])):
            if not isinstance(proj, dict):
                continue
            p_name = proj.get("name", f"Project-{p_idx}")
            scope_desc = f"projects[{p_idx}] ({p_name})"

            for b_idx, b in enumerate(proj.get("bullets", [])):
                b_text = b.get("text") if isinstance(b, dict) else str(b)
                if not b_text:
                    continue
                cid = f"C-{claim_counter:03d}"
                claim_counter += 1
                b_claims = cls.extract_claims_from_bullet(b_text, cid, scope=scope_desc)
                claims.extend(b_claims)

            for desc_k in ("description", "description_zh", "description_en"):
                d_text = proj.get(desc_k)
                if d_text:
                    cid = f"C-{claim_counter:03d}"
                    claim_counter += 1
                    d_claims = cls.extract_claims_from_bullet(d_text, cid, scope=scope_desc)
                    claims.extend(d_claims)

        return claims
