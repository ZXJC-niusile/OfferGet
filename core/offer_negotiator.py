"""
OfferGet Offer Negotiator Engine (core.offer_negotiator)
========================================================
Total compensation package valuation, 6 contract trap/red flag detectors,
salary consistency auditing, and high-EQ tactical counter-offer generation.
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


class OfferNegotiator:
    """
    Offer Evaluation and Counter-Offer Negotiation Engine.
    
    Capabilities:
    1. Total Compensation Breakdown:
       Base, Target Bonus, Sign-on, Stock/RSU, Housing Fund, Estimated annual cash.
    2. 6 Contract Trap / Red Flag Detectors:
       - Trap 1: Probation salary discount < 80% or probation duration > 6 months.
       - Trap 2: Non-compete clause without statutory monthly compensation or scope too broad.
       - Trap 3: Base salary split with excessive floating performance ratio (>30% floating).
       - Trap 4: Unrealistic equity/RSU vesting cliff or unexercisable terms.
       - Trap 5: Unstated/uncompensated overtime expectations.
       - Trap 6: Discrepancy with stated expected salary from earlier rounds.
    3. Tactical Counter-Offer Generator:
       Generates professional, high-EQ counter-offer letters and verbal negotiation scripts.
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
        role = str(offer_data.get("role") or offer_data.get("job_title") or "大模型算法架构师")

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
            reasons.append(f"试用期约定为【{duration} 个月】，超过《劳动合同法》第十九条规定的上限（最长不超过6个月）")
            severity = "CRITICAL"
        elif duration > 3 and "三年" not in clause_text:
            # If 1-3 year contract, max probation is 2 months
            pass

        # Check discount < 80% (0.80)
        if discount_ratio < 0.80:
            detected = True
            reasons.append(f"试用期工资发放比例仅为正式工资的【{int(discount_ratio * 100)}%】，低于《劳动合同法》第二十条规定的法定期限底线（不得低于80%）")
            severity = "CRITICAL"

        # Check social insurance during probation
        if social_insurance is False or "试用期不缴纳社保" in clause_text:
            detected = True
            reasons.append("条款声明试用期内不缴纳社保公积金，属于严重违反《社会保险法》的违法条款")
            severity = "CRITICAL"

        # Check text heuristics
        if not detected and clause_text:
            if re.search(r"试用期.*(70%|七折|六折|60%|半薪)", clause_text):
                detected = True
                reasons.append("条款文本中包含低于 80% 的试用期薪资折损表述")
                severity = "CRITICAL"
            elif re.search(r"试用期.*([7-9]个月|1年|一年|半年以上)", clause_text):
                detected = True
                reasons.append("条款文本中包含超过 6 个月的试用期约定")
                severity = "CRITICAL"

        return {
            "trap_id": "TRAP_01_PROBATION",
            "name": "试用期薪资折扣与期限合规陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "试用期期限与薪资比例符合劳动法规标准。",
            "legal_basis": "《中华人民共和国劳动合同法》第十九条、第二十条明确规定：三年以上固定期限和无固定期限劳动合同，试用期不得超过六个月；劳动者在试用期的工资不得低于本单位相同岗位最低档工资或者劳动合同约定工资的百分之八十，并不得低于用人单位所在地的最低工资标准。",
            "negotiation_countermeasure": "向 HR 明确主张修正录用函条款：“要求试用期约定为法定允许的 3-6 个月之内，且试用期薪资必须按正式薪资 100% 全额发放（或严格按不低于 80% 法定比例支付），入职首日起足额缴纳五险一金”。",
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
            reasons.append(f"竞业限制期限约定为【{duration} 个月】，超过《劳动合同法》第二十四条规定的最长 2 年上限")
            severity = "CRITICAL"

        # Check compensation claimed to be included in monthly wage
        if applies and (included_in_salary or "包含在日常工资" in clause_text or "月薪已含竞业" in clause_text or "不再另行支付" in clause_text):
            detected = True
            reasons.append("约定‘竞业补偿金已包含在日常月薪中且离职后不另行支付’，根据最高人民法院司法解释，该条款涉嫌违法且剥夺劳动者法定补偿权")
            severity = "CRITICAL"
        elif applies and comp_ratio <= 0.0 and ("离职后支付" not in clause_text):
            detected = True
            reasons.append("竞业限制条款未明确约定离职后按月支付的法定经济补偿金标准（法定通常不低于离职前月均工资的 30%）")
            severity = "HIGH"

        # Check overly broad scope
        if applies and scope:
            if re.search(r"(所有|全行业|任何|全部).*?(互联网|人工智能|软件|科技|算法)", scope):
                detected = True
                reasons.append(f"竞业限制范围极其泛化（【{scope[:40]}...】），未限定于具备实际竞争关系的实体清单，严重限制职业自由")
                if severity != "CRITICAL":
                    severity = "HIGH"

        # Text search fallback
        if not detected and clause_text:
            if "竞业" in clause_text and ("全行业" in clause_text or "任何互联网" in clause_text or "不另行补偿" in clause_text):
                detected = True
                reasons.append("条款文本中包含无偿竞业或泛行业垄断性竞业约定")
                severity = "HIGH"

        return {
            "trap_id": "TRAP_02_NON_COMPETE",
            "name": "竞业限制无偿化与范围泛化陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "未设置显失公平的竞业限制条款或条款合规。",
            "legal_basis": "《中华人民共和国劳动合同法》第二十三条、第二十四条及《最高人民法院关于审理劳动争议案件适用法律问题的解释（一）》第三十六条：用人单位与劳动者约定竞业限制的，必须在解除或终止劳动合同后在竞业限制期限内按月给予经济补偿（法定标准通常不低于劳动合同解除前十二个月平均工资的30%）；在职期间‘工资已含竞业补偿’的格式约定依法无效；竞业期限最长不得超过二年。",
            "negotiation_countermeasure": "向 HR 明确提出条款修改诉求：“1. 删除‘工资已含离职竞业补偿’的不规范字样；2. 明确离职时由用人单位书面决定是否启动竞业，启动则按月支付不低于前12个月平均月薪30%-50%的补偿金；3. 竞业范围必须明确附录双方签字认可的 3-5 家精准核心直接竞品名单，不得使用‘所有人工智能与互联网公司’等泛化定义”。",
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
                f"月薪中浮动绩效比例高达【{int(floating_ratio * 100)}%】（固定基本工资仅占 {int(fixed_ratio * 100)}%），超过行业 30% 浮动安全红线"
            )
            severity = "CRITICAL" if floating_ratio >= 0.50 else "HIGH"

        # Check if base is artificially suppressed to local minimum wage
        fixed_amount = monthly_base * fixed_ratio
        if 0 < fixed_amount <= 3000 and monthly_base > 15000:
            detected = True
            reasons.append(f"固定基本工资被刻意压低至【{fixed_amount} 元】（接近法定最低工资），涉嫌规避经济补偿金与加班基数计算")
            severity = "CRITICAL"

        # Text search in salary notes
        notes = str(offer_data.get("salary_structure_notes") or offer_data.get("salary_notes") or "")
        if "浮动考核" in notes and "扣减" in notes:
            if not detected:
                detected = True
                reasons.append("薪资附注中包含单方主观考核扣减浮动绩效的单边条款")
                severity = "HIGH"

        return {
            "trap_id": "TRAP_03_SALARY_SPLIT",
            "name": "基本薪资拆分与高额浮动绩效陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "固定基本工资占比达标，现金流保障性良好。",
            "legal_basis": "《中华人民共和国劳动合同法》及各地工资支付规定：用人单位将约定月薪恶意拆分为微量基本工资加高额浮动绩效，旨在获得单方面无因扣减薪资的自由裁量权，并在员工离职、试用期被辞退或计算法定补偿金（N+1）时按超低基本工资推脱责任，具有极高的现金确定性风险。",
            "negotiation_countermeasure": "坚持谈判底线：“作为核心架构师，薪酬的确定性与现金流安全是信任基石。要求将固定月薪比例提升至 80% 以上（或 100% 固定现金），如确有浮动绩效，必须在录用函中提供清晰客观、可度量、非主观裁量的考核细则，并设立未达成时的保底发放机制”。",
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
            reasons.append(f"期权/RSU 设置了长达【{cliff_years} 年】的归属等待期 (Cliff)（标准行业惯例为 1 年），极大增加了兑现前被动出局的沉没成本")
            severity = "HIGH"

        # Check forced repurchase at par value (1分钱/0.01元/面值回购)
        if re.search(r"(面值|0\.01元|1分钱|原始出资额|成本价).*?(回购|收回|作废)", repurchase_clause):
            detected = True
            reasons.append(f"期权退出协议约定离职时公司可按【面值/成本价强制回购】已归属期权，剥夺员工资本增值权益，属于典型的‘纸面财富画饼’条款")
            severity = "CRITICAL"

        # Check IPO only
        if "仅在上市后" in repurchase_clause or "上市后方可行权" in repurchase_clause:
            detected = True
            reasons.append("期权条款约定‘仅在公司成功上市后方可行权’且未明确上市时间表与回购兜底，流动性风险极高")
            if severity != "CRITICAL":
                severity = "HIGH"

        # Check undisclosed total pool
        if total_pool_disclosed is False or "份额未定" in vesting_schedule:
            detected = True
            reasons.append("仅承诺期权股数而隐瞒公司总股本与估值基准，无法计算实际持股比例与真实纸面价值")
            if severity == "NONE":
                severity = "MEDIUM"

        return {
            "trap_id": "TRAP_04_EQUITY_CLIFF",
            "name": "期权超长等待期与掠夺性强制回购陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "期权/RSU 归属机制与退出条款处于合理行业范围。",
            "legal_basis": "《中华人民共和国公司法》及最高人民法院股权激励争议裁判规则：股权期权属于对核心员工长期贡献的劳动激励对价。若在协议中单方设定‘离职无条件按面值（如0.01元）强制回购已归属权益’，违反公平原则，已在多起知名司法判例中被认定为显失公平或无效格式条款。",
            "negotiation_countermeasure": "向公司期权委员会提出书面修正要求：“1. 调整为行业标准的 1 年 Cliff 归属机制（满 1 年归属 25%，后续按季度均匀归属）；2. 明确约定已归属期权在离职时由员工自主选择保留或按最新一轮融资公允市场估值（Fair Market Value）由公司回购，坚决删除按 0.01 元面值剥夺已归属期权的霸王条款”。",
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
                reasons.append("单方实行‘综合工时制/不定时工时制’，未提供人社行政审批许可批文，涉嫌规避法定加班费支付义务")
                severity = "HIGH"

        # Check uncompensated overtime clauses
        if overtime_pay in ("none", "included_in_base", "dinner_stipend_only") or re.search(
            r"(包揽所有加班|月薪已包揽|不设加班费|无加班工资|加班视为自愿|无偿加班|仅报销晚餐打车)",
            work_text
        ):
            detected = True
            reasons.append("合同条款明确注明‘月薪已包揽一切加班、不支付加班费或仅提供餐补打车报销’，涉嫌违法排除劳动者合法报酬权")
            severity = "HIGH"

        return {
            "trap_id": "TRAP_05_OVERTIME",
            "name": "工时制度瑕疵与无偿高压加班陷阱",
            "detected": detected,
            "severity": severity if detected else "NONE",
            "issue_summary": "；".join(reasons) if detected else "工时制与考勤加班规范符合国家法定标准。",
            "legal_basis": "《中华人民共和国劳动法》第三十六条、第四十四条及《关于企业实行不定时工作制和综合计算工时工作制的审批办法》规定：实行特殊工时制必须经人力资源社会保障行政部门审批备案；法定标准工作时间以外的延长工作时间，用人单位必须依法支付不低于法定倍数（150%、200%、300%）的加班报酬，任何通过格式条款免除用人单位加班费义务的约定均属违法无效。",
            "negotiation_countermeasure": "在沟通中探询日常发版与加班强度，口头对齐：“确认岗位属于标准工时制，对于项目攻坚期的突发性周末加班，明确以 1:1 调休形式予以平衡，并请 HR 协助从录用函中移除‘薪资包揽一切加班’的不合规表述”。",
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
                    f"Offer 固定月薪（{int(monthly_base)} 元）显著低于前期面试明确沟通的期望月薪（{int(expected_base)} 元），倒挂幅度达 {round(base_gap_pct * 100, 1)}%"
                )
                severity = "HIGH"
            elif base_gap_pct >= 0.08:
                detected = True
                reasons.append(
                    f"Offer 固定月薪较预期存在微幅落差（差距 {round(base_gap_pct * 100, 1)}%），具备合理的向上对齐空间"
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
            "legal_basis": "猎头与人力资源薪酬博弈规则：HR 在发 Offer 阶段往往存在定级压薪惯性，尝试测试候选人心理底线，将确定性的现金 Base 压低，转而用‘年终奖可能高达6-8个月’等不确定承诺画饼补差，需通过锚定战功与竞争性 Offer 坚定反推。",
            "negotiation_countermeasure": "以客观战功与前期预期为锚定点：“前期与业务主管沟通中，我的技术交付能力得到了高度认可。当前 Offer 的月度 Base 相比我的核心预期存在一定落差。为保障全心投入，期望能够拉齐至 XX 万/月；或在月薪不变的前提下，通过增加 YY 万元首年 Sign-on Bonus 予以平衡”。",
        }

    # ---------------------------------------------------------------------------
    # Tactical Counter-Offer Generator
    # ---------------------------------------------------------------------------

    def generate_counter_offer(
        self,
        evaluation_result: Dict[str, Any],
        target_base: Optional[float] = None,
        competing_offers: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generates professional, high-EQ counter-offer letters and verbal negotiation scripts.
        """
        company = evaluation_result.get("company", "贵司")
        role = evaluation_result.get("role", "大模型算法架构师")
        comp = evaluation_result.get("total_compensation", {})
        current_base = float(comp.get("monthly_base", 0.0))
        current_package = float(comp.get("total_annual_package", 0.0))
        detected_traps = evaluation_result.get("detected_traps", [])

        # Establish Target Base
        if target_base is None or target_base <= 0:
            target_base = round(current_base * 1.15, 0)

        base_increment = int(target_base - current_base)
        base_increment_pct = round((base_increment / current_base) * 100, 1) if current_base > 0 else 15.0

        # Formulate competing offer narrative
        competing_str = ""
        competing_str_en = ""
        has_competing = bool(competing_offers and len(competing_offers) > 0)
        if has_competing:
            c = competing_offers[0]
            c_company = c.get("company", "某头部人工智能实验室")
            c_pkg = c.get("package_annual", "具有极高竞争力的薪酬总包")
            c_base = c.get("base_monthly")
            c_base_str = f"（固定月薪达 {int(c_base)} 元）" if c_base else ""
            competing_str = f"目前我也收到了来自 {c_company} 等团队的录用要约，其提供的综合总包达到 {c_pkg} 元{c_base_str}，且在固定现金比例与合同条款上给予了极大的诚意。"
            competing_str_en = f"I currently hold a competing offer from {c_company} with an annualized package of {c_pkg} RMB, which offers a highly competitive base salary and favorable contractual terms."
        else:
            competing_str = "综合考量当前行业一线大模型架构师的外部市场分位（如 Levels.fyi 及头部独角兽薪酬带宽），以及我能够直接带来的万卡集群故障治理与推理降本战功，"
            competing_str_en = "Considering benchmark market compensation for Senior Staff LLM Architects and the immediate technical impact I will deliver in cluster stabilization and inference cost reduction,"

        # Tactical Clause Remedy Requests
        trap_remedy_requests = []
        for trap in detected_traps:
            trap_remedy_requests.append(f"【{trap['name']}】：{trap['negotiation_countermeasure']}")

        # 1. Chinese Written Counter-Offer Letter
        counter_offer_letter = f"""尊敬的 {company} 招聘团队与业务主管：

您好！非常感谢贵司对我的认可并发送【{role}】的录用通知（Offer Letter）。在过去的数轮技术沟通中，我与团队业务主管深入探讨了基座模型预训练、分布式通信治理与智能体系统的战略规划，团队务实的极客氛围与宏大的业务愿景深深吸引了我，我也非常渴望能加入团队共同攻坚核心算法壁垒。

在仔细审阅 Offer 薪酬构成与合同细则后，出于对这份长期合作的珍视，我希望就部分薪酬构成与合同条款与您进行诚恳的探讨与对齐：

1. 关于固定月薪与现金确定性：
目前 Offer 约定的月度基本薪酬为 {int(current_base):,} 元/月。{competing_str}
为了能够完全解除后顾之忧、全身心投入到团队下季度的核心里程碑攻坚中，我真诚期望能将固定月薪调整至 {int(target_base):,} 元/月（增幅约 {base_increment_pct}%）；或者在月薪保持现状的基础上，通过设置首年签约入职奖金（Sign-on Bonus）约 {int(base_increment * 12):,} 元以弥补现金落差。

2. 关于劳动合同合规与保护性条款修正：
在录用函条款中，我注意到有以下几项涉及行业常规条款的细节，期望能同步给予修正完善：
"""
        for idx, t in enumerate(detected_traps, 1):
            counter_offer_letter += f"  ({idx}) {t['name']}：建议按照国家劳动法规及行业通行惯例，优化为更具确定性的标准表述；\n"

        counter_offer_letter += f"""
我始终将 {company} 视为我的第一职业选择。我相信凭借在千卡集群大规模训练通信治理（日均宕机压至8分钟）、GRPO纯强化学习对齐及高并发推理降本（年省3800万算力）方面的实战经验，入职后能在前90天内为团队带来远超薪酬溢价的直接技术与商业回报。

非常期待与您进一步沟通，争取早日达成双赢并完成签约！

祝好，
候选人敬上
"""

        # 2. English Written Counter-Offer Letter
        counter_offer_letter_en = f"""Dear {company} Hiring Team,

Thank you very much for extending the offer for the {role} position. I truly enjoyed my conversations with the engineering leadership regarding foundation model scaling, distributed systems reliability, and agentic infrastructure. I am genuinely excited about the team's mission.

After reviewing the offer details and compensation package, I would love to discuss a few specific points to align our expectations for a long-term partnership:

1. Base Salary & Cash Certainty:
The current offer outlines a base of {int(current_base):,} RMB/month. {competing_str_en}
To comfortably make this commitment, I would be grateful if we could adjust the monthly base to {int(target_base):,} RMB/month (approx. +{base_increment_pct}%), or alternatively bridge this delta through a first-year Sign-on Bonus of {int(base_increment * 12):,} RMB.

2. Contractual Terms Alignment:
I also noticed a few contractual clauses regarding probation terms, non-compete scope, and equity vesting that diverge from standard industry benchmarks. I look forward to working together to ensure these reflect mutually protective terms.

{company} remains my top choice, and I am confident that my hands-on expertise in NCCL communication optimization and vLLM FP8 serving will deliver immediate, outsized ROI to the lab.

Thank you for your understanding and advocacy. I look forward to finalizing our agreement.

Warm regards,
Candidate
"""

        # 3. High-EQ Verbal Negotiation Script (Broken into 5 phases)
        verbal_script = {
            "opening_and_anchor": (
                f"“李老师/王经理您好！非常感谢团队这么快把录用函发过来。之前和业务一号位深聊后，我对咱们团队攻坚 AGI 的技术底气和业务前景非常兴奋，"
                f"我也非常认可团队的方向，咱们团队绝对是我的第一优先级选择！”"
            ),
            "leverage_presentation": (
                f"“在仔细评估整体薪酬包后，我必须坦诚地向您汇报：目前猎头和同行给我的市场对标反馈非常热烈"
                + (f"，包括 {competing_offers[0].get('company', '另一家头部实验室')} 在内的团队也开出了非常诚意的条件" if has_competing else "，外部对资深大模型架构师的薪资带宽普遍处于高位")
                + f"。结合我过去主导千卡集群治理将日均中断缩短到8分钟、自研推理引擎年省千万算力的现成战功，我入职第一天就能直接为咱们核心业务产生闭环价值。”"
            ),
            "the_ask_compensation": (
                f"“为了能让我毫无顾虑、100% 聚焦在核心代码和技术攻坚上，我想向您争取把月度 Base 调整到 {int(target_base):,} 元/月（差距仅为 {int(base_increment):,} 元）。"
                f"如果部门本财年的月度现金预算确有刚性职级上限，咱们是否能够通过一笔首年签约奖金 (Sign-on Bonus) 约 {int(base_increment * 12):,} 元来把这个落差补齐？这样既不破坏团队职级体系，又能解决我的现实顾虑。”"
            ),
            "trap_rectification_points": (
                "“另外在合同条款上，有几个法务常规细节咱们顺手理顺一下："
                + "、".join([f"比如【{t['name']}】希望按国家法规和行业惯例做规范化表述" for t in detected_traps[:3]])
                + "。我相信这对咱们大厂规范管理也是一件很顺理成章的事。”"
            ),
            "closing_and_commitment": (
                "“只要这两个核心点我们能达成共识，我今天就可以正式口头接受 Offer，立刻启动上一家的离职交接流程，"
                "全力以赴准备入职！您看咱们能不能一起向 HRVP / 薪酬委员会做一次特批申请？非常感谢您的支持与争取！”"
            ),
        }

        # 4. Tactical Leverage Points
        tactical_leverage_points = [
            "【确定性商业战功对冲】：用‘年均节省3800万元真实云算力’和‘千卡集群日均中断从2.4h压至8min’的量化指标，证明薪酬溢价在业务第一季度即可完全收回。",
            "【外部竞品溢价锚点】：以头部 AI 实验室或同级大厂的竞争性录用要约作为客观杠杆，证明自身处于行业薪酬带宽的 Upper Band。",
            "【灵活性替代方案 (Sign-on)】：在月度 Base 遇到定级职级天花板时，主动提出以‘首年 Sign-on Bonus’形式弥补，既给 HR 台阶下，又确保税后现金落袋。",
            "【合规性条款有理有节】：对合同陷阱的质疑必须援引具体国家劳动法规，站在‘保护双方长期合规’的高度提出修正，不激化个人矛盾。",
        ]

        return {
            "target_base": target_base,
            "base_increment": base_increment,
            "base_increment_pct": base_increment_pct,
            "counter_offer_letter": counter_offer_letter,
            "counter_offer_letter_en": counter_offer_letter_en,
            "verbal_negotiation_script": verbal_script,
            "trap_remedy_requests": trap_remedy_requests,
            "tactical_leverage_points": tactical_leverage_points,
            "negotiation_strategy_summary": (
                f"目标锁定固定月薪 {int(target_base):,} 元（或增设 {int(base_increment * 12):,} 元 Sign-on Bonus）；"
                f"同步推进 {len(detected_traps)} 项合同陷阱条款的法务修正。采取‘极高意愿+战功锚定+双赢提议’的策略，预计可达成预期目标。"
            ),
        }

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
        """Generates comprehensive executive valuation narrative."""
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
            lines.append(f"【⚠️ 重点合同陷阱警报】共检测出 {len(detected_traps)} 项法律合规或利益陷阱：")
            for idx, trap in enumerate(detected_traps, 1):
                lines.append(f"  [{idx}] 【{trap['name']}】(严重度: {trap['severity']})")
                lines.append(f"      • 问题隐患：{trap['issue_summary']}")
                lines.append(f"      • 谈判对策：{trap['negotiation_countermeasure']}")
            lines.append("")
            lines.append("【决策建议】：不可盲目直接签字！建议立即启动 Counter-Offer 战术谈判，修正霸王条款并争取薪酬上浮。")
        else:
            lines.append("【合同合规性评价】：各项条款未见显著法律漏洞与利益陷阱，薪酬结构整体健康度良好，可按标准流程稳步推进签约。")

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
