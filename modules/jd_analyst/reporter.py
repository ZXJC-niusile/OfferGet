"""
Offer Strategy Reporter: Compiles decoded JD, matching analysis, red flags,
and predictions into a standalone bilingual interactive HTML report.
"""

import os
import json
from typing import Optional, List, Dict
from .models import (
    DecodedJD,
    CandidateProfile,
    MatcherResult,
    RedFlagReport,
    PredictionResult,
    GapState,
)


class OfferStrategyReporter:
    """
    Generates a high-impact, standalone single-file bilingual interactive HTML
    Offer Strategy Report with embedded SVGs, responsive design, and zero external dependencies.
    """

    def generate_html(
        self,
        jd: DecodedJD,
        candidate: CandidateProfile,
        matcher: MatcherResult,
        redflags: RedFlagReport,
        prediction: PredictionResult,
    ) -> str:
        """Compile all analytics into an interactive HTML report."""
        score_pct = round(matcher.final_match_score * 100, 1)
        raw_pct = round(matcher.raw_match_score * 100, 1)

        # Determine theme color based on score & veto
        if matcher.is_hard_vetoed:
            gauge_color = "#e11d48"  # Red
            status_text_cn = "触发硬门槛拦截 (扣罚后)"
            status_text_en = "Hard Threshold Vetoed"
        elif score_pct >= 75:
            gauge_color = "#10b981"  # Emerald
            status_text_cn = "高度匹配 (优质标的)"
            status_text_en = "Strong Fit"
        elif score_pct >= 55:
            gauge_color = "#f59e0b"  # Amber
            status_text_cn = "中度匹配 (需针对性补强)"
            status_text_en = "Moderate Fit"
        else:
            gauge_color = "#ef4444"  # Red
            status_text_cn = "匹配度偏低 (差距较大)"
            status_text_en = "Low Fit"

        # Generate SVG Dashboards
        gauge_svg = self._render_gauge_svg(score_pct, gauge_color)
        gap_chart_svg = self._render_gap_chart_svg(matcher)
        channel_chart_svg = self._render_channel_chart_svg(prediction)

        # Build sections
        tldr_html = self._build_tldr_html(jd, candidate, matcher, redflags, prediction, score_pct)
        thresholds_html = self._build_thresholds_html(matcher)
        decoding_html = self._build_decoding_html(jd)
        gap_matrix_html = self._build_gap_matrix_html(matcher)
        redflags_html = self._build_redflags_html(redflags)
        probability_html = self._build_probability_html(prediction, channel_chart_svg)
        top20_html = self._build_top20_html(prediction)
        action_plan_html = self._build_action_plan_html()

        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OfferGet - JD 智能深度分析与通关策略报告 | {jd.job_title}</title>
    <style>
        :root {{
            --bg-body: #0b0f19;
            --bg-card: #111827;
            --bg-card-hover: #1f2937;
            --border-color: #374151;
            --text-primary: #f9fafb;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-blue: #3b82f6;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --accent-purple: #8b5cf6;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            background-color: var(--bg-body);
            color: var(--text-primary);
            font-family: var(--font-family);
            line-height: 1.6;
            padding: 24px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            background: linear-gradient(135deg, #1e1b4b 0%, #1e293b 100%);
            border: 1px solid #4338ca;
            border-radius: 16px;
            padding: 32px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }}
        .header-title h1 {{
            font-size: 28px;
            font-weight: 800;
            color: #fff;
            margin-bottom: 8px;
        }}
        .header-title .subtitle {{
            color: #a5b4fc;
            font-size: 15px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        .badge-blue {{ background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; }}
        .badge-emerald {{ background: #064e3b; color: #6ee7b7; border: 1px solid #10b981; }}
        .badge-amber {{ background: #78350f; color: #fcd34d; border: 1px solid #f59e0b; }}
        .badge-rose {{ background: #881337; color: #fda4af; border: 1px solid #f43f5e; }}
        .badge-purple {{ background: #4c1d95; color: #c4b5fd; border: 1px solid #8b5cf6; }}
        
        .dash-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 24px;
            margin-bottom: 24px;
        }}
        .card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
            transition: all 0.2s ease;
        }}
        .card:hover {{
            border-color: #4b5563;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #1f2937;
            padding-bottom: 14px;
            margin-bottom: 18px;
        }}
        .card-header h2 {{
            font-size: 18px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .card-header .en-label {{
            font-size: 13px;
            color: var(--text-muted);
            font-weight: 400;
        }}
        
        /* Metric Score Box */
        .score-box {{
            display: flex;
            align-items: center;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .score-text {{
            text-align: center;
        }}
        .score-number {{
            font-size: 48px;
            font-weight: 900;
            line-height: 1;
        }}
        .score-status {{
            margin-top: 6px;
            font-size: 14px;
            font-weight: 600;
        }}
        .formula-card {{
            background: #0d1322;
            border: 1px dashed #2e384d;
            border-radius: 8px;
            padding: 12px;
            margin-top: 16px;
            font-size: 13px;
            color: #94a3b8;
        }}
        .formula-card code {{
            color: #38bdf8;
            font-family: Consolas, monospace;
        }}

        /* Tabs and Filters */
        .tab-bar {{
            display: flex;
            gap: 8px;
            overflow-x: auto;
            margin-bottom: 16px;
            padding-bottom: 6px;
        }}
        .tab-btn {{
            background: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 13px;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.15s;
        }}
        .tab-btn:hover, .tab-btn.active {{
            background: #3b82f6;
            color: #fff;
            border-color: #3b82f6;
        }}

        /* Table & Lists */
        .item-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .item-box {{
            background: #172033;
            border: 1px solid #28354e;
            border-radius: 10px;
            padding: 14px 18px;
            transition: border-color 0.2s;
        }}
        .item-box:hover {{
            border-color: #3b82f6;
        }}
        .item-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
        }}
        .item-title {{
            font-size: 15px;
            font-weight: 600;
            color: #f1f5f9;
        }}
        .item-desc {{
            font-size: 13px;
            color: #cbd5e1;
            margin-bottom: 6px;
        }}
        .item-meta {{
            font-size: 12px;
            color: #94a3b8;
            background: #0f172a;
            padding: 8px 12px;
            border-radius: 6px;
            margin-top: 6px;
            border-left: 3px solid #3b82f6;
        }}
        
        /* Accordion */
        details {{
            background: #172033;
            border: 1px solid #28354e;
            border-radius: 10px;
            margin-bottom: 12px;
            overflow: hidden;
        }}
        summary {{
            padding: 14px 18px;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #1e293b;
        }}
        summary:hover {{
            background: #273549;
        }}
        .details-body {{
            padding: 16px 18px;
            border-top: 1px solid #28354e;
            font-size: 14px;
            color: #cbd5e1;
        }}
        
        /* Timeline */
        .timeline {{
            position: relative;
            padding-left: 28px;
            margin-top: 16px;
        }}
        .timeline::before {{
            content: '';
            position: absolute;
            left: 10px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #334155;
        }}
        .timeline-step {{
            position: relative;
            margin-bottom: 24px;
        }}
        .timeline-step::before {{
            content: '';
            position: absolute;
            left: -23px;
            top: 4px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #3b82f6;
            border: 2px solid #0f172a;
        }}
        .timeline-title {{
            font-size: 15px;
            font-weight: 700;
            color: #e2e8f0;
            margin-bottom: 4px;
        }}
        .timeline-desc {{
            font-size: 13px;
            color: #94a3b8;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            body {{ padding: 12px; }}
            .header-title h1 {{ font-size: 22px; }}
            .dash-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="header-title">
                <h1>OfferGet 智能 JD 深度分析与通关策略报告</h1>
                <div class="subtitle">
                    <span>目标职位 / Target Role: <strong>{jd.job_title}</strong></span>
                    <span>•</span>
                    <span>团队部门 / Dept: <strong>{jd.company_or_dept}</strong></span>
                </div>
            </div>
            <div>
                <span class="badge badge-purple">AI / LLM 专家级定制解码引擎</span>
            </div>
        </header>

        <!-- TL;DR Executive Summary & Score Dashboard -->
        <div class="dash-grid">
            <!-- Score Card -->
            <div class="card">
                <div class="card-header">
                    <h2>整体匹配度与通关判定 <span class="en-label">/ Match Score & Gate</span></h2>
                    <span class="badge badge-blue">加权综合算法</span>
                </div>
                <div class="score-box">
                    <div>{gauge_svg}</div>
                    <div class="score-text">
                        <div class="score-number" style="color: {gauge_color};">{score_pct}%</div>
                        <div class="score-status" style="color: {gauge_color};">{status_text_cn}</div>
                        <div style="color: var(--text-muted); font-size: 12px;">{status_text_en}</div>
                    </div>
                </div>
                <div class="formula-card">
                    <div><strong>算法公式 / Formula:</strong></div>
                    <code>Match Score = 0.6 * MustHave ({round(matcher.must_have_score*100,1)}%) + 0.2 * NiceToHave ({round(matcher.nice_to_have_score*100,1)}%) + 0.2 * HiddenSignal ({round(matcher.hidden_signal_fit*100,1)}%)</code>
                    <div style="margin-top: 4px; font-size: 12px;">原始无扣罚分: {raw_pct}% {f' | ⚠️ 触发一票否决扣罚' if matcher.is_hard_vetoed else ''}</div>
                </div>
            </div>

            <!-- Gap Chart Card -->
            <div class="card">
                <div class="card-header">
                    <h2>五态差距分布矩阵 <span class="en-label">/ 5-State Gap Radar</span></h2>
                    <span class="badge badge-emerald">{len(matcher.gap_matrix)} 维度全景剖析</span>
                </div>
                <div>{gap_chart_svg}</div>
                <div style="display: flex; justify-content: space-around; font-size: 12px; margin-top: 14px; text-align: center;">
                    <div><span style="color:#10b981;">●</span> 已匹配: {matcher.matched_count}</div>
                    <div><span style="color:#3b82f6;">●</span> 表达缺口: {matcher.expression_gap_count}</div>
                    <div><span style="color:#f59e0b;">●</span> 证据不足: {matcher.insufficient_evidence_count}</div>
                    <div><span style="color:#f43f5e;">●</span> 真实缺口: {matcher.real_gap_count}</div>
                    <div><span style="color:#a855f7;">●</span> 待确认: {matcher.to_be_confirmed_count}</div>
                </div>
            </div>
        </div>

        <!-- Executive Summary TL;DR -->
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <h2>执行摘要与战略建议 <span class="en-label">/ Executive Summary (TL;DR)</span></h2>
                <span class="badge badge-amber">求职决胜指南</span>
            </div>
            {tldr_html}
        </div>

        <!-- Hard Thresholds Interception & Breakthrough -->
        {thresholds_html}

        <!-- 5-Layer Semantic Decoding Blueprint -->
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <h2>JD 五图层深度语义解码 <span class="en-label">/ 5-Layer Semantic Blueprint</span></h2>
                <span class="badge badge-blue">过滤 {len(jd.filtered_boilerplates)} 条公关套话</span>
            </div>
            {decoding_html}
        </div>

        <!-- 5-State Gap Matrix Details -->
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <h2>五态差距细分矩阵与补齐方案 <span class="en-label">/ 5-State Gap Matrix</span></h2>
                <span class="badge badge-purple">逐条诊断与修改指导</span>
            </div>
            {gap_matrix_html}
        </div>

        <!-- Red Flags Radar -->
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <h2>技术岗位红旗与陷阱探测 <span class="en-label">/ Red Flags & Trap Radar</span></h2>
                <span class="badge { 'badge-rose' if redflags.risk_score >= 40 else 'badge-emerald' }">风险评分: {redflags.risk_score}/100 ({redflags.overall_risk_level})</span>
            </div>
            {redflags_html}
        </div>

        <!-- Interview Probability & Channel Forecast -->
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <h2>拿面概率测算与投递渠道矩阵 <span class="en-label">/ Interview Probability Forecast</span></h2>
                <span class="badge badge-emerald">渠道乘数模型</span>
            </div>
            {probability_html}
        </div>

        <!-- Top 20 Interview Predictor -->
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <h2>面试预测 Top 20 深度押题器 <span class="en-label">/ Interview Prediction Top 20</span></h2>
                <span class="badge badge-blue">4 大维度 × 5 题全景关联</span>
            </div>
            {top20_html}
        </div>

        <!-- 6-Week Action Plan -->
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <h2>6 周通关冲刺行动计划 <span class="en-label">/ 6-Week Strategic Action Plan</span></h2>
                <span class="badge badge-emerald">从简历到 Offer 闭环</span>
            </div>
            {action_plan_html}
        </div>

        <footer style="text-align: center; color: var(--text-muted); font-size: 13px; padding: 24px 0;">
            OfferGet JD Analyst Engine • 专业级 AI/大模型算法求职决策系统 • Generated by Antigravity
        </footer>
    </div>

    <!-- Interactive Filtering Script -->
    <script>
        function filterGapMatrix(state) {{
            const buttons = document.querySelectorAll('#gap-tabs .tab-btn');
            buttons.forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            const items = document.querySelectorAll('.gap-item-row');
            items.forEach(item => {{
                if (state === 'ALL' || item.dataset.state === state) {{
                    item.style.display = 'block';
                }} else {{
                    item.style.display = 'none';
                }}
            }});
        }}

        function filterTop20(cat) {{
            const buttons = document.querySelectorAll('#top20-tabs .tab-btn');
            buttons.forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            const items = document.querySelectorAll('.q-item-row');
            items.forEach(item => {{
                if (cat === 'ALL' || item.dataset.category === cat) {{
                    item.style.display = 'block';
                }} else {{
                    item.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
"""
        return html_template

    def save_report(
        self,
        output_path: str,
        jd: DecodedJD,
        candidate: CandidateProfile,
        matcher: MatcherResult,
        redflags: RedFlagReport,
        prediction: PredictionResult,
    ) -> str:
        """Generate and save the HTML report to a file."""
        html_content = self.generate_html(jd, candidate, matcher, redflags, prediction)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return output_path

    def _render_gauge_svg(self, pct: float, color: str) -> str:
        """Render a sleek circular SVG score gauge."""
        pct = max(0.0, min(100.0, pct))
        radius = 54
        circumference = 2 * 3.14159 * radius
        dashoffset = circumference * (1.0 - pct / 100.0)

        svg = f"""<svg width="140" height="140" viewBox="0 0 140 140">
            <circle cx="70" cy="70" r="{radius}" fill="none" stroke="#1f2937" stroke-width="12" />
            <circle cx="70" cy="70" r="{radius}" fill="none" stroke="{color}" stroke-width="12"
                    stroke-dasharray="{circumference}" stroke-dashoffset="{dashoffset}"
                    stroke-linecap="round" transform="rotate(-90 70 70)" style="transition: stroke-dashoffset 0.8s ease;" />
            <text x="70" y="76" text-anchor="middle" font-size="22" font-weight="bold" fill="{color}">{pct}%</text>
        </svg>"""
        return svg

    def _render_gap_chart_svg(self, matcher: MatcherResult) -> str:
        """Render a horizontal bar distribution of the 5 gap states."""
        total = max(len(matcher.gap_matrix), 1)
        data = [
            ("已匹配 / Matched", matcher.matched_count, "#10b981"),
            ("表达缺口 / Expression Gap", matcher.expression_gap_count, "#3b82f6"),
            ("证据不足 / Insufficient", matcher.insufficient_evidence_count, "#f59e0b"),
            ("真实缺口 / Real Gap", matcher.real_gap_count, "#f43f5e"),
            ("待确认 / To Be Confirmed", matcher.to_be_confirmed_count, "#a855f7"),
        ]

        svg_parts = ['<svg width="100%" height="150" viewBox="0 0 450 150">']
        y = 12
        for label, count, color in data:
            pct_val = count / total
            width = int(pct_val * 240)
            svg_parts.append(f"""
                <text x="10" y="{y+12}" font-size="11" fill="#cbd5e1">{label}</text>
                <rect x="170" y="{y}" width="240" height="15" rx="4" fill="#1e293b" />
                <rect x="170" y="{y}" width="{max(width, 4 if count > 0 else 0)}" height="15" rx="4" fill="{color}" />
                <text x="420" y="{y+12}" font-size="11" font-weight="bold" fill="#f8fafc">{count}</text>
            """)
            y += 26
        svg_parts.append('</svg>')
        return "".join(svg_parts)

    def _render_channel_chart_svg(self, pred: PredictionResult) -> str:
        """Render channel probability comparisons in SVG."""
        forecasts = pred.probability_forecast.channel_forecasts
        svg_parts = ['<svg width="100%" height="160" viewBox="0 0 520 160">']
        y = 14
        colors = {
            "INTERNAL_REFERRAL": "#10b981",
            "RECRUITER_DIRECT": "#3b82f6",
            "HEADHUNTER": "#8b5cf6",
            "COLD_APPLICATION": "#f43f5e",
        }
        for c_key, c_val in forecasts.items():
            color = colors.get(c_key, "#3b82f6")
            avg_prob = (c_val.min_prob + c_val.max_prob) / 2.0
            bar_width = int((avg_prob / 100.0) * 260)
            svg_parts.append(f"""
                <text x="10" y="{y+13}" font-size="12" fill="#cbd5e1">{c_val.channel_name_cn}</text>
                <rect x="170" y="{y}" width="260" height="18" rx="4" fill="#1e293b" />
                <rect x="170" y="{y}" width="{max(bar_width, 4)}" height="18" rx="4" fill="{color}" />
                <text x="440" y="{y+13}" font-size="11" font-weight="bold" fill="#f8fafc">{c_val.min_prob}%-{c_val.max_prob}%</text>
            """)
            y += 34
        svg_parts.append('</svg>')
        return "".join(svg_parts)

    def _build_tldr_html(
        self,
        jd: DecodedJD,
        candidate: CandidateProfile,
        matcher: MatcherResult,
        redflags: RedFlagReport,
        pred: PredictionResult,
        score_pct: float,
    ) -> str:
        best_chan = pred.probability_forecast.channel_forecasts.get("INTERNAL_REFERRAL")
        chan_text = f"{best_chan.min_prob}%-{best_chan.max_prob}%" if best_chan else "N/A"

        return f"""
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px;">
            <div class="item-box" style="border-left: 4px solid var(--accent-blue);">
                <div style="font-size: 12px; color: var(--text-muted);">核心匹配结论 / Verdict</div>
                <div style="font-size: 16px; font-weight: bold; margin: 4px 0;">{ '⚠️ 硬门槛受限 (需破局通道)' if matcher.is_hard_vetoed else ('🏆 核心优势明显' if score_pct >= 75 else '⚖️ 具备较强竞争底座') }</div>
                <div style="font-size: 13px; color: #94a3b8;">已命中 {matcher.matched_count} 项核心要求，存在 {matcher.expression_gap_count} 项表达缺口与 {matcher.insufficient_evidence_count} 项证据不足待补足。</div>
            </div>
            <div class="item-box" style="border-left: 4px solid var(--accent-emerald);">
                <div style="font-size: 12px; color: var(--text-muted);">推荐突破渠道 / Best Channel</div>
                <div style="font-size: 16px; font-weight: bold; margin: 4px 0; color: #34d399;">内部员工内推 ({chan_text})</div>
                <div style="font-size: 13px; color: #94a3b8;">相比海投胜率放大 8.3x，可有效跨过机器ATS初筛并直接触达技术主管。</div>
            </div>
            <div class="item-box" style="border-left: 4px solid { '#f43f5e' if redflags.risk_score >= 40 else '#10b981' };">
                <div style="font-size: 12px; color: var(--text-muted);">红旗与陷阱预警 / Risk Radar</div>
                <div style="font-size: 16px; font-weight: bold; margin: 4px 0;">{redflags.overall_risk_level} 风险级别</div>
                <div style="font-size: 13px; color: #94a3b8;">侦测到 {len(redflags.flags)} 处关键警示：{redflags.summary[:50]}...</div>
            </div>
        </div>
        """

    def _build_thresholds_html(self, matcher: MatcherResult) -> str:
        if not matcher.is_hard_vetoed:
            return """
            <div class="card" style="margin-bottom: 24px; border-left: 4px solid #10b981;">
                <div class="card-header" style="margin-bottom: 0; padding-bottom: 0; border-bottom: none;">
                    <h2>硬门槛一票否决检查通过 <span class="en-label">/ Hard Thresholds Gate: Passed</span></h2>
                    <span class="badge badge-emerald">全部硬性指标达标</span>
                </div>
            </div>
            """

        reasons_li = "".join([f"<li>{r}</li>" for r in matcher.hard_veto_reasons])
        advice_li = "".join([f"<li>{a}</li>" for a in matcher.breakthrough_advice])

        return f"""
        <div class="card" style="margin-bottom: 24px; border-left: 4px solid #f43f5e; background: #1a0f14;">
            <div class="card-header">
                <h2>⚠️ 硬门槛独立拦截与破局通道建议 <span class="en-label">/ Hard Threshold Veto & Breakthrough Strategy</span></h2>
                <span class="badge badge-rose">一票否决拦截触发</span>
            </div>
            <div style="margin-bottom: 14px; font-size: 14px; color: #fca5a5;">
                <strong>拦截原因 / Veto Reasons:</strong>
                <ul style="padding-left: 20px; margin-top: 6px;">{reasons_li}</ul>
            </div>
            <div style="background: #2a1219; border: 1px dashed #f43f5e; padding: 14px; border-radius: 8px; font-size: 13px; color: #fecdd3;">
                <strong>🚀 破局通道专家建议 / Breakthrough Recommendations:</strong>
                <ul style="padding-left: 20px; margin-top: 6px;">{advice_li}</ul>
            </div>
        </div>
        """

    def _build_decoding_html(self, jd: DecodedJD) -> str:
        # Layer 1: Thresholds
        th_html = "".join([f"<span class='badge badge-blue' style='margin: 4px;'>{t.requirement}</span>" for t in jd.hard_thresholds])

        # Layer 2: Responsibilities
        resp_html = "".join([
            f"<div class='item-box'><div class='item-title'>{r.title}</div><div class='item-desc'>{r.description}</div><div class='badge badge-purple'>{r.domain}</div></div>"
            for r in jd.core_responsibilities[:4]
        ])

        # Layer 3: Core Skills
        must_skills = [s for s in jd.core_skills if s.importance == "MUST_HAVE"]
        nice_skills = [s for s in jd.core_skills if s.importance == "NICE_TO_HAVE"]
        must_tags = "".join([f"<span class='badge badge-emerald' style='margin: 3px;'>{s.name} ({s.category})</span>" for s in must_skills])
        nice_tags = "".join([f"<span class='badge badge-amber' style='margin: 3px;'>{s.name} ({s.category})</span>" for s in nice_skills])

        # Layer 4: Jargon
        jargon_html = "".join([
            f"""<div class='item-box' style='border-left: 3px solid #f59e0b;'>
                <div class='item-title' style='color:#fcd34d;'>原文黑话: &ldquo;{sig.original_text}&rdquo;</div>
                <div class='item-desc' style='margin-top:4px;'><strong>底层真相 / Real Subtext:</strong> {sig.translated_meaning}</div>
                <div style='font-size:12px; color:#f87171;'><strong>潜在风险:</strong> {sig.underlying_risk}</div>
                <div class='item-meta'><strong>应对攻防:</strong> {sig.candidate_countermeasure}</div>
            </div>"""
            for sig in jd.implicit_signals
        ])

        # Layer 5: Pain Points & KPIs
        pain_html = "".join([
            f"""<div class='item-box' style='border-left: 3px solid #3b82f6;'>
                <div class='item-title'>{p.aspect}</div>
                <div class='item-desc'>{p.description}</div>
                <div class='item-meta'><strong>核心考核目标 (KPI/SLA):</strong> <code>{p.evaluation_metric}</code></div>
            </div>"""
            for p in jd.business_pain_points
        ])

        return f"""
        <div style="display: flex; flex-direction: column; gap: 16px;">
            <details open>
                <summary>图层 1: 硬门槛指标 / Layer 1: Hard Thresholds ({len(jd.hard_thresholds)})</summary>
                <div class="details-body">{th_html or '无硬性限定'}</div>
            </details>
            <details open>
                <summary>图层 2: 核心职责 / Layer 2: Core Responsibilities ({len(jd.core_responsibilities)})</summary>
                <div class="details-body item-list">{resp_html}</div>
            </details>
            <details open>
                <summary>图层 3: 核心技能图谱 (AI/LLM深度优化) / Layer 3: Core Skills ({len(jd.core_skills)})</summary>
                <div class="details-body">
                    <div style="margin-bottom: 8px;"><strong>必备技术栈 (Must Have):</strong><br>{must_tags or '无明确标注'}</div>
                    <div><strong>加分/期望技术栈 (Nice To Have):</strong><br>{nice_tags or '无明确加分项'}</div>
                </div>
            </details>
            <details open>
                <summary>图层 4: 大厂黑话与隐性信号翻译 / Layer 4: Implicit Signals & Jargon ({len(jd.implicit_signals)})</summary>
                <div class="details-body item-list">{jargon_html or '未侦测到典型黑话套话'}</div>
            </details>
            <details open>
                <summary>图层 5: 业务痛点与考核目标 (KPIs) / Layer 5: Pain Points & Target Metrics ({len(jd.business_pain_points)})</summary>
                <div class="details-body item-list">{pain_html}</div>
            </details>
        </div>
        """

    def _build_gap_matrix_html(self, matcher: MatcherResult) -> str:
        state_colors = {
            "MATCHED": "badge-emerald",
            "EXPRESSION_GAP": "badge-blue",
            "INSUFFICIENT_EVIDENCE": "badge-amber",
            "REAL_GAP": "badge-rose",
            "TO_BE_CONFIRMED": "badge-purple",
        }

        items_html = []
        for g in matcher.gap_matrix:
            badge_cls = state_colors.get(g.state.value if isinstance(g.state, GapState) else str(g.state), "badge-blue")
            state_cn = g.state.label_cn if isinstance(g.state, GapState) else str(g.state)
            state_en = g.state.label_en if isinstance(g.state, GapState) else str(g.state)
            st_val = g.state.value if isinstance(g.state, GapState) else str(g.state)

            items_html.append(f"""
            <div class="item-box gap-item-row" data-state="{st_val}">
                <div class="item-top">
                    <div class="item-title">{g.requirement_name} <span class="badge {badge_cls}" style="margin-left: 8px;">{state_cn} / {state_en}</span></div>
                    <div style="font-size: 13px; font-weight: bold; color: #94a3b8;">得分: {g.score}</div>
                </div>
                <div class="item-desc"><strong>候选人佐证:</strong> {g.candidate_evidence}</div>
                <div style="font-size: 13px; color: #94a3b8; margin-bottom: 4px;"><strong>差距诊断:</strong> {g.gap_explanation}</div>
                <div class="item-meta"><strong>🛠️ 行动修改建议 / Actionable Advice:</strong> {g.actionable_advice}</div>
            </div>
            """)

        return f"""
        <div class="tab-bar" id="gap-tabs">
            <button class="tab-btn active" onclick="filterGapMatrix('ALL')">全部维度 ({len(matcher.gap_matrix)})</button>
            <button class="tab-btn" onclick="filterGapMatrix('MATCHED')">已匹配 ({matcher.matched_count})</button>
            <button class="tab-btn" onclick="filterGapMatrix('EXPRESSION_GAP')">表达缺口 ({matcher.expression_gap_count})</button>
            <button class="tab-btn" onclick="filterGapMatrix('INSUFFICIENT_EVIDENCE')">证据不足 ({matcher.insufficient_evidence_count})</button>
            <button class="tab-btn" onclick="filterGapMatrix('REAL_GAP')">真实缺口 ({matcher.real_gap_count})</button>
            <button class="tab-btn" onclick="filterGapMatrix('TO_BE_CONFIRMED')">待确认 ({matcher.to_be_confirmed_count})</button>
        </div>
        <div class="item-list">
            {''.join(items_html)}
        </div>
        """

    def _build_redflags_html(self, redflags: RedFlagReport) -> str:
        if not redflags.flags:
            return """
            <div style="color: #6ee7b7; padding: 12px; background: #064e3b; border-radius: 8px;">
                ✅ 经深度扫描，未在 JD 中发现明显的红旗与求职陷阱。岗位描述扎实，权责清晰。
            </div>
            """

        flags_html = []
        for f in redflags.flags:
            sev_badge = "badge-rose" if f.severity == "HIGH" else "badge-amber"
            flags_html.append(f"""
            <div class="item-box" style="border-left: 4px solid { '#f43f5e' if f.severity == 'HIGH' else '#f59e0b' };">
                <div class="item-top">
                    <div class="item-title">{f.title_cn} <span class="badge {sev_badge}">{f.severity} 风险</span></div>
                </div>
                <div style="font-size: 13px; color: #fca5a5; margin-bottom: 6px;"><strong>JD 敏感特征捕捉:</strong> &ldquo;{f.trigger_snippet}&rdquo;</div>
                <div class="item-desc"><strong>深度危害剖析 / Risk Impact:</strong> {f.risk_analysis}</div>
                <div class="item-meta" style="border-left-color: #f59e0b;"><strong>🛡️ 面试反击排查话术 / Interview Defense:</strong> {f.interview_defense}</div>
            </div>
            """)

        return f"<div class='item-list'>{''.join(flags_html)}</div>"

    def _build_probability_html(self, pred: PredictionResult, chart_svg: str) -> str:
        fc = pred.probability_forecast
        age_warning = ""
        if fc.is_ghost_job_risk:
            age_warning = f"""
            <div style="background: #451a03; border: 1px solid #b45309; padding: 12px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; color: #fef3c7;">
                ⚠️ <strong>僵尸职位警报:</strong> 该岗位已挂出 {fc.listing_age_days} 天（衰减系数 {fc.age_decay_multiplier}x），极可能已进入发Offer收尾期或纯粹作为蓄水池。普通海投基本无效，强烈建议走内部推荐直接核查HC真实性！
            </div>
            """

        return f"""
        {age_warning}
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; align-items: center;">
            <div>
                {chart_svg}
            </div>
            <div class="item-box">
                <div style="font-size: 13px; color: #94a3b8;">战略投递指导 / Strategy Summary</div>
                <div style="font-size: 14px; margin-top: 6px; line-height: 1.7; color: #f1f5f9;">{fc.strategic_summary}</div>
                <div style="margin-top: 12px; font-size: 12px; color: #a5b4fc;">
                    <strong>挂出时效调整:</strong> {fc.listing_age_days} 天 (衰减乘数: {fc.age_decay_multiplier}x)
                </div>
            </div>
        </div>
        """

    def _build_top20_html(self, pred: PredictionResult) -> str:
        qs_html = []
        for q in pred.top20_questions:
            cat_badge = {
                "ARCHITECTURE": "badge-blue",
                "PRINCIPLES": "badge-purple",
                "BQ": "badge-amber",
                "REVERSE": "badge-emerald",
            }.get(q.category_type.value if hasattr(q.category_type, "value") else str(q.category_type), "badge-blue")

            cat_val = q.category_type.value if hasattr(q.category_type, "value") else str(q.category_type)

            qs_html.append(f"""
            <div class="item-box q-item-row" data-category="{cat_val}">
                <div class="item-top">
                    <div class="item-title">#{q.question_id}. {q.question_cn}</div>
                    <span class="badge {cat_badge}">{q.category_cn}</span>
                </div>
                <div style="font-size: 12px; color: #94a3b8; font-style: italic; margin-bottom: 6px;">{q.question_en}</div>
                <div style="font-size: 12px; color: #38bdf8; margin-bottom: 4px;"><strong>🎯 关联 JD 信号:</strong> {q.jd_signal}</div>
                <div style="font-size: 13px; color: #cbd5e1; margin-bottom: 6px;"><strong>💡 面试官考察目的:</strong> {q.interviewer_intent}</div>
                <div class="item-meta"><strong>📝 通关备考要点与答题框架:</strong> {q.prep_keypoints}</div>
            </div>
            """)

        return f"""
        <div class="tab-bar" id="top20-tabs">
            <button class="tab-btn active" onclick="filterTop20('ALL')">全部押题 (20题)</button>
            <button class="tab-btn" onclick="filterTop20('ARCHITECTURE')">架构与系统设计 (5题)</button>
            <button class="tab-btn" onclick="filterTop20('PRINCIPLES')">底层原理与算法细节 (5题)</button>
            <button class="tab-btn" onclick="filterTop20('BQ')">BQ 与团队协同 (5题)</button>
            <button class="tab-btn" onclick="filterTop20('REVERSE')">候选人反问高级提问 (5题)</button>
        </div>
        <div class="item-list">
            {''.join(qs_html)}
        </div>
        """

    def _build_action_plan_html(self) -> str:
        return """
        <div class="timeline">
            <div class="timeline-step">
                <div class="timeline-title">第 1-2 周: 简历关键词对齐与表达缺口重构 (Phase 1: Resume & ATS Alignment)</div>
                <div class="timeline-desc">
                    1. 针对报告中标记为【表达缺口】的条目，将原有泛化描述（如“负责模型训练部署”）全面替换为目标 JD 强匹配术语（如“基于 vLLM PagedAttention 与 FP8 量化实现吞吐提升 3.2x”）；<br>
                    2. 在简历头部明确突出 3-5 个硬核关键词（如 3D并行、DPO对齐、FlashAttention、Tool Use）；<br>
                    3. 输出对齐版的中英文双语简历，准备好 1 页精简版专供招聘官直通沟通。
                </div>
            </div>
            <div class="timeline-step">
                <div class="timeline-title">第 3-4 周: 证据不足补齐与项目战功数据化 (Phase 2: Evidence Hardening & Metrics)</div>
                <div class="timeline-desc">
                    1. 针对【证据不足】项，严格依照 STAR 框架填补数字：补充 GPU 算力集群规模（如 64 卡 H800）、并发 QPS、P99 时延降低百分比、真实业务增量指标；<br>
                    2. 针对【真实缺口】项，在 GitHub 上检索 1 个标杆开源项目（如 FastChat/vLLM/OpenRLHF）跑通最小可用验证，记录踩坑复盘，形成“具备快速落地手感”的谈资。
                </div>
            </div>
            <div class="timeline-step">
                <div class="timeline-title">第 5 周: 核心底层原理深度复盘与模拟演练 (Phase 3: Deep Principles & Mock Interviews)</div>
                <div class="timeline-desc">
                    1. 重点攻克【押题 Top 20】中的架构设计题与算法数学推导题（FlashAttention Online Softmax、DPO损失函数对比推导、RoPE频域旋转矩阵）；<br>
                    2. 准备 3 个具有戏剧张力的 BQ 故事（Loss 发散紧急排障、业务方 Bad Case 质疑化解、跨部门推动架构重构）；<br>
                    3. 找同行好友进行 1-2 轮压力模拟面试，控制每道题阐述在 3-5 分钟内结构化展开。
                </div>
            </div>
            <div class="timeline-step">
                <div class="timeline-title">第 6 周: 渠道突破冲刺与反问攻防落地 (Phase 4: Channel Sprints & Reverse Inquiries)</div>
                <div class="timeline-desc">
                    1. 放弃盲目海投，全力锁定【内部员工内推】（胜率提升 8.3 倍）与脉脉/知乎上的业务 Leader 直联；<br>
                    2. 附带定制 Cover Letter 与开源战功链接直接发起沟通；<br>
                    3. 在技术终面与主管面中熟练运用【5道高阶反问提问】，反客为主摸清团队真实算力与业务底色，争取最优职级与薪酬 Offer。
                </div>
            </div>
        </div>
        """
