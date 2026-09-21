"""
OfferGet Multi-Offer Comparison Matrix & Valuation Engine (core/offer_comparator.py)
====================================================================================
Ported and evolved from offerPilot (offer_comparison, compensation)
and ResumeSkills (offer-comparison-analyzer).

Provides multi-offer quantitative comparison:
1. Complete compensation breakdown: Cash, Bonus, Equity/RSU, Housing Fund.
2. Effective Hourly Rate (真实折算时薪): Total Real Compensation / Annual Work Hours.
3. 6-Dimension Scoring:
   - 纯现金流收益 (Immediate Cash Flow)
   - 综合总包价值 (Total Annual Package)
   - 真实时薪性价比 (WLB & Hourly Rate)
   - 公积金与福利保障 (Benefits & Housing Fund)
   - 业务跑道与行业红利 (Business Runway & Market Tailwind)
   - 平台背书与成长空间 (Platform Reputation & Career Growth)
4. Go/No-Go Decision Matrix & Markdown Summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class OfferEntity:
    """Represents a concrete job offer package with compensation and work environment parameters."""

    company_name: str
    role_title: str
    city: str = "北京"
    base_monthly_salary: float = 25000.0
    salary_months: float = 14.0  # e.g., 14薪, 16薪
    annual_bonus_expected: float = 0.0
    sign_on_bonus: float = 0.0
    equity_rsu_annual: float = 0.0
    housing_fund_rate: float = 0.12  # e.g., 12%, 8%, 5%
    housing_fund_base_capped: bool = True
    city_housing_fund_cap_base: float = 33891.0  # Reference cap for Tier-1 cities
    weekly_work_hours: float = 45.0  # 965=40h, 995=50h, 996=60h
    daily_commute_hours: float = 1.5
    monthly_rent_or_commute_cost: float = 3500.0
    career_growth_score: float = 8.0  # 1-10
    stability_score: float = 8.0      # 1-10
    notes: str = ""


@dataclass
class CalculatedOfferMetrics:
    """Computed metrics, effective hourly rate, and multidimensional scores for an offer."""

    annual_cash_base: float
    annual_total_cash: float
    annual_total_package: float
    annual_housing_fund_total: float  # Both employer and employee contributions
    annual_work_hours: float
    effective_hourly_rate: float
    composite_score: float
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)


@dataclass
class OfferComparisonReport:
    """Synthesized comparison report across multiple offers."""

    offers: List[Tuple[OfferEntity, CalculatedOfferMetrics]]
    ranked_companies: List[str]
    best_overall: str
    best_hourly_rate: str
    best_cash_flow: str
    recommendation_summary: str
    comparison_table_md: str

    @property
    def evaluations(self) -> List[Tuple[OfferEntity, CalculatedOfferMetrics]]:
        return self.offers

    @property
    def winner_offer_id(self) -> str:
        return self.best_overall


class OfferComparator:
    """Evaluates and compares 2-5 job offers quantitatively."""

    WEEKS_PER_YEAR: float = 50.0

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "effective_hourly_rate": 0.25,
        "immediate_cash": 0.25,
        "total_package": 0.15,
        "benefits_housing_fund": 0.15,
        "career_growth": 0.10,
        "stability_risk": 0.10,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = dict(self.DEFAULT_WEIGHTS)
        if weights:
            self.weights.update(weights)

    def evaluate_single_offer(self, offer: OfferEntity) -> CalculatedOfferMetrics:
        """Calculates precise financial compensation, work hours, and effective hourly rate."""
        # 1. Base cash
        cash_base = offer.base_monthly_salary * offer.salary_months
        total_cash = cash_base + offer.annual_bonus_expected + offer.sign_on_bonus
        total_pkg = total_cash + offer.equity_rsu_annual

        # 2. Housing fund calculation (公积金个人+公司双边计入实际收益)
        fund_base = offer.base_monthly_salary
        if offer.housing_fund_base_capped:
            fund_base = min(fund_base, offer.city_housing_fund_cap_base)
        # Double side contribution = 2 * rate * base * 12
        annual_fund = fund_base * offer.housing_fund_rate * 2.0 * 12.0

        # 3. Work hours calculation (包含通勤隐性成本折算)
        annual_work_hours = offer.weekly_work_hours * self.WEEKS_PER_YEAR
        annual_commute_hours = offer.daily_commute_hours * 5.0 * self.WEEKS_PER_YEAR
        total_committed_hours = max(annual_work_hours + annual_commute_hours * 0.5, 1000.0)

        # 4. Net real compensation (总现金 + 公积金 - 租房/通勤溢价)
        annual_living_premium = offer.monthly_rent_or_commute_cost * 12.0
        net_annual_val = total_cash + annual_fund - annual_living_premium
        effective_hourly = round(net_annual_val / total_committed_hours, 1)

        # 5. 6-Dimension scores (1-100 scale)
        d_cash = min(100.0, max(20.0, total_cash / 5000.0))
        d_pkg = min(100.0, max(20.0, total_pkg / 6000.0))
        d_hourly = min(100.0, max(20.0, effective_hourly * 0.5))
        d_benefit = min(100.0, max(20.0, (annual_fund / 80000.0) * 100.0))
        d_growth = min(100.0, offer.career_growth_score * 10.0)
        d_stability = min(100.0, offer.stability_score * 10.0)

        dim_scores = {
            "immediate_cash": d_cash,
            "total_package": d_pkg,
            "effective_hourly_rate": d_hourly,
            "benefits_housing_fund": d_benefit,
            "career_growth": d_growth,
            "stability_risk": d_stability,
        }

        # Weighted composite score
        composite = round(
            sum(dim_scores[k] * self.weights.get(k, 0.0) for k in dim_scores),
            1,
        )

        pros: List[str] = []
        cons: List[str] = []

        if effective_hourly >= 160.0:
            pros.append(f"真实折算时薪高（{effective_hourly} 元/h），单位时间产出效益优异")
        elif effective_hourly < 100.0:
            cons.append(f"折算时薪偏低（仅 {effective_hourly} 元/h），高工时或高租房成本稀释了薪资")

        if total_cash >= 400000.0:
            pros.append(f"现金流充沛（年度现金 {round(total_cash/10000.0, 1)} 万），抗风险能力强")

        if offer.housing_fund_rate >= 0.12:
            pros.append(f"公积金顶格缴纳（{int(offer.housing_fund_rate*100)}%），每年免税沉淀 {round(annual_fund/10000.0, 1)} 万")
        elif offer.housing_fund_rate <= 0.05:
            cons.append(f"公积金按最低比例（{int(offer.housing_fund_rate*100)}%）缴纳，福利保障较薄弱")

        if offer.weekly_work_hours >= 55.0:
            cons.append(f"预估周工时达 {offer.weekly_work_hours} 小时（高强度加班），生活平衡度低")
        elif offer.weekly_work_hours <= 42.0:
            pros.append(f"工作时间规范（周工时约 {offer.weekly_work_hours} 小时），具备充足个人成长时间")

        return CalculatedOfferMetrics(
            annual_cash_base=round(cash_base, 2),
            annual_total_cash=round(total_cash, 2),
            annual_total_package=round(total_pkg, 2),
            annual_housing_fund_total=round(annual_fund, 2),
            annual_work_hours=round(annual_work_hours, 1),
            effective_hourly_rate=effective_hourly,
            composite_score=composite,
            dimension_scores=dim_scores,
            pros=pros,
            cons=cons,
        )

    def compare(self, offers: List[OfferEntity]) -> OfferComparisonReport:
        """Compares multiple offers and generates rank order, best picks, and markdown table."""
        if not offers:
            raise ValueError("至少需要提供一个 Offer 进行评估与对比。")

        evaluated: List[Tuple[OfferEntity, CalculatedOfferMetrics]] = []
        for o in offers:
            m = self.evaluate_single_offer(o)
            evaluated.append((o, m))

        # Sort by composite score descending
        ranked = sorted(evaluated, key=lambda x: x[1].composite_score, reverse=True)
        ranked_names = [item[0].company_name for item in ranked]

        best_overall = ranked[0][0].company_name
        best_hourly = max(evaluated, key=lambda x: x[1].effective_hourly_rate)[0].company_name
        best_cash = max(evaluated, key=lambda x: x[1].annual_total_cash)[0].company_name

        # Markdown comparison table
        table_lines = [
            "| 公司与岗位 | 现金年包 (万) | 公积金 (万/年) | 预估周工时 | 真实时薪 (元/h) | 综合评分 | 核心优势与风险 |",
            "|:---|:---:|:---:|:---:|:---:|:---:|:---|",
        ]
        for o, m in ranked:
            cash_wan = round(m.annual_total_cash / 10000.0, 1)
            fund_wan = round(m.annual_housing_fund_total / 10000.0, 1)
            summary_pro = m.pros[0] if m.pros else "待遇均衡"
            summary_con = f"；劣势: {m.cons[0]}" if m.cons else ""
            table_lines.append(
                f"| **{o.company_name}**<br>_{o.role_title}_ | {cash_wan}万 | {fund_wan}万 | {o.weekly_work_hours}h | **{m.effective_hourly_rate}** | **{m.composite_score}** | {summary_pro}{summary_con} |"
            )

        md_table = "\n".join(table_lines)

        summary = (
            f"在参与比对的 {len(offers)} 个 Offer 中，**{best_overall}** 综合加权评分最高（{ranked[0][1].composite_score} 分）。"
            + (f" 若追求单位时间性价比（最高真实时薪），推荐考虑 **{best_hourly}**（{max(e[1].effective_hourly_rate for e in evaluated)} 元/h）。" if best_hourly != best_overall else "")
            + (f" 若当前阶段极度看重即时现金流到账，最高现金包为 **{best_cash}**。" if best_cash != best_overall else "")
        )

        return OfferComparisonReport(
            offers=evaluated,
            ranked_companies=ranked_names,
            best_overall=best_overall,
            best_hourly_rate=best_hourly,
            best_cash_flow=best_cash,
            recommendation_summary=summary,
            comparison_table_md=md_table,
        )

    @classmethod
    def compare_offers(
        cls,
        offers: List[Any],
        weights: Optional[Dict[str, float]] = None,
    ) -> OfferComparisonReport:
        comparator = cls(weights=weights)
        parsed: List[OfferEntity] = []
        for o in offers:
            if isinstance(o, OfferEntity):
                parsed.append(o)
            elif isinstance(o, dict):
                d = dict(o)
                if "base_salary_k" in d:
                    d["base_monthly_salary"] = float(d.pop("base_salary_k")) * 1000.0
                if "months" in d:
                    d["salary_months"] = float(d.pop("months"))
                if "offer_id" in d:
                    d.pop("offer_id")
                parsed.append(OfferEntity(**d))
            else:
                parsed.append(o)
        return comparator.compare(parsed)


# Aliases for cross-module consistency
MultiOfferComparator = OfferComparator
OfferItem = OfferEntity
