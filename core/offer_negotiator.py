"""
OfferGet Offer Negotiator Engine (core.offer_negotiator)
========================================================
Total compensation package valuation, 6 contract trap/red flag detectors,
salary consistency auditing, and high-EQ tactical counter-offer generation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

COMPLIANCE_DISCLAIMER = (
    "提示：以上条款分析基于常见劳动人事合规实践，可能存在一定合规风险，建议结合录用协议原文咨询专业劳动法执业律师或人事合规顾问。"
)


class OfferNegotiator:
    """
    Offer Evaluation and Counter-Offer Negotiation Engine.
    
    Capabilities:
    1. Total Compensation Breakdown:
       Base, Target Bonus, Sign-on, Stock/RSU, Housing Fund, Estimated annual cash.
    2. 6 Contract Trap / Red Flag Detectors (Compliance-softened with disclaimers):
       - Trap 1: Probation salary discount < 80% or probation duration > 6 months.
       - Trap 2: Non-compete clause without statutory monthly compensation or scope too broad.
       - Trap 3: Base salary split with excessive floating performance ratio (>30% floating).
       - Trap 4: Unrealistic equity/RSU vesting cliff or unexercisable terms.
       - Trap 5: Unstated/uncompensated overtime expectations.
       - Trap 6: Discrepancy with stated expected salary from earlier rounds.
    3. Evidence Gate & Tactical Counter-Offer Generator:
       Anchors negotiation claims strictly against verified candidate profile facts and
       competing offers. Fallbacks gracefully to robust professional value narratives
       without hallucinating technical metrics.
    """

    def __init__(self):
        pass

    def evaluate_offer(
        self,
        offer_data: Dict[str, Any],
        candidate_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates the total package, executes 6 contract trap checks,
        and computes compensation certainty breakdown.
        """
        # 1. Parse Basic Information
        company = str(offer_data.get("company") or "目标企业")
        role = str(
            offer_data.get("role")
            or offer_data.get("job_title")
            or (candidate_profile.get("candidate", {}).get("title_zh") if candidate_profile else None)
            or "核心岗位"
        )

        # 2. Extract Base Salary & Performance Split
        monthly_base = float(
            offer_data.get("base_salary_monthly")
            or offer_data.get("monthly_base")
            or offer_data.get("monthly_salary")
            or offer_data.get("base_monthly")
            or 0.0
        )
        months_per_year = float(
            offer_data.get("months_per_year")
            or offer_data.get("salary_months")
            or offer_data.get("months")
            or 12.0
        )

        # Performance Split / Floating Ratio
        split_data = offer_data.get("performance_split", {})
        fixed_ratio = float(split_data.get("fixed_ratio", offer_data.get("fixed_ratio", 1.0)))
        floating_ratio = float(split_data.get("floating_ratio", offer_data.get("floating_ratio", 0.0)))

        # If ratios weren't explicitly provided, check if separate values are given
        if "fixed_base_monthly" in offer_data and monthly_base > 0:
            fixed_val = float(offer_data["fixed_base_monthly"])
            fixed_ratio = round(fixed_val / monthly_base, 4)
            floating_ratio = round(1.0 - fixed_ratio, 4)

        monthly_guaranteed = round(monthly_base * fixed_ratio, 2)
        monthly_floating = round(monthly_base * floating_ratio, 2)
        annual_base = round(monthly_base * months_per_year, 2)
        guaranteed_annual_cash = round(monthly_guaranteed * months_per_year, 2)
        floating_performance_annual = round(monthly_floating * months_per_year, 2)

        # 3. Target Bonus
        target_bonus_annual = float(offer_data.get("target_bonus_annual") or offer_data.get("annual_bonus") or 0.0)
        target_bonus_months = float(offer_data.get("target_bonus_months") or offer_data.get("bonus_months") or 0.0)
        if target_bonus_annual == 0.0 and target_bonus_months > 0.0:
            target_bonus_annual = round(monthly_base * target_bonus_months, 2)

        # 4. Sign-on Bonus
        sign_on_bonus = float(offer_data.get("sign_on_bonus") or offer_data.get("sign_on") or 0.0)

        # 5. Equity / RSU
        stock_data = offer_data.get("stock_rsu") or offer_data.get("equity") or {}
        stock_total_value = float(stock_data.get("total_grant_value") or stock_data.get("total_value") or 0.0)
        vesting_years = float(stock_data.get("vesting_years") or 4.0)
        annualized_stock_value = float(
            stock_data.get("annualized_value")
            or (round(stock_total_value / vesting_years, 2) if vesting_years > 0 else 0.0)
        )

        # 6. Employer Housing Fund (公积金)
        housing_data = offer_data.get("housing_fund") or {}
        if isinstance(housing_data, (int, float)):
            employer_housing_annual = round(float(housing_data) * 12, 2)
        elif isinstance(housing_data, dict):
            monthly_hf = housing_data.get("monthly_employer_amount") or housing_data.get("monthly_amount")
            if monthly_hf is not None:
                employer_housing_annual = round(float(monthly_hf) * 12, 2)
            else:
                rate = float(housing_data.get("rate") or 0.12)
                # Cap base in tier-1 Chinese cities is approximately 35,000 RMB
                capped_base = min(monthly_base, 35000.0) if monthly_base > 0 else 35000.0
                employer_housing_annual = round(capped_base * rate * 12, 2)
        else:
            employer_housing_annual = round(min(monthly_base, 35000.0) * 0.12 * 12, 2)

        # Total Cash and Total Package
        total_annual_cash = round(annual_base + target_bonus_annual + sign_on_bonus, 2)
        total_annual_package = round(total_annual_cash + annualized_stock_value + employer_housing_annual, 2)
        cash_ratio = round(total_annual_cash / total_annual_package, 4) if total_annual_package > 0 else 1.0

        total_compensation = {
            "monthly_base": monthly_base,
            "months_per_year": months_per_year,
            "annual_base": annual_base,
            "monthly_guaranteed_base": monthly_guaranteed,
            "monthly_floating_kpi": monthly_floating,
            "guaranteed_annual_cash": guaranteed_annual_cash,
            "floating_performance_annual": floating_performance_annual,
            "target_bonus_months": target_bonus_months,
            "target_bonus_annual": target_bonus_annual,
            "sign_on_bonus": sign_on_bonus,
            "stock_rsu_total": stock_total_value,
            "stock_rsu_annualized": annualized_stock_value,
            "vesting_years": vesting_years,
            "employer_housing_fund_annual": employer_housing_annual,
            "total_annual_cash": total_annual_cash,
            "total_annual_package": total_annual_package,
            "cash_ratio": cash_ratio,
        }

        # 7. Execute 6 Contract Trap Detectors
        traps = [
            self._detect_probation_trap(offer_data),
            self._detect_non_compete_trap(offer_data),
            self._detect_salary_split_trap(offer_data, monthly_base, fixed_ratio, floating_ratio),
            self._detect_equity_trap(offer_data, stock_data),
            self._detect_overtime_trap(offer_data),
            self._detect_salary_discrepancy_trap(offer_data, candidate_profile, monthly_base, total_annual_cash),
        ]

        detected_traps = [t for t in traps if t["detected"]]
        trap_count = len(detected_traps)
        critical_count = sum(1 for t in detected_traps if t["severity"] == "CRITICAL")
        high_count = sum(1 for t in detected_traps if t["severity"] == "HIGH")

        if critical_count > 0:
            risk_level = "CRITICAL"
        elif high_count >= 2:
            risk_level = "HIGH"
        elif trap_count >= 1:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Overall Offer Quality Score (0-100)
        # Deduct for traps and low cash ratio
        penalty = critical_count * 25 + high_count * 15 + (trap_count - critical_count - high_count) * 8
        if cash_ratio < 0.60:
            penalty += 10
        overall_score = max(round(100 - penalty, 1), 20.0)

        # Risk and Evaluation Narrative
        narrative = self._generate_evaluation_narrative(
            company=company,
            role=role,
            total_compensation=total_compensation,
            detected_traps=detected_traps,
            risk_level=risk_level,
            overall_score=overall_score,
        )

        return {
            "company": company,
            "role": role,
            "total_compensation": total_compensation,
            "contract_traps": traps,
            "detected_traps": detected_traps,
            "trap_count": trap_count,
            "critical_trap_count": critical_count,
            "high_trap_count": high_count,
            "risk_level": risk_level,
            "overall_score": overall_score,
            "evaluation_narrative": narrative,
            "candidate_profile": candidate_profile,
            "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        }

    # ---------------------------------------------------------------------------
    # 6 Individual Trap Detectors
    # ---------------------------------------------------------------------------

    def _detect_probation_trap(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trap 1: Probation salary discount < 80% or probation duration > 6 months.
        Labor Contract Law Articles 19 & 20.
        """
        prob_data = offer_data.get("probation", {})
        duration = float(prob_data.get("duration_months") or prob_data.get("months") or 0.0)
        discount_ratio = float(
            prob_data.get("salary_discount_rate")
            or prob_data.get("salary_ratio")
            or prob_data.get("discount_ratio")
            or 1.0
        )
        social_insurance = prob_data.get("pay_social_insurance", True)
        clause_text = str(prob_data.get("clause") or prob_data.get("description") or "")

        detected = False
        reasons = []
        severity = "NONE"

        # Check duration > 6 months
        if duration > 6:
            detected = True
            reasons.append(
                f"试用期约定为【{duration} 个月】，超出《劳动合同法》第十九条关于最长试用期（不超过6个月）的法定基准，建议协商调整为合规期限"
            )
            severity = "CRITICAL"
        elif duration > 3 and "三年" not in clause_text:
            # If 1-3 year contract, max probation is 2 months
            pass

        # Check discount < 80% (0.80)
        if discount_ratio < 0.80:
            detected = True
            reasons.append(
                f"试用期工资发放比例约定为正式工资的【{int(discount_ratio * 100)}%】，低于《劳动合同法》第二十条规定的不得低于80%的合规基准，建议按法定比例或100%全额发放"
            )
            severity = "CRITICAL"

        # Check social insurance during probation
        if social_insurance is False or "试用期不缴纳社保" in clause_text:
            detected = True
            reasons.append(
                "条款声明试用期内不缴纳社保公积金，可能违反《社会保险法》用人单位参保缴费相关规定，存在较大合规瑕疵与用工风险"
            )
            severity = "CRITICAL"

        # Check text heuristics
        if not detected and clause_text:
            if re.search(r"试用期.*(70%|七折|六折|60%|半薪)", clause_text):
                detected = True
                reasons.append("条款文本中包含低于 80% 的试用期薪资折损表述，存在合规风险")
                severity = "CRITICAL"
            elif re.search(r"试用期.*([7-9]个月|1年|一年|半年以上)", clause_text):
                detected = True
                reasons.append("条款文本中包含可能超过 6 个月的试用期约定，存在合规风险")
                severity = "CRITICAL"

        return {
            "trap_id": "TRAP_01_PROBATION",
            "name": "试用期薪资折扣与期限合规陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "试用期期限与薪资比例符合劳动法规与常见合规标准。",
            "legal_basis": (
                "根据《中华人民共和国劳动合同法》第十九条、第二十条规定：三年以上固定期限和无固定期限劳动合同，"
                "试用期法定上限为六个月；劳动者在试用期的工资通常不得低于本单位相同岗位最低档工资或者劳动合同约定工资的百分之八十。"
            ),
            "negotiation_countermeasure": (
                "建议向 HR 友好沟通并核对录用函条款：“希望试用期约定在法定的 3-6 个月之内，试用期薪资建议按正式薪资 100% 全额发放"
                "（或不低于 80% 法定参考比例），入职首日起依法依规足额缴纳五险一金”。"
            ),
            "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        }

    def _detect_non_compete_trap(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trap 2: Non-compete clause without statutory monthly compensation or scope too broad.
        Labor Contract Law Articles 23 & 24.
        """
        nc_data = offer_data.get("non_compete", {})
        applies = nc_data.get("applies", False)
        duration = float(nc_data.get("duration_months") or nc_data.get("months") or 0.0)
        comp_ratio = float(nc_data.get("monthly_compensation_rate") or nc_data.get("compensation_ratio") or 0.0)
        included_in_salary = nc_data.get("compensation_included_in_salary", False)
        scope = str(nc_data.get("scope") or "")
        clause_text = str(nc_data.get("clause") or nc_data.get("description") or "")

        detected = False
        reasons = []
        severity = "NONE"

        # Check duration > 24 months
        if applies and duration > 24:
            detected = True
            reasons.append(
                f"竞业限制期限约定为【{duration} 个月】，超出《劳动合同法》第二十四条规定的最长 2 年合规上限，建议协商缩减"
            )
            severity = "CRITICAL"

        # Check compensation claimed to be included in monthly wage
        if applies and (included_in_salary or "包含在日常工资" in clause_text or "月薪已含竞业" in clause_text or "不再另行支付" in clause_text):
            detected = True
            reasons.append(
                "约定‘竞业补偿金已包含在日常月薪中且离职后不另行支付’，在司法实务中通常倾向于认定该类条款不能免除用人单位离职后的法定补偿义务，可能存在较大合规争议与法律风险"
            )
            severity = "CRITICAL"
        elif applies and comp_ratio <= 0.0 and ("离职后支付" not in clause_text):
            detected = True
            reasons.append(
                "竞业限制条款未明确约定离职后按月支付的经济补偿金标准，可能影响条款履行的约束力与合理性（行业常见参考不低于离职前月均工资的 30%）"
            )
            severity = "HIGH"

        # Check overly broad scope
        if applies and scope:
            if re.search(r"(所有|全行业|任何|全部).*?(互联网|人工智能|软件|科技|算法)", scope):
                detected = True
                reasons.append(
                    f"竞业限制范围较为泛化（【{scope[:40]}...】），建议协商限定于具备实际竞争关系的核心实体清单"
                )
                if severity != "CRITICAL":
                    severity = "HIGH"

        # Text search fallback
        if not detected and clause_text:
            if "竞业" in clause_text and ("全行业" in clause_text or "任何互联网" in clause_text or "不另行补偿" in clause_text):
                detected = True
                reasons.append("条款文本中包含无偿竞业或泛行业宽泛竞业约定，存在一定合规风险")
                severity = "HIGH"

        return {
            "trap_id": "TRAP_02_NON_COMPETE",
            "name": "竞业限制无偿化与范围泛化陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "未设置显失公平的竞业限制条款或条款整体合规。",
            "legal_basis": (
                "根据《中华人民共和国劳动合同法》第二十三条、第二十四条及相关司法解释实践：用人单位与劳动者约定竞业限制的，"
                "通常应在解除或终止劳动合同后在竞业限制期限内按月给予经济补偿；司法实务中普遍倾向于认为在职期间‘工资已含竞业补偿’存在合规瑕疵；"
                "竞业期限法定最长一般不超过二年。"
            ),
            "negotiation_countermeasure": (
                "建议向 HR 提出合理的条款优化建议：“1. 建议规范在职期间竞业补偿表述；2. 建议明确离职时由用人单位书面决定是否正式启动竞业程序及离职后按月补偿标准"
                "（行业建议参考前12个月平均月薪30%-50%）；3. 建议竞业范围明确附录双方认可的核心直接竞品清单，避免使用泛行业定义”。"
            ),
            "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        }

    def _detect_salary_split_trap(
        self,
        offer_data: Dict[str, Any],
        monthly_base: float,
        fixed_ratio: float,
        floating_ratio: float,
    ) -> Dict[str, Any]:
        """
        Trap 3: Base salary split with excessive floating performance ratio (>30% floating).
        """
        detected = False
        reasons = []
        severity = "NONE"

        # Check floating ratio > 30%
        if floating_ratio > 0.30:
            detected = True
            reasons.append(
                f"月薪中浮动绩效比例达到【{int(floating_ratio * 100)}%】（固定基本工资占 {int(fixed_ratio * 100)}%），浮动比例偏高，可能增加月度现金流的不确定性"
            )
            severity = "CRITICAL" if floating_ratio >= 0.50 else "HIGH"

        # Check if base is artificially suppressed to local minimum wage
        fixed_amount = monthly_base * fixed_ratio
        if 0 < fixed_amount <= 3000 and monthly_base > 15000:
            detected = True
            reasons.append(
                f"固定基本工资相对较低（【{fixed_amount} 元】），在经济补偿金及加班基数计算等实务中可能存在争议风险"
            )
            severity = "CRITICAL"

        # Text search in salary notes
        notes = str(offer_data.get("salary_structure_notes") or offer_data.get("salary_notes") or "")
        if "浮动考核" in notes and "扣减" in notes:
            if not detected:
                detected = True
                reasons.append("薪资附注中包含单方考核扣减浮动绩效的约定，可能增加薪资发放的随意性与履约风险")
                severity = "HIGH"

        return {
            "trap_id": "TRAP_03_SALARY_SPLIT",
            "name": "基本薪资拆分与高额浮动绩效陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "固定基本工资占比达标，现金流确定性保障良好。",
            "legal_basis": (
                "根据《中华人民共和国劳动合同法》及各地工资支付规定相关实践：用人单位若将约定月薪大比例拆分为浮动绩效，"
                "可能赋予用人单位过大的单方考核裁量权，在考核机制不清晰时容易引发劳动争议与现金流不确定性风险。"
            ),
            "negotiation_countermeasure": (
                "建议提出稳健的薪酬结构沟通：“立足岗位专业价值与长远发展，薪酬确定性是信任基石。建议将固定月薪比例提升至 80% 以上"
                "（或争取更高确定性现金），如包含浮动绩效，建议在录用协议或附件中明确客观、可度量、非主观裁量的考核细则与发放机制”。"
            ),
            "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        }

    def _detect_equity_trap(self, offer_data: Dict[str, Any], stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trap 4: Unrealistic equity/RSU vesting cliff or unexercisable terms.
        """
        cliff_years = float(stock_data.get("cliff_years") or 1.0)
        vesting_schedule = str(stock_data.get("vesting_schedule") or "")
        repurchase_clause = str(
            stock_data.get("repurchase_clause")
            or stock_data.get("repurchase_terms")
            or stock_data.get("exit_terms")
            or ""
        )
        liquidity = str(stock_data.get("liquidity") or stock_data.get("liquidity_status") or "")
        total_pool_disclosed = stock_data.get("total_pool_disclosed", True)

        detected = False
        reasons = []
        severity = "NONE"

        # Check Cliff > 1 year
        if cliff_years > 1:
            detected = True
            reasons.append(
                f"期权/RSU 设置了【{cliff_years} 年】的归属等待期 (Cliff)（常见行业惯例通常为 1 年），可能增加兑现前的沉没成本"
            )
            severity = "HIGH"

        # Check forced repurchase at par value (1分钱/0.01元/面值回购)
        if re.search(r"(面值|0\.01元|1分钱|原始出资额|成本价).*?(回购|收回|作废)", repurchase_clause):
            detected = True
            reasons.append(
                "期权退出协议约定离职时公司可按面值/成本价强制回购已归属期权，对员工既得权益限制较为苛刻，在类似争议判例中存在被认定为显失公平的风险"
            )
            severity = "CRITICAL"

        # Check IPO only
        if "仅在上市后" in repurchase_clause or "上市后方可行权" in repurchase_clause:
            detected = True
            reasons.append("期权条款约定‘仅在公司成功上市后方可行权’且未明确行权与回购机制，流动性存在一定不确定性")
            if severity != "CRITICAL":
                severity = "HIGH"

        # Check undisclosed total pool
        if total_pool_disclosed is False or "份额未定" in vesting_schedule:
            detected = True
            reasons.append("未明确披露期权池总股本或估值基准，持股比例与真实价值测算存在不透明性")
            if severity == "NONE":
                severity = "MEDIUM"

        return {
            "trap_id": "TRAP_04_EQUITY_CLIFF",
            "name": "期权超长等待期与掠夺性强制回购陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "期权/RSU 归属机制与退出条款处于合理行业范围。",
            "legal_basis": (
                "根据公司法及股权激励争议司法裁判实务：股权期权属于对核心人才长期贡献的劳动激励对价。"
                "若在协议中单方设定离职无条件按名义面值强制回购已归属权益，在司法实践中可能被认定为显失公平或格式条款效力存疑。"
            ),
            "negotiation_countermeasure": (
                "建议向公司期权管理部门提出条款合理化沟通：“1. 建议采用行业常见的 1 年 Cliff 归属机制（满 1 年归属 25%，后续按季度均匀归属）；"
                "2. 建议明确已归属期权离职时的公允退出机制或保留机制，避免极端低价强制回购约定”。"
            ),
            "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        }

    def _detect_overtime_trap(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trap 5: Unstated/uncompensated overtime expectations.
        """
        work_data = offer_data.get("working_hours") or offer_data.get("working_hours_overtime") or {}
        if isinstance(work_data, str):
            work_text = work_data
            work_system = ""
            overtime_pay = ""
        else:
            work_text = str(work_data.get("clause") or work_data.get("description") or "")
            work_system = str(work_data.get("system") or "")
            overtime_pay = str(work_data.get("overtime_pay") or "")

        detected = False
        reasons = []
        severity = "NONE"

        # Check comprehensive working hours / flexible system without approval
        if work_system in ("comprehensive", "综合工时制", "不定时工时制", "flexible"):
            approved = work_data.get("labor_bureau_approved", False) if isinstance(work_data, dict) else False
            if not approved:
                detected = True
                reasons.append("实行特殊工时制未明确提供人社部门行政审批许可，在加班核算与工时制度合规上可能存在争议风险")
                severity = "HIGH"

        # Check uncompensated overtime clauses
        if overtime_pay in ("none", "included_in_base", "dinner_stipend_only") or re.search(
            r"(包揽所有加班|月薪已包揽|不设加班费|无加班工资|加班视为自愿|无偿加班|仅报销晚餐打车)",
            work_text
        ):
            detected = True
            reasons.append("合同条款注明‘月薪已包揽一切加班、不支付加班费或仅提供餐补打车报销’，可能存在排除劳动者法定报酬权利的合规争议")
            severity = "HIGH"

        return {
            "trap_id": "TRAP_05_OVERTIME",
            "name": "工时制度瑕疵与无偿高压加班陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "工时制与考勤加班规范符合国家法定与行业标准。",
            "legal_basis": (
                "根据《中华人民共和国劳动法》及工时审批相关规定：实行特殊工时制通常须经人力资源社会保障行政部门审批备案；"
                "法定标准工作时间以外的延长工作时间，用人单位应依法安排补休或支付相应加班报酬，格式条款单方排除加班报酬在争议仲裁中可能面临不予支持的风险。"
            ),
            "negotiation_countermeasure": (
                "建议在录用沟通中探询日常工作节奏：“建议确认岗位适用标准工时制，对阶段性业务攻坚加班建议明确以调休或法定方式平衡，"
                "建议优化录用函中薪资包揽一切加班的相关表述”。"
            ),
            "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        }

    def _detect_salary_discrepancy_trap(
        self,
        offer_data: Dict[str, Any],
        candidate_profile: Optional[Dict[str, Any]],
        monthly_base: float,
        total_annual_cash: float,
    ) -> Dict[str, Any]:
        """
        Trap 6: Discrepancy with stated expected salary from earlier rounds.
        """
        expected_base = 0.0
        expected_annual = 0.0

        # Extract expectation from offer_data or candidate_profile
        exp_data = offer_data.get("candidate_expected") or offer_data.get("expected_salary") or {}
        if isinstance(exp_data, (int, float)):
            expected_base = float(exp_data)
        elif isinstance(exp_data, dict):
            expected_base = float(exp_data.get("expected_base_monthly") or exp_data.get("monthly_base") or 0.0)
            expected_annual = float(exp_data.get("expected_total_annual") or exp_data.get("annual_total") or 0.0)

        if expected_base == 0.0 and candidate_profile:
            cand_exp = candidate_profile.get("salary_expectation") or candidate_profile.get("candidate", {}).get("expected_salary") or {}
            if isinstance(cand_exp, dict):
                expected_base = float(cand_exp.get("expected_base_monthly") or cand_exp.get("monthly_base") or 0.0)
                expected_annual = float(cand_exp.get("expected_total_annual") or cand_exp.get("annual_total") or 0.0)

        detected = False
        reasons = []
        severity = "NONE"

        # Compare Monthly Base Gap
        if expected_base > 0 and monthly_base > 0:
            base_gap_pct = (expected_base - monthly_base) / expected_base
            if base_gap_pct >= 0.15:
                detected = True
                reasons.append(
                    f"Offer 固定月薪（{int(monthly_base)} 元）显著低于前期沟通的期望月薪（{int(expected_base)} 元），差距达 {round(base_gap_pct * 100, 1)}%"
                )
                severity = "HIGH"
            elif base_gap_pct >= 0.08:
                detected = True
                reasons.append(
                    f"Offer 固定月薪较前期沟通期望存在微幅落差（差距 {round(base_gap_pct * 100, 1)}%），具备合理的向上对齐空间"
                )
                severity = "MEDIUM"

        # Compare Annual Cash Gap
        if expected_annual > 0 and total_annual_cash > 0:
            annual_gap_pct = (expected_annual - total_annual_cash) / expected_annual
            if annual_gap_pct >= 0.15 and not detected:
                detected = True
                reasons.append(
                    f"Offer 年度现金总包（{int(total_annual_cash)} 元）低于前期预期（{int(expected_annual)} 元），差距达 {round(annual_gap_pct * 100, 1)}%"
                )
                severity = "HIGH"

        return {
            "trap_id": "TRAP_06_SALARY_DISCREPANCY",
            "name": "前期沟通预期薪资倒挂与压低陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "Offer 薪酬水平与前期沟通期望对齐度良好。",
            "legal_basis": (
                "薪酬沟通与定级实务：录用薪酬与前期沟通预期产生落差时，通常源于薪酬宽带、职级定级或部门预算平衡考量，"
                "建议通过客观梳理自身专业贡献与市场对标进行理性争取。"
            ),
            "negotiation_countermeasure": (
                "建议以客观能力与前期预期为基准进行友好沟通：“前期与业务团队沟通深入，岗位匹配度获得充分认可。"
                "当前 Offer 的月度 Base 相比前期核心预期存在一定落差。为保障全心投入，期望能够拉齐至合理水平；"
                "或在月薪不变的前提下，通过增加首年 Sign-on Bonus 予以平衡”。"
            ),
            "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        }

    # ---------------------------------------------------------------------------
    # Evidence Gate: Fact Extraction & Grounding
    # ---------------------------------------------------------------------------

    @staticmethod
    def _extract_evidence_and_gate(
        candidate_profile: Optional[Dict[str, Any]],
        competing_offers: Optional[List[Dict[str, Any]]],
        role: str = "",
    ) -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
        """
        Evidence Gate:
        Extracts verified factual claims from candidate_profile and competing_offers.
        Identifies unsupported claims and pending questions.

        Returns:
            (profile_grounded, competing_grounded, all_grounded, unsupported_claims, pending_questions)
        """
        profile_grounded: List[str] = []
        competing_grounded: List[str] = []
        unsupported_claims: List[str] = []
        pending_questions: List[str] = []

        # 1. Extract from candidate profile
        if isinstance(candidate_profile, dict):
            # Experiences
            experiences = candidate_profile.get("experience") or candidate_profile.get("work_experience") or []
            if isinstance(experiences, list):
                for exp in experiences:
                    if not isinstance(exp, dict):
                        continue
                    exp_role = exp.get("role") or exp.get("title") or "核心岗位"
                    highlights = exp.get("highlights") or exp.get("achievements") or exp.get("bullets") or []
                    if isinstance(highlights, list):
                        for h in highlights:
                            if isinstance(h, dict):
                                claim = h.get("claim_zh") or h.get("claim") or h.get("description")
                                if claim and str(claim).strip():
                                    profile_grounded.append(str(claim).strip())
                                elif h.get("verified_metrics"):
                                    metrics_str = ", ".join(f"{k}: {v}" for k, v in h["verified_metrics"].items())
                                    profile_grounded.append(f"{exp_role}期间达成核心量化成果（{metrics_str}）")
                            elif isinstance(h, str) and h.strip():
                                profile_grounded.append(h.strip())

            # Projects
            projects = candidate_profile.get("projects") or candidate_profile.get("project_experience") or []
            if isinstance(projects, list):
                for proj in projects:
                    if not isinstance(proj, dict):
                        continue
                    p_name = proj.get("name") or proj.get("title") or "核心项目"
                    p_highlights = proj.get("highlights") or proj.get("achievements") or []
                    if isinstance(p_highlights, list) and p_highlights:
                        for ph in p_highlights:
                            if isinstance(ph, dict):
                                c = ph.get("claim_zh") or ph.get("claim") or ph.get("description")
                                if c and str(c).strip():
                                    profile_grounded.append(f"【{p_name}】{str(c).strip()}")
                            elif isinstance(ph, str) and ph.strip():
                                profile_grounded.append(f"【{p_name}】{ph.strip()}")
                    elif proj.get("description_zh") or proj.get("description"):
                        desc = str(proj.get("description_zh") or proj.get("description")).strip()
                        if any(char.isdigit() for char in desc) or len(desc) <= 100:
                            profile_grounded.append(f"【{p_name}】{desc}")

        # 2. Extract from competing offers
        if isinstance(competing_offers, list) and len(competing_offers) > 0:
            for c in competing_offers:
                if not isinstance(c, dict):
                    continue
                c_comp = c.get("company", "同业企业")
                c_pkg = c.get("package_annual")
                c_base = c.get("base_monthly")
                details = []
                if c_pkg:
                    details.append(f"年包总额约 {int(c_pkg):,} 元" if isinstance(c_pkg, (int, float)) else f"年包约 {c_pkg}")
                if c_base:
                    details.append(f"固定月薪达 {int(c_base):,} 元" if isinstance(c_base, (int, float)) else f"月薪约 {c_base}")
                det_str = f"（{'，'.join(details)}）" if details else ""
                competing_grounded.append(f"持有【{c_comp}】录用要约{det_str}")

        all_grounded = profile_grounded + competing_grounded

        # 3. Evidence Gate checks: identify unsupported claims & pending questions
        if not competing_grounded:
            unsupported_claims.append(
                "未提供经核验的外部竞争 Offer 数据，已自动拦截‘外部竞品要约’主张，降级为通用行业市场薪酬带宽叙事。"
            )
            pending_questions.append(
                "是否有其他在流程中或已拿到的外部 Offer？如有，可补充竞品公司名称、Base 月薪及年包总额，以增强薪酬博弈杠杆。"
            )

        if not profile_grounded:
            unsupported_claims.append(
                "画像中未提供经量化认证的业务或技术成效指标，已自动拦截未经画像证实的具体战功指标，降级为稳健通用专业价值叙事。"
            )
            pending_questions.append(
                "是否能补充过往经历中具体负责的核心业务指标或量化产出（如效率提升%、成本节省额、业务增长规模）？这将显著增强薪酬说服力。"
            )

        return profile_grounded, competing_grounded, all_grounded, unsupported_claims, pending_questions

    # ---------------------------------------------------------------------------
    # Tactical Counter-Offer Generator
    # ---------------------------------------------------------------------------

    def generate_counter_offer(
        self,
        evaluation_result: Dict[str, Any],
        target_base: Optional[float] = None,
        competing_offers: Optional[List[Dict[str, Any]]] = None,
        candidate_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generates professional, high-EQ counter-offer letters and verbal negotiation scripts.
        Anchors claims strictly in candidate_profile and competing_offers via Evidence Gate.
        """
        company = str(evaluation_result.get("company", "目标企业"))
        comp = evaluation_result.get("total_compensation", {})
        current_base = float(comp.get("monthly_base", 0.0))
        current_package = float(comp.get("total_annual_package", 0.0))
        detected_traps = evaluation_result.get("detected_traps", [])

        # Fallback profile from evaluation_result if not explicitly provided
        if candidate_profile is None:
            candidate_profile = evaluation_result.get("candidate_profile")

        # Resolve role dynamically
        cand_title = ""
        if isinstance(candidate_profile, dict):
            cand_info = candidate_profile.get("candidate", {})
            if isinstance(cand_info, dict):
                cand_title = cand_info.get("title_zh") or cand_info.get("title") or cand_info.get("role") or ""
        role = evaluation_result.get("role")
        if not role or role in ("大模型算法架构师", "核心岗位", "目标岗位"):
            role = cand_title or role or "核心岗位"
        role = str(role)

        # Establish Target Base
        if target_base is None or target_base <= 0:
            target_base = round(current_base * 1.15, 0)

        base_increment = int(target_base - current_base)
        base_increment_pct = round((base_increment / current_base) * 100, 1) if current_base > 0 else 15.0

        # Execute Evidence Gate
        profile_grounded, competing_grounded, all_grounded, unsupported_claims, pending_questions = (
            self._extract_evidence_and_gate(candidate_profile, competing_offers, role=role)
        )

        # Formulate competing offer narrative
        has_competing = bool(competing_offers and len(competing_offers) > 0)
        if has_competing:
            c = competing_offers[0]
            c_company = c.get("company", "外部同业企业")
            c_pkg = c.get("package_annual", "具有极高竞争力的薪酬总包")
            c_base = c.get("base_monthly")
            c_base_str = f"（固定月薪达 {int(c_base):,} 元）" if c_base else ""
            pkg_str = f"{int(c_pkg):,} 元" if isinstance(c_pkg, (int, float)) else str(c_pkg)
            competing_str = (
                f"目前我也收到了来自 {c_company} 等团队的录用要约，其提供的综合总包达到 {pkg_str}{c_base_str}，"
                f"且在固定现金比例与合同条款上给予了极大的诚意。"
            )
            competing_str_en = (
                f"I currently hold a competing offer from {c_company} with an annualized package of {pkg_str} RMB, "
                f"which offers a highly competitive base salary and favorable contractual terms."
            )
        else:
            competing_str = (
                f"综合考量当前市场上同类【{role}】岗位的外部市场分位与行业薪酬带宽，"
                f"结合我过往在业务落地中所展现的专业交付能力与直接产出，"
            )
            competing_str_en = (
                f"Considering current market benchmarks and compensation percentiles for the {role} position, "
                f"alongside my verified track record of domain execution and impact,"
            )

        # Build grounded tech/business achievement narrative
        if profile_grounded:
            cleaned_claims = []
            for claim in profile_grounded[:2]:
                c_clean = re.sub(r"^[【\[].*?[】\]]\s*", "", claim).strip().rstrip("。；; ")
                if len(c_clean) > 80:
                    c_clean = c_clean[:80] + "..."
                cleaned_claims.append(c_clean)
            evidence_narrative_zh = f"凭借在【{'；'.join(cleaned_claims)}】等方面的实战经验与扎实交付成果"
            evidence_narrative_en = "my hands-on track record and verified delivery across core domain deliverables"
        else:
            evidence_narrative_zh = "凭借扎实的专业技能、系统的业务认知与过往项目中积累的稳定交付能力"
            evidence_narrative_en = "my professional expertise, execution capability, and proven commitment to rigorous delivery"

        # Tactical Clause Remedy Requests
        trap_remedy_requests = []
        for trap in detected_traps:
            trap_remedy_requests.append(f"【{trap['name']}】：{trap['negotiation_countermeasure']}")

        if detected_traps:
            pending_questions.append(
                f"针对录用函中检测到的 {len(detected_traps)} 项潜在合同条款合规疑点（如：{detected_traps[0]['name']}），"
                "建议向 HR 索取正式劳动合同与竞业协议附录原文，并在签字前咨询专业劳动法执业律师或人事合规顾问。"
            )

        # 1. Chinese Written Counter-Offer Letter
        counter_offer_letter = f"""尊敬的 {company} 招聘团队与业务主管：

您好！非常感谢贵司对我的认可并发送【{role}】的录用通知（Offer Letter）。在过去的沟通交流中，我与团队业务主管就【{role}】岗位的业务规划与核心目标进行了深入探讨，团队务实专业的协作氛围与清晰的业务愿景深深吸引了我，我也非常期待能加入团队共同创造业务价值。

在仔细审阅 Offer 薪酬构成与合同细则后，出于对这份长期合作的珍视，我希望就部分薪酬构成与合同条款与您进行诚恳的探讨与对齐：

1. 关于固定月薪与现金确定性：
目前 Offer 约定的月度基本薪酬为 {int(current_base):,} 元/月。{competing_str}
为了能够完全解除后顾之忧、全身心投入到团队下季度的核心里程碑攻坚中，我真诚期望能将固定月薪调整至 {int(target_base):,} 元/月（增幅约 {base_increment_pct}%）；或者在月薪保持现状的基础上，通过设置首年签约入职奖金（Sign-on Bonus）约 {int(base_increment * 12):,} 元以弥补现金落差。

2. 关于劳动合同合规与保护性条款优化：
在录用函条款中，我注意到有以下几项涉及行业常规条款的细节，期望能同步给予沟通优化：
"""
        for idx, t in enumerate(detected_traps, 1):
            counter_offer_letter += f"  ({idx}) {t['name']}：建议按照国家劳动法规及行业通行合规惯例，优化为更具确定性的标准表述；\n"

        if detected_traps:
            counter_offer_letter += "\n（注：以上条款建议基于常见劳动人事合规实践，旨在促进双方达成规范、共赢的长期合作协议。）\n"

        counter_offer_letter += f"""
我始终将 {company} 视为我的第一职业选择。我相信{evidence_narrative_zh}，入职后能在前90天内为团队带来扎实的业务回报与价值增益。

非常期待与您进一步沟通，争取早日达成双赢并完成签约！

祝好，
候选人敬上
"""

        # 2. English Written Counter-Offer Letter
        counter_offer_letter_en = f"""Dear {company} Hiring Team,

Thank you very much for extending the offer for the {role} position. I truly enjoyed my conversations with the leadership regarding the strategic roadmap and core objectives for the team. I am genuinely excited about the team's mission and future.

After reviewing the offer details and compensation package, I would love to discuss a few specific points to align our expectations for a long-term partnership:

1. Base Salary & Cash Certainty:
The current offer outlines a base of {int(current_base):,} RMB/month. {competing_str_en}
To comfortably make this commitment, I would be grateful if we could adjust the monthly base to {int(target_base):,} RMB/month (approx. +{base_increment_pct}%), or alternatively bridge this delta through a first-year Sign-on Bonus of {int(base_increment * 12):,} RMB.

2. Contractual Terms Alignment:
I also noticed a few contractual clauses regarding probation terms, non-compete scope, and equity terms that diverge from standard industry compliance benchmarks. I look forward to working together to ensure these reflect mutually protective terms.

{company} remains my top choice, and I am confident that {evidence_narrative_en} will allow me to deliver immediate, measurable ROI to the organization.

Thank you for your understanding and advocacy. I look forward to finalizing our agreement.

Warm regards,
Candidate
"""

        # 3. High-EQ Verbal Negotiation Script (5 phases)
        if profile_grounded:
            cleaned_verbal = []
            for claim in profile_grounded[:2]:
                c_clean = re.sub(r"^[【\[].*?[】\]]\s*", "", claim).strip().rstrip("。；; ")
                if len(c_clean) > 50:
                    c_clean = c_clean[:50] + "..."
                cleaned_verbal.append(c_clean)
            verbal_impact = f"。结合我过往在【{'、'.join(cleaned_verbal)}】等方面的真实落地经验，我入职后能迅速在核心业务中产生闭环价值。"
        else:
            verbal_impact = f"。结合我在该岗位上扎实的专业积累与稳定交付履约记录，我入职后能迅速在核心业务中产生闭环价值。"

        if has_competing:
            c_comp_name = competing_offers[0].get("company", "外部同业企业")
            verbal_leverage = f"，包括【{c_comp_name}】在内的团队也开出了非常诚意的条件"
        else:
            verbal_leverage = f"，外部对【{role}】的核心市场对标反馈与薪酬带宽普遍处于高位"

        verbal_script = {
            "opening_and_anchor": (
                f"“您好！非常感谢团队这么快把录用函发过来。之前和业务主管深入沟通后，我对咱们团队在【{role}】方向的业务前景与务实规划非常认可，"
                f"咱们团队绝对是我的第一优先级选择！”"
            ),
            "leverage_presentation": (
                f"“在仔细评估整体薪酬包后，我必须坦诚地向您汇报：目前猎头和同行给我的市场对标反馈非常热烈"
                f"{verbal_leverage}"
                f"{verbal_impact}”"
            ),
            "the_ask_compensation": (
                f"“为了能让我毫无顾虑、100% 聚焦在核心工作与业务攻坚上，我想向您争取把月度 Base 调整到 {int(target_base):,} 元/月（差距为 {int(base_increment):,} 元）。"
                f"如果部门本财年的月度现金预算确有刚性职级上限，咱们是否能够通过一笔首年签约奖金 (Sign-on Bonus) 约 {int(base_increment * 12):,} 元来把这个落差补齐？这样既不破坏团队职级体系，又能解决我的现实顾虑。”"
            ),
            "trap_rectification_points": (
                "“另外在录用协议条款上，有几个合规常规细节咱们顺手理顺一下："
                + "、".join([f"比如【{t['name']}】建议按国家法规和行业合规惯例做规范化表述" for t in detected_traps[:3]])
                + "。我相信这对咱们双方长期规范合作也是一件很顺理成章的事。”"
            ),
            "closing_and_commitment": (
                "“只要这两个核心点我们能达成共识，我今天就可以正式口头接受 Offer，立刻启动上一家的离职交接流程，"
                "全力以赴准备入职！您看咱们能不能一起向 HRVP / 薪酬委员会做一次沟通申请？非常感谢您的支持与争取！”"
            ),
        }

        # 4. Tactical Leverage Points
        if profile_grounded:
            p_sample = re.sub(r"^[【\[].*?[】\]]\s*", "", profile_grounded[0]).strip().rstrip("。；; ")
            if len(p_sample) > 40:
                p_sample = p_sample[:40] + "..."
            point_1 = f"【确定性业务战功对冲】：基于画像中已验证的客观成果（如：{p_sample}），向用人单位证明薪酬溢价具备明确的业务回报支撑。"
        else:
            point_1 = "【专业能力与交付价值对冲】：以扎实的专业方法论与既往稳定的交付履约记录为依托，强调入职后能够快速接手核心工作，降低用人单位的试错与磨合成本。"

        if has_competing:
            c_comp_name = competing_offers[0].get("company", "外部同业企业")
            point_2 = f"【外部竞品要约锚点】：以【{c_comp_name}】真实录用要约作为客观市场杠杆，展示自身在行业薪酬带宽中的竞争力和稀缺性。"
        else:
            point_2 = f"【行业市场带宽对标】：以【{role}】在同业一线的市场薪酬分位为参考基准，客观阐述当前薪酬与市场合理水平的对齐空间。"

        point_3 = "【灵活性替代方案 (Sign-on)】：在月度 Base 遇到定级职级天花板时，主动提出以‘首年 Sign-on Bonus’形式弥补，既给 HR 台阶下，又确保现金利益落实。"
        point_4 = "【合规性条款有理有节】：对合同条款疑点的探讨援引具体劳动法规与合规实践，站在‘保护双方长期规范合作’的高度提出优化建议，附带合规提示并避免激化矛盾。"

        tactical_leverage_points = [point_1, point_2, point_3, point_4]

        return {
            "target_base": target_base,
            "base_increment": base_increment,
            "base_increment_pct": base_increment_pct,
            "counter_offer_letter": counter_offer_letter,
            "counter_offer_letter_en": counter_offer_letter_en,
            "chinese_letter": counter_offer_letter,
            "english_letter": counter_offer_letter_en,
            "verbal_negotiation_script": verbal_script,
            "verbal_script": verbal_script,
            "detected_traps": detected_traps,
            "trap_remedy_requests": trap_remedy_requests,
            "tactical_leverage_points": tactical_leverage_points,
            "negotiation_strategy_summary": (
                f"目标锁定固定月薪 {int(target_base):,} 元（或增设 {int(base_increment * 12):,} 元 Sign-on Bonus）；"
                f"同步推进 {len(detected_traps)} 项合同条款的合规沟通。采取‘极高意愿+战功/价值锚定+双赢提议’的策略，预计可达成预期目标。"
            ),
            "grounded_claims": all_grounded,
            "unsupported_claims": unsupported_claims,
            "pending_questions": pending_questions,
            "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        }

    def generate_counter_offer_letter(
        self,
        evaluation_result: Dict[str, Any],
        target_base: Optional[float] = None,
        competing_offers: Optional[List[Dict[str, Any]]] = None,
        candidate_profile: Optional[Dict[str, Any]] = None,
        lang: str = "zh",
    ) -> str:
        """
        Directly generates the counter-offer letter in Chinese ('zh') or English ('en').
        """
        res = self.generate_counter_offer(
            evaluation_result=evaluation_result,
            target_base=target_base,
            competing_offers=competing_offers,
            candidate_profile=candidate_profile,
        )
        return res["counter_offer_letter"] if lang.lower() == "zh" else res["counter_offer_letter_en"]

    # ---------------------------------------------------------------------------
    # Narrative Generator
    # ---------------------------------------------------------------------------

    def _generate_evaluation_narrative(
        self,
        company: str,
        role: str,
        total_compensation: Dict[str, Any],
        detected_traps: List[Dict[str, Any]],
        risk_level: str,
        overall_score: float,
    ) -> str:
        """Generates comprehensive executive valuation narrative with compliance disclaimers."""
        annual_cash = total_compensation["total_annual_cash"]
        total_pkg = total_compensation["total_annual_package"]
        cash_ratio_pct = round(total_compensation["cash_ratio"] * 100, 1)

        lines = [
            f"【Offer 综合估值报告】针对 {company} 的【{role}】录用要约评估完成：",
            f"• 首年综合总包价值 (Total Package)：约 {int(total_pkg):,} 元人民币；",
            f"• 确定性首年年度现金 (Annual Cash)：约 {int(annual_cash):,} 元人民币（现金占比 {cash_ratio_pct}%）；",
            f"• 合同综合健康得分：{overall_score} / 100（风险评级：【{risk_level}】）。",
            "",
        ]

        if detected_traps:
            lines.append(f"【⚠️ 重点合同条款合规提示】共检测出 {len(detected_traps)} 项潜在合规或履约风险疑点：")
            for idx, trap in enumerate(detected_traps, 1):
                lines.append(f"  [{idx}] 【{trap['name']}】(关注等级: {trap['severity']})")
                lines.append(f"      • 关注要点：{trap['issue_summary']}")
                lines.append(f"      • 沟通建议：{trap['negotiation_countermeasure']}")
            lines.append("")
            lines.append("【决策建议】：建议在正式签署前启动 Counter-Offer 沟通，就上述条款与用人单位友好对齐，并争取合理薪酬带宽。")
        else:
            lines.append("【合同合规性评价】：各项条款未见显著合规疑点，薪酬结构整体健康度良好，可按标准流程稳步推进签约。")

        lines.append("")
        lines.append(f"【合规免责声明】{COMPLIANCE_DISCLAIMER}")

        return "\n".join(lines)


def evaluate_offer_package(
    offer_data: Dict[str, Any],
    candidate_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Top-level convenience function for evaluating offer package.
    """
    negotiator = OfferNegotiator()
    return negotiator.evaluate_offer(offer_data, candidate_profile)

