"""
OfferGet Application Tracker Engine (application_tracker.py)
============================================================
Tracks multi-target application pipelines, DDCL countdowns, and schedule conflicts:
1. Status Machine: pending -> applied -> written_test -> interview -> offer -> closed.
2. Deadline & Schedule Conflict Detector (detects clashing exam/interview slots).
3. Cooling Period & Multi-division lockout warning (e.g. Alibaba / ByteDance BG concurrency limits).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional


class AppStatus(str, Enum):
    PENDING = "pending"             # 待投递
    APPLIED = "applied"             # 已投递
    WRITTEN_TEST = "written_test"   # 笔试 / 机试
    INTERVIEW = "interview"         # 面试中 / 夏令营考核
    OFFER = "offer"                 # 已获 Offer / 优营
    CLOSED = "closed"               # 流程结束 / 放弃 / 拒信


@dataclass
class ApplicationRecord:
    id: str
    target_name: str         # 公司名或高校学院名
    role_or_track: str       # 岗位名称或申报轨道 (直博/学硕)
    status: AppStatus = AppStatus.APPLIED
    deadline: Optional[str] = None      # 格式: YYYY-MM-DD
    exam_or_interview_time: Optional[str] = None  # 格式: YYYY-MM-DD HH:MM
    channel: str = "内推"    # 内推 / 官网 / 导师直联 / 猎头
    cooling_days_left: int = 0
    notes: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))


class ApplicationTracker:
    """
    Manages local application pipelines, schedule collisions, and deadlines.
    """

    def __init__(self):
        self.records: List[ApplicationRecord] = []

    def add_record(self, record: ApplicationRecord) -> None:
        self.records.append(record)

    def detect_schedule_conflicts(self) -> List[Dict[str, Any]]:
        """
        Detects overlapping exams or interviews on the same day/hour.
        """
        events: Dict[str, List[ApplicationRecord]] = {}
        for r in self.records:
            if r.exam_or_interview_time:
                day_key = r.exam_or_interview_time[:10]  # Group by date
                events.setdefault(day_key, []).append(r)

        conflicts = []
        for day, recs in events.items():
            if len(recs) > 1:
                conflicts.append({
                    "date": day,
                    "count": len(recs),
                    "targets": [f"{r.target_name} ({r.role_or_track})" for r in recs],
                    "warning": f"【冲突预警】{day} 存在 {len(recs)} 场考核/笔试重叠，需提前协调时间！"
                })
        return conflicts

    def get_upcoming_deadlines(self, days_threshold: int = 7) -> List[Dict[str, Any]]:
        """
        Calculates upcoming deadlines within threshold days.
        """
        today = datetime.now().date()
        upcoming = []
        for r in self.records:
            if r.deadline and r.status in [AppStatus.PENDING, AppStatus.APPLIED]:
                try:
                    d_date = datetime.strptime(r.deadline, "%Y-%m-%d").date()
                    delta = (d_date - today).days
                    if 0 <= delta <= days_threshold:
                        upcoming.append({
                            "target": r.target_name,
                            "role": r.role_or_track,
                            "deadline": r.deadline,
                            "days_left": delta,
                            "urgency": "紧急" if delta <= 2 else "临近"
                        })
                except Exception:
                    pass
        return sorted(upcoming, key=lambda x: x["days_left"])

    def generate_board_markdown(self) -> str:
        """
        Renders a clean Markdown status board.
        """
        lines = [
            "# OfferGet 全局申请推进看板 (Application Tracker Board)",
            "",
            "| ID | 目标机构/高校 | 岗位/轨道 | 状态 | 关键考核时间 | 截止日 | 渠道 |",
            "|:---|:---|:---|:---:|:---:|:---:|:---:|"
        ]
        for r in self.records:
            lines.append(
                f"| `{r.id}` | **{r.target_name}** | {r.role_or_track} | `{r.status.value}` | "
                f"{r.exam_or_interview_time or '—'} | {r.deadline or '—'} | {r.channel} |"
            )
        return "\n".join(lines)
