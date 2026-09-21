from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.defense.evaluator import DefenseEvaluator


@dataclass
class InterviewDialogueTurn:
    """代表面试实录中的一轮对话"""
    turn_id: int
    interviewer_question: str
    candidate_answer: str
    interviewer_challenge: str = ""
    intent_category: str = "通用技术考察"
    blindspots: List[str] = field(default_factory=list)
    metric_anomalies: List[str] = field(default_factory=list)
    omitted_key_mechanisms: List[str] = field(default_factory=list)
    turn_score: float = 80.0
    safe_response_guidance: str = ""
    verdict: str = "pass"  # "pass", "warning", "gap"


@dataclass
class NextRoundChecklist:
    """(N+1) 面针对性备战清单与综合诊断"""
    session_title: str
    target_role: str
    total_turns: int
    weak_turns_count: int
    next_round_readiness_score: float
    blindspot_summary: List[str] = field(default_factory=list)
    high_frequency_follow_ups: List[str] = field(default_factory=list)
    mandatory_metrics_to_memorize: List[str] = field(default_factory=list)
    failure_contingency_scripts: List[Dict[str, str]] = field(default_factory=list)
    dialogue_turns: List[InterviewDialogueTurn] = field(default_factory=list)
    markdown_report: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TranscriptParser:
    """面试实录长文本切分器"""

    # 正则识别面试官发言前缀
    INTERVIEWER_PREFIXES = [
        r"^(?:面试官|提问|考官|主管|Leader|Interviewer|Q\d*|问)(?:[:：\s]|\b)",
    ]
    # 正则识别候选人发言前缀
    CANDIDATE_PREFIXES = [
        r"^(?:候选人|我|应聘者|答辩人|Candidate|A\d*|答)(?:[:：\s]|\b)",
    ]

    @classmethod
    def parse(cls, transcript_text: str) -> List[InterviewDialogueTurn]:
        """将非结构化面试录音/文本整理为标准轮次列表"""
        lines = [line.strip() for line in transcript_text.strip().splitlines() if line.strip()]
        if not lines:
            return []

        turns: List[InterviewDialogueTurn] = []
        curr_turn_id = 1
        curr_q = ""
        curr_a = ""
        curr_speaker = None  # "interviewer" or "candidate"

        interviewer_pattern = re.compile("|".join(cls.INTERVIEWER_PREFIXES), re.IGNORECASE)
        candidate_pattern = re.compile("|".join(cls.CANDIDATE_PREFIXES), re.IGNORECASE)

        for line in lines:
            # 检查是否为面试官前缀
            m_interviewer = interviewer_pattern.match(line)
            m_candidate = candidate_pattern.match(line)

            if m_interviewer:
                # 如果此前已有一组问答，先封存
                if curr_q and curr_a:
                    turns.append(
                        InterviewDialogueTurn(
                            turn_id=curr_turn_id,
                            interviewer_question=curr_q.strip(),
                            candidate_answer=curr_a.strip(),
                        )
                    )
                    curr_turn_id += 1
                    curr_q = ""
                    curr_a = ""
                cleaned_line = interviewer_pattern.sub("", line).strip()
                curr_q = cleaned_line
                curr_speaker = "interviewer"
            elif m_candidate:
                cleaned_line = candidate_pattern.sub("", line).strip()
                curr_a = cleaned_line
                curr_speaker = "candidate"
            else:
                # 延续前一个说话人的内容
                if curr_speaker == "candidate":
                    curr_a = f"{curr_a}\n{line}" if curr_a else line
                elif curr_speaker == "interviewer":
                    curr_q = f"{curr_q}\n{line}" if curr_q else line
                else:
                    # 默认初始为问题
                    curr_q = line
                    curr_speaker = "interviewer"

        # 封存最后一轮
        if curr_q:
            turns.append(
                InterviewDialogueTurn(
                    turn_id=curr_turn_id,
                    interviewer_question=curr_q.strip(),
                    candidate_answer=curr_a.strip(),
                )
            )

        return turns


class PostInterviewDebriefEngine:
    """真实面试长文本复盘与 (N+1) 面备战清单引擎"""

    # 常见技术领域意图探测
    INTENT_KEYWORDS = {
        "高并发与分布式架构": ["高并发", "qps", "分布式", "微服务", "分库分表", "kafka", "mq", "熔断", "降级"],
        "数据库与存储性能": ["mysql", "redis", "索引", "事务", "锁", "缓存", "一致性", "b+树", "持久化"],
        "系统底层与网络": ["tcp", "http", "三次握手", "epoll", "io多路复用", "内存泄漏", "gc", "goroutine"],
        "业务设计与架构权衡": ["架构设计", "业务重构", "选型", "成本", "trade-off", "演进", "可用性"],
        "团队协作与工程质量": ["上线", "排障", "监控", "故障", "ci/cd", "测试", "代码规范"],
    }

    @classmethod
    def _detect_intent(cls, question: str) -> str:
        q_lower = question.lower()
        for category, kws in cls.INTENT_KEYWORDS.items():
            if any(kw in q_lower for kw in kws):
                return category
        return "专业深度与综合能力"

    @classmethod
    def debrief(
        cls,
        transcript_text: str,
        target_role: str = "后端开发工程师",
        session_title: str = "真实面试复盘",
        profile_evidence_index: Optional[Dict[str, Any]] = None,
    ) -> NextRoundChecklist:
        """执行长文本面试复盘，生成针对下一轮的备战清单"""
        turns = TranscriptParser.parse(transcript_text)
        if not turns:
            return NextRoundChecklist(
                session_title=session_title,
                target_role=target_role,
                total_turns=0,
                weak_turns_count=0,
                next_round_readiness_score=0.0,
                markdown_report="# 面试复盘报告\n未解析到有效的面试对话轮次，请检查文本格式。",
            )

        weak_turns_count = 0
        all_blindspots: List[str] = []
        follow_ups: List[str] = []
        metrics_to_memorize: List[str] = []
        contingency_scripts: List[Dict[str, str]] = []
        turn_scores: List[float] = []

        for turn in turns:
            turn.intent_category = cls._detect_intent(turn.interviewer_question)

            # 借助 100 分制防守评估器
            eval_res = DefenseEvaluator.evaluate(
                question=turn.interviewer_question,
                answer=turn.candidate_answer,
            )
            turn.turn_score = eval_res.total_score
            turn.safe_response_guidance = eval_res.safe_answer
            turn_scores.append(eval_res.total_score)

            # 诊断盲区
            if eval_res.total_score < 70.0:
                turn.verdict = "gap"
                weak_turns_count += 1
            elif eval_res.total_score < 85.0:
                turn.verdict = "warning"
            else:
                turn.verdict = "pass"

            for prob in eval_res.main_problems:
                turn.blindspots.append(prob)
                all_blindspots.append(f"[第{turn.turn_id}轮] {prob}")

            # 提取数字/指标作为备背口径
            numbers_found = re.findall(r"\d+(?:\.\d+)?(?:%|％|w|k|ms|s|qps|tps|mb|gb)?", turn.candidate_answer, re.IGNORECASE)
            for num in numbers_found:
                num = num.strip()
                if not num or (num.isdigit() and len(num) == 4 and (1990 <= int(num) <= 2030)):
                    continue  # 忽略空或年份
                if any(c.isdigit() for c in num):
                    metrics_to_memorize.append(f"参数口径核实: {num}（原问题: {turn.interviewer_question[:25]}...）")

            # 检查证据库底稿一致性
            if profile_evidence_index:
                # 校验答复中出现的未经底稿验证的绝对技术词
                verified_skills = set(profile_evidence_index.get("verified_skills", []))
                for word in ["架构重构", "全链路压测", "自研内核", "百亿级", "零故障"]:
                    if word in turn.candidate_answer and word not in profile_evidence_index.get("keywords", []):
                        turn.metric_anomalies.append(f"词汇「{word}」在底层经历底稿中缺乏硬性支撑")

            # 生成下一轮高频追问方向
            if turn.verdict in ("gap", "warning"):
                follow_up_q = f"针对【{turn.intent_category}】：请详细阐明「{turn.interviewer_question[:30]}」在极端高压场景下的熔断兜底策略与量化基线？"
                follow_ups.append(follow_up_q)
                contingency_scripts.append({
                    "turn_id": str(turn.turn_id),
                    "original_question": turn.interviewer_question,
                    "safe_script": turn.safe_response_guidance,
                })

        avg_score = sum(turn_scores) / len(turn_scores) if turn_scores else 0.0

        # 去重
        unique_blindspots = list(dict.fromkeys(all_blindspots))
        unique_follow_ups = list(dict.fromkeys(follow_ups))
        unique_metrics = list(dict.fromkeys(metrics_to_memorize))

        # 编译 Markdown 战报
        md_lines = [
            f"# 🎯 面试全复盘战报与 (N+1) 面备战清单",
            f"- **复盘主题**: {session_title}",
            f"- **目标岗位**: {target_role}",
            f"- **总对话轮次**: {len(turns)} 轮",
            f"- **薄弱/待加固轮次**: {weak_turns_count} 轮",
            f"- **下一轮面试就绪度预估分**: {avg_score:.1f} / 100",
            "",
            "## 1. 核心技术盲区梳理",
        ]
        if unique_blindspots:
            for bp in unique_blindspots[:5]:
                md_lines.append(f"- ⚠️ {bp}")
        else:
            md_lines.append("- ✅ 全场防守严密，未暴露明显事实与表达漏洞。")

        md_lines.extend([
            "",
            "## 2. (N+1) 面预计高频追问预测",
        ])
        if unique_follow_ups:
            for fu in unique_follow_ups[:4]:
                md_lines.append(f"- ❓ {fu}")
        else:
            md_lines.append("- 💡 下一轮面试官预计将侧重业务大局观与系统演化落地。")

        md_lines.extend([
            "",
            "## 3. 必背量化参数与指标口径核验",
        ])
        if unique_metrics:
            for met in unique_metrics[:5]:
                md_lines.append(f"- 📊 {met}")
        else:
            md_lines.append("- ℹ️ 建议在后续作答中主动引入基线数字（如优化前 vs 优化后对比）。")

        md_lines.extend([
            "",
            "## 4. 薄弱环节 5 步安全答题预案",
        ])
        for script_info in contingency_scripts[:3]:
            md_lines.extend([
                f"### [第{script_info['turn_id']}轮] {script_info['original_question']}",
                f"```text\n{script_info['safe_script']}\n```",
                "",
            ])

        markdown_report = "\n".join(md_lines).strip()

        return NextRoundChecklist(
            session_title=session_title,
            target_role=target_role,
            total_turns=len(turns),
            weak_turns_count=weak_turns_count,
            next_round_readiness_score=round(avg_score, 1),
            blindspot_summary=unique_blindspots,
            high_frequency_follow_ups=unique_follow_ups,
            mandatory_metrics_to_memorize=unique_metrics,
            failure_contingency_scripts=contingency_scripts,
            dialogue_turns=turns,
            markdown_report=markdown_report,
        )
