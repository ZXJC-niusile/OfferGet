"""
OfferGet Unified Application Tracker & Storage Engine (application_tracker.py)
=============================================================================
Tracks multi-target application pipelines, DDCL countdowns, schedule conflicts,
state transition timelines, evidence snapshots, duplicate submission collisions,
offer compensation comparisons, and outcome feedback loops with SQLite/local
persistent storage.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.artifacts import write_json_atomic


class AppStatus(str, Enum):
    PENDING = "pending"             # 待投递
    APPLIED = "applied"             # 已投递
    WRITTEN_TEST = "written_test"   # 笔试 / 机试
    INTERVIEW = "interview"         # 面试中 / 夏令营考核
    OFFER = "offer"                 # 已获 Offer / 优营
    CLOSED = "closed"               # 流程结束 / 放弃 / 拒信

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_string(cls, val: Any) -> AppStatus:
        """Coerces any raw status string or enum to canonical AppStatus."""
        if isinstance(val, AppStatus):
            return val
        s = str(val.value if hasattr(val, "value") else val).strip().lower()
        if any(k in s for k in ["offer", "优营"]):
            return cls.OFFER
        if any(k in s for k in ["interview", "面试", "夏令营", "复试"]):
            return cls.INTERVIEW
        if any(k in s for k in ["written", "test", "笔试", "机试"]):
            return cls.WRITTEN_TEST
        if any(k in s for k in ["closed", "reject", "未通过", "淘汰", "挂", "withdrawn", "放弃"]):
            return cls.CLOSED
        if any(k in s for k in ["applied", "已投递", "在途", "网申"]):
            return cls.APPLIED
        return cls.PENDING

    def to_guard_status(self) -> str:
        """Maps to DuplicateApplicationGuard status string."""
        if self == AppStatus.INTERVIEW:
            return "interviewing"
        if self == AppStatus.OFFER:
            return "offered"
        if self == AppStatus.CLOSED:
            return "rejected"
        return "pending"


@dataclass
class StatusEvent:
    """A historical state transition event."""
    timestamp: str
    from_status: str
    to_status: str
    note: str = ""

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


class OutcomeStage(str, Enum):
    """Canonical process stage vocabulary for outcome records."""
    APPLIED = "applied"               # 已投递
    SCREENING = "screening"           # 简历筛选
    WRITTEN_TEST = "written_test"     # 笔试 / 机试
    INTERVIEW = "interview"           # 面试
    OFFER = "offer"                   # Offer 环节
    CLOSED = "closed"                 # 流程关闭

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_string(cls, val: Any) -> "OutcomeStage":
        if isinstance(val, OutcomeStage):
            return val
        s = str(val.value if hasattr(val, "value") else val).strip().lower()
        aliases = {
            "投递": cls.APPLIED, "已投递": cls.APPLIED,
            "筛选": cls.SCREENING, "简历": cls.SCREENING, "screening": cls.SCREENING,
            "笔试": cls.WRITTEN_TEST, "机试": cls.WRITTEN_TEST,
            "面试": cls.INTERVIEW, "复试": cls.INTERVIEW, "夏令营": cls.INTERVIEW,
            "offer": cls.OFFER, "优营": cls.OFFER,
            "结束": cls.CLOSED, "关闭": cls.CLOSED,
        }
        try:
            return cls(s)
        except ValueError:
            if s in aliases:
                return aliases[s]
        raise ValueError(f"unknown outcome stage: {val}")


class OutcomeResult(str, Enum):
    """Canonical result vocabulary for outcome records."""
    ADVANCED = "advanced"             # 通过进入下一环节
    REJECTED = "rejected"             # 未通过
    WITHDRAWN = "withdrawn"           # 主动退出
    NO_RESPONSE = "no_response"       # 无回应
    OFFER_RECEIVED = "offer_received" # 收到 Offer
    OTHER = "other"                   # 其他

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_string(cls, val: Any) -> "OutcomeResult":
        if isinstance(val, OutcomeResult):
            return val
        s = str(val.value if hasattr(val, "value") else val).strip().lower()
        aliases = {
            "通过": cls.ADVANCED, "晋级": cls.ADVANCED,
            "拒绝": cls.REJECTED, "未通过": cls.REJECTED, "挂": cls.REJECTED,
            "退出": cls.WITHDRAWN, "放弃": cls.WITHDRAWN,
            "无回应": cls.NO_RESPONSE, "无音讯": cls.NO_RESPONSE,
            "收到offer": cls.OFFER_RECEIVED, "拿到offer": cls.OFFER_RECEIVED,
            "其他": cls.OTHER,
        }
        try:
            return cls(s)
        except ValueError:
            if s in aliases:
                return aliases[s]
        raise ValueError(f"unknown outcome result: {val}")


FEEDBACK_TAGS = frozenset(
    {
        "technical_depth",     # 技术深度
        "communication",       # 沟通表达
        "system_design",       # 系统设计
        "domain_experience",   # 领域经验
        "leadership",          # 领导力
        "collaboration",       # 团队协作
        "other",               # 其他
    }
)


def _canonical_outcome_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


@dataclass
class OutcomeRecord:
    """One observed process outcome with feedback, reflection and next action.

    ``outcome_id`` is a deterministic idempotency digest: recording the same
    logical outcome twice replays instead of duplicating history.
    """

    application_id: str
    stage: OutcomeStage
    result: OutcomeResult
    feedback_text: str = ""
    reflection_text: str = ""
    next_action_text: str = ""
    feedback_tags: List[str] = field(default_factory=list)
    occurred_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    outcome_id: str = ""

    def __post_init__(self) -> None:
        self.stage = OutcomeStage.from_string(self.stage)
        self.result = OutcomeResult.from_string(self.result)
        tags: List[str] = []
        for tag in self.feedback_tags:
            t = str(tag).strip().lower()
            if t not in FEEDBACK_TAGS:
                raise ValueError(f"unknown feedback tag: {tag}")
            if t not in tags:
                tags.append(t)
        self.feedback_tags = tags
        self.feedback_text = str(self.feedback_text or "")
        self.reflection_text = str(self.reflection_text or "")
        self.next_action_text = str(self.next_action_text or "")
        if not self.occurred_at:
            self.occurred_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        if not self.outcome_id:
            self.outcome_id = self.compute_id()

    def compute_id(self) -> str:
        return _canonical_outcome_hash({
            "application_id": self.application_id,
            "stage": self.stage.value,
            "result": self.result.value,
            "feedback_text": self.feedback_text,
            "reflection_text": self.reflection_text,
            "next_action_text": self.next_action_text,
            "feedback_tags": self.feedback_tags,
            "occurred_at": self.occurred_at,
        })

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["stage"] = self.stage.value
        data["result"] = self.result.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutcomeRecord":
        return cls(
            application_id=str(data.get("application_id", "")),
            stage=OutcomeStage.from_string(data.get("stage", OutcomeStage.APPLIED.value)),
            result=OutcomeResult.from_string(data.get("result", OutcomeResult.OTHER.value)),
            feedback_text=str(data.get("feedback_text", "")),
            reflection_text=str(data.get("reflection_text", "")),
            next_action_text=str(data.get("next_action_text", "")),
            feedback_tags=list(data.get("feedback_tags", [])),
            occurred_at=str(data.get("occurred_at", "")),
            outcome_id=str(data.get("outcome_id", "")),
        )


@dataclass
class ResumeVersion:
    """Immutable metadata for a generated, application-linked resume version."""

    application_id: Optional[str]
    proposal_id: Optional[str]
    profile_hash: str
    jd_hash: str = ""
    theme: str = ""
    output_paths: Dict[str, str] = field(default_factory=dict)
    artifact_status: Dict[str, str] = field(default_factory=dict)
    artifact_hashes: Dict[str, str] = field(default_factory=dict)
    accept_phase: str = "completed"
    label: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    version_id: str = ""

    def __post_init__(self) -> None:
        if not self.profile_hash:
            raise ValueError("profile_hash is required")
        if not self.version_id:
            self.version_id = _canonical_outcome_hash({
                "application_id": self.application_id,
                "proposal_id": self.proposal_id,
                "profile_hash": self.profile_hash,
                "jd_hash": self.jd_hash,
                "theme": self.theme,
                "output_paths": self.output_paths,
                "artifact_status": self.artifact_status,
                "artifact_hashes": self.artifact_hashes,
                "accept_phase": self.accept_phase,
            })

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResumeVersion":
        return cls(
            application_id=data.get("application_id"),
            proposal_id=data.get("proposal_id"),
            profile_hash=str(data.get("profile_hash", "")),
            jd_hash=str(data.get("jd_hash", "")),
            theme=str(data.get("theme", "")),
            output_paths=dict(data.get("output_paths", {})),
            artifact_status=dict(data.get("artifact_status", {})),
            artifact_hashes=dict(data.get("artifact_hashes", {})),
            accept_phase=str(data.get("accept_phase", "completed")),
            label=str(data.get("label", "")),
            created_at=str(data.get("created_at", "")) or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            version_id=str(data.get("version_id", "")),
        )


@dataclass
class ApplicationRecord:
    """Unified application record supporting tracking, collision check, timeline, and offer data."""
    id: str
    target_name: str                               # 公司名或高校学院名
    role_or_track: str                             # 岗位名称或申报轨道 (直博/学硕)
    status: AppStatus = AppStatus.APPLIED
    deadline: Optional[str] = None                 # 格式: YYYY-MM-DD
    exam_or_interview_time: Optional[str] = None   # 格式: YYYY-MM-DD HH:MM
    channel: str = "内推"                          # 内推 / 官网 / 导师直联 / 猎头
    cooling_days_left: int = 0
    notes: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    applied_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    status_history: List[Dict[str, str]] = field(default_factory=list)
    evidence_snapshot: Dict[str, Any] = field(default_factory=dict)
    offer_details: Optional[Dict[str, Any]] = None
    collision_risk: Optional[str] = None
    target_level: str = ""                         # 职级/阶段 (e.g. P6, P7, 校招, 实习, 学硕, 直博)
    portal_url: str = ""                           # 网申链接/系统页面
    recruiter_contact: str = ""                    # HR/猎头/导师联系方式

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = AppStatus.from_string(self.status)
        if not self.status_history and self.status:
            self.status_history.append({
                "timestamp": self.updated_at,
                "from_status": "",
                "to_status": str(self.status.value if hasattr(self.status, "value") else self.status),
                "note": "初始化创建",
            })

    def transition_status(self, new_status: Union[AppStatus, str], note: str = "") -> None:
        """Transitions to a new status and logs to the status history timeline."""
        old_val = str(self.status.value if hasattr(self.status, "value") else self.status)
        if isinstance(new_status, str):
            new_status = AppStatus.from_string(new_status)
        new_val = str(new_status.value if hasattr(new_status, "value") else new_status)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.status = new_status
        self.updated_at = now_str
        self.status_history.append({
            "timestamp": now_str,
            "from_status": old_val,
            "to_status": new_val,
            "note": note,
        })

    def attach_offer(self, offer_data: Dict[str, Any]) -> None:
        """Attaches offer compensation breakdown."""
        self.offer_details = copy_offer = dict(offer_data)
        self.transition_status(AppStatus.OFFER, note=f"收到 Offer: {copy_offer.get('title', self.role_or_track)}")

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if hasattr(self.status, "value") else str(self.status)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ApplicationRecord:
        d = dict(data)
        stat = d.get("status", AppStatus.APPLIED)
        if isinstance(stat, str):
            try:
                stat = AppStatus(stat)
            except ValueError:
                pass
        d["status"] = stat
        valid_fields = {f.name for f in fields(cls)}
        clean_d = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**clean_d)


def create_evidence_snapshot(
    profile: Union[Dict[str, Any], Any],
    jd: Union[Any, Dict[str, Any], str],
    matcher_result: Optional[Any] = None,
    ats_score: Optional[float] = None,
    evidence_graph: Optional[Any] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Creates an immutable, verifiable application scoring & evidence snapshot.

    Implements the OfferGet immutable snapshot contract (ADR-011):
    Captures exact profile fingerprint, JD fingerprint, match score, gap matrix,
    and verified evidence claims at the time of evaluation or application submission.
    """
    from core.jd_compat import to_canonical
    from core.profile_adapter import ProfileContext

    ctx = ProfileContext.from_profile(profile)
    canon_jd = to_canonical(jd)

    from core.fingerprints import jd_fingerprint, profile_fingerprint

    prof_hash = profile_fingerprint(ctx)
    jd_hash = jd_fingerprint(canon_jd)

    match_score = None
    gap_summary = []

    def _ratio_score(value: Any) -> Optional[float]:
        if value is None:
            return None
        numeric = float(value)
        return numeric / 100.0 if abs(numeric) > 1.0 else numeric

    def _percent_score(value: Any) -> int:
        numeric = float(value)
        return round(numeric * 100) if abs(numeric) <= 1.0 else round(numeric)

    if matcher_result is not None:
        if isinstance(matcher_result, dict):
            match_score = matcher_result.get("overall_score", matcher_result.get("overall_match_score"))
            if match_score is None:
                match_score = matcher_result.get("final_match_score", matcher_result.get("match_score"))
            raw_gaps = matcher_result.get("gap_matrix", [])
        else:
            match_score = getattr(matcher_result, "overall_score", None)
            if match_score is None:
                match_score = getattr(matcher_result, "final_match_score", None)
            raw_gaps = getattr(matcher_result, "gap_matrix", [])
        for g in raw_gaps:
            if isinstance(g, dict):
                state_val = g.get("state", "")
                if hasattr(state_val, "value"):
                    state_val = state_val.value
                gap_summary.append({
                    "requirement": g.get("requirement_name", ""),
                    "state": state_val,
                    "score": _percent_score(g.get("score", 0.0)),
                    "evidence": g.get("candidate_evidence", ""),
                })
            else:
                state_val = g.state.value if hasattr(g.state, "value") else str(g.state)
                gap_summary.append({
                    "requirement": g.requirement_name,
                    "state": state_val,
                    "score": _percent_score(getattr(g, "score", 0.0)),
                    "evidence": getattr(g, "candidate_evidence", ""),
                })
        match_score = _ratio_score(match_score)

    graph_snapshot = None
    if evidence_graph is not None and hasattr(evidence_graph, "audit_snapshot"):
        graph_snapshot = evidence_graph.audit_snapshot()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot_id = f"SNAP-{time.time_ns()}-{prof_hash[:6]}"

    return {
        "snapshot_id": snapshot_id,
        "created_at": now_str,
        "profile_fingerprint": prof_hash,
        "jd_fingerprint": jd_hash,
        "job_title": canon_jd.job_title,
        "company_or_dept": canon_jd.company_or_dept,
        "candidate_name": ctx.normalized_profile.get("candidate", {}).get("name", "候选人"),
        "match_score": match_score,
        "ats_score": ats_score,
        "verified_skills_count": len(ctx.skills),
        "gap_matrix": gap_summary,
        "evidence_graph": graph_snapshot,
        "notes": notes,
    }


class ApplicationStore:
    """
    Lightweight SQLite / JSON persistent storage engine for application tracking.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = ":memory:"):
        self.db_path = str(db_path) if db_path else ":memory:"
        self._shared_conn: Optional[sqlite3.Connection] = None
        self._file_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:")
            self._shared_conn.row_factory = sqlite3.Row
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._init_db()
        except Exception:
            self.close()
            raise

    def _get_connection(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        if self._file_conn is None:
            self._file_conn = sqlite3.connect(self.db_path)
            self._file_conn.row_factory = sqlite3.Row
        return self._file_conn

    def close(self) -> None:
        """Closes all active SQLite connections."""
        if self._file_conn is not None:
            try:
                self._file_conn.close()
            except Exception:
                pass
            self._file_conn = None
        if self._shared_conn is not None:
            try:
                self._shared_conn.close()
            except Exception:
                pass
            self._shared_conn = None

    def __enter__(self) -> ApplicationStore:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    CURRENT_SCHEMA_VERSION: int = 8

    def _init_db(self) -> None:
        conn = self._get_connection()
        cur = conn.execute("PRAGMA user_version")
        row = cur.fetchone()
        current_v = row[0] if row else 0
        if current_v > self.CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Unsupported future application schema v{current_v}; "
                f"current version is v{self.CURRENT_SCHEMA_VERSION}"
            )
        if current_v < self.CURRENT_SCHEMA_VERSION:
            self._run_migrations(conn, current_v)

    def _run_migrations(self, conn: sqlite3.Connection, from_version: int) -> None:
        """Executes sequential forward schema migrations."""
        if from_version < 1:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    target_name TEXT NOT NULL,
                    role_or_track TEXT NOT NULL,
                    status TEXT NOT NULL,
                    deadline TEXT,
                    exam_or_interview_time TEXT,
                    channel TEXT,
                    cooling_days_left INTEGER DEFAULT 0,
                    notes TEXT,
                    applied_date TEXT,
                    updated_at TEXT,
                    collision_risk TEXT,
                    status_history_json TEXT,
                    evidence_snapshot_json TEXT,
                    offer_details_json TEXT
                )
                """
            )
            conn.execute("PRAGMA user_version = 1")
            conn.commit()

        if from_version < 2:
            cur = conn.execute("PRAGMA table_info(applications)")
            existing_cols = {r[1] for r in cur.fetchall()}
            if "target_level" not in existing_cols:
                conn.execute("ALTER TABLE applications ADD COLUMN target_level TEXT DEFAULT ''")
            if "portal_url" not in existing_cols:
                conn.execute("ALTER TABLE applications ADD COLUMN portal_url TEXT DEFAULT ''")
            if "recruiter_contact" not in existing_cols:
                conn.execute("ALTER TABLE applications ADD COLUMN recruiter_contact TEXT DEFAULT ''")
            conn.execute("PRAGMA user_version = 2")
            conn.commit()

        if from_version < 3:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS material_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    application_id TEXT,
                    source_profile_hash TEXT NOT NULL,
                    source_jd_hash TEXT NOT NULL,
                    patches_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    accepted_patch_ids_json TEXT NOT NULL DEFAULT '[]',
                    proposal_hash TEXT NOT NULL,
                    conflict_reason TEXT NOT NULL DEFAULT '',
                    applied_phase TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("PRAGMA user_version = 3")
            conn.commit()

        if from_version < 4:
            existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(material_proposals)").fetchall()}
            if "application_id" not in existing_cols:
                conn.execute("ALTER TABLE material_proposals ADD COLUMN application_id TEXT")
            conn.execute("PRAGMA user_version = 4")
            conn.commit()

        if from_version < 5:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS application_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    result TEXT NOT NULL,
                    feedback_text TEXT NOT NULL DEFAULT '',
                    reflection_text TEXT NOT NULL DEFAULT '',
                    next_action_text TEXT NOT NULL DEFAULT '',
                    feedback_tags_json TEXT NOT NULL DEFAULT '[]',
                    occurred_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_outcomes_application ON application_outcomes(application_id, occurred_at DESC)"
            )
            conn.execute("PRAGMA user_version = 5")
            conn.commit()

        if from_version < 6:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resume_versions (
                    version_id TEXT PRIMARY KEY,
                    application_id TEXT,
                    proposal_id TEXT,
                    profile_hash TEXT NOT NULL,
                    jd_hash TEXT NOT NULL DEFAULT '',
                    theme TEXT NOT NULL DEFAULT '',
                    output_paths_json TEXT NOT NULL DEFAULT '{}',
                    label TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resume_versions_application ON resume_versions(application_id, created_at DESC)"
            )
            conn.execute("PRAGMA user_version = 6")
            conn.commit()

        if from_version < 7:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'resume_versions'"
            ).fetchone()
            if table_exists is None:
                conn.execute(
                    """
                    CREATE TABLE resume_versions (
                        version_id TEXT PRIMARY KEY,
                        application_id TEXT,
                        proposal_id TEXT,
                        profile_hash TEXT NOT NULL,
                        jd_hash TEXT NOT NULL DEFAULT '',
                        theme TEXT NOT NULL DEFAULT '',
                        output_paths_json TEXT NOT NULL DEFAULT '{}',
                        artifact_status_json TEXT NOT NULL DEFAULT '{}',
                        artifact_hashes_json TEXT NOT NULL DEFAULT '{}',
                        accept_phase TEXT NOT NULL DEFAULT 'completed',
                        label TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL
                    )
                    """
                )
            else:
                existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(resume_versions)").fetchall()}
                if "artifact_status_json" not in existing_cols:
                    conn.execute("ALTER TABLE resume_versions ADD COLUMN artifact_status_json TEXT NOT NULL DEFAULT '{}' ")
                if "artifact_hashes_json" not in existing_cols:
                    conn.execute("ALTER TABLE resume_versions ADD COLUMN artifact_hashes_json TEXT NOT NULL DEFAULT '{}' ")
                if "accept_phase" not in existing_cols:
                    conn.execute("ALTER TABLE resume_versions ADD COLUMN accept_phase TEXT NOT NULL DEFAULT 'completed'")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resume_versions_application ON resume_versions(application_id, created_at DESC)"
            )
            conn.execute("PRAGMA user_version = 7")
            conn.commit()

        if from_version < 8:
            existing_p_cols = {row[1] for row in conn.execute("PRAGMA table_info(material_proposals)").fetchall()}
            if "applied_phase" not in existing_p_cols:
                conn.execute("ALTER TABLE material_proposals ADD COLUMN applied_phase TEXT NOT NULL DEFAULT ''")
            conn.execute("PRAGMA user_version = 8")
            conn.commit()

    def save(self, record: ApplicationRecord) -> None:
        """Inserts or updates an application record atomically."""
        stat_val = record.status.value if hasattr(record.status, "value") else str(record.status)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO applications (
                    id, target_name, role_or_track, status, deadline,
                    exam_or_interview_time, channel, cooling_days_left, notes,
                    applied_date, updated_at, collision_risk,
                    status_history_json, evidence_snapshot_json, offer_details_json,
                    target_level, portal_url, recruiter_contact
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    target_name=excluded.target_name,
                    role_or_track=excluded.role_or_track,
                    status=excluded.status,
                    deadline=excluded.deadline,
                    exam_or_interview_time=excluded.exam_or_interview_time,
                    channel=excluded.channel,
                    cooling_days_left=excluded.cooling_days_left,
                    notes=excluded.notes,
                    applied_date=excluded.applied_date,
                    updated_at=excluded.updated_at,
                    collision_risk=excluded.collision_risk,
                    status_history_json=excluded.status_history_json,
                    evidence_snapshot_json=excluded.evidence_snapshot_json,
                    offer_details_json=excluded.offer_details_json,
                    target_level=excluded.target_level,
                    portal_url=excluded.portal_url,
                    recruiter_contact=excluded.recruiter_contact
                """,
                (
                    record.id,
                    record.target_name,
                    record.role_or_track,
                    stat_val,
                    record.deadline,
                    record.exam_or_interview_time,
                    record.channel,
                    record.cooling_days_left,
                    record.notes,
                    record.applied_date,
                    record.updated_at,
                    record.collision_risk,
                    json.dumps(record.status_history, ensure_ascii=False),
                    json.dumps(record.evidence_snapshot, ensure_ascii=False),
                    json.dumps(record.offer_details, ensure_ascii=False) if record.offer_details else None,
                    record.target_level or "",
                    record.portal_url or "",
                    record.recruiter_contact or "",
                ),
            )
            conn.commit()

    def attach_evidence_snapshot(self, record_id: str, snapshot: Dict[str, Any]) -> bool:
        """Persist an immutable career-review snapshot onto an application record."""
        if not isinstance(snapshot, dict):
            raise TypeError("evidence snapshot must be a dictionary")
        payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        with self._get_connection() as conn:
            result = conn.execute(
                "UPDATE applications SET evidence_snapshot_json = ?, updated_at = ? WHERE id = ?",
                (payload, datetime.now().strftime("%Y-%m-%d %H:%M"), record_id),
            )
            conn.commit()
            return result.rowcount == 1

    def save_material_proposal(self, proposal: Any) -> None:
        """Create or update a serialized MaterialProposal."""
        from core.material_proposal import MaterialProposal

        if not isinstance(proposal, MaterialProposal):
            raise TypeError("proposal must be a MaterialProposal")
        data = proposal.to_dict()
        with self._get_connection() as conn:
            if data.get("application_id"):
                exists = conn.execute(
                    "SELECT 1 FROM applications WHERE id = ?",
                    (data["application_id"],),
                ).fetchone()
                if exists is None:
                    raise ValueError(
                        f"application_id does not exist: {data['application_id']}"
                    )
            conn.execute(
                """
                INSERT INTO material_proposals (
                    proposal_id, application_id, source_profile_hash, source_jd_hash, patches_json,
                    status, accepted_patch_ids_json, proposal_hash, conflict_reason, applied_phase, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    application_id=excluded.application_id,
                    source_profile_hash=excluded.source_profile_hash,
                    source_jd_hash=excluded.source_jd_hash,
                    patches_json=excluded.patches_json,
                    status=excluded.status,
                    accepted_patch_ids_json=excluded.accepted_patch_ids_json,
                    proposal_hash=excluded.proposal_hash,
                    conflict_reason=excluded.conflict_reason,
                    applied_phase=excluded.applied_phase
                """,
                (
                    data["proposal_id"], data.get("application_id"), data["source_profile_hash"], data["source_jd_hash"],
                    json.dumps(data["patches"], ensure_ascii=False, sort_keys=True),
                    data["status"], json.dumps(data["accepted_patch_ids"]),
                    data["proposal_hash"], data["conflict_reason"],
                    data.get("applied_phase", ""),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()

    def get_material_proposal(self, proposal_id: str) -> Any:
        from core.material_proposal import MaterialProposal

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM material_proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        return MaterialProposal.from_dict({
            "proposal_id": data["proposal_id"],
            "application_id": data.get("application_id"),
            "source_profile_hash": data["source_profile_hash"],
            "source_jd_hash": data["source_jd_hash"],
            "patches": json.loads(data["patches_json"]),
            "status": data["status"],
            "accepted_patch_ids": json.loads(data["accepted_patch_ids_json"]),
            "proposal_hash": data["proposal_hash"],
            "conflict_reason": data["conflict_reason"],
            "applied_phase": data.get("applied_phase", ""),
        })

    def list_material_proposals(
        self,
        status: Optional[str] = None,
        application_id: Optional[str] = None,
        company: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[Any]:
        with self._get_connection() as conn:
            query = (
                "SELECT DISTINCT p.proposal_id FROM material_proposals p "
                "LEFT JOIN applications a ON a.id = p.application_id WHERE 1=1"
            )
            params: List[str] = []
            if status:
                query += " AND p.status = ?"
                params.append(status)
            if application_id:
                query += " AND p.application_id = ?"
                params.append(application_id)
            if company:
                query += " AND a.target_name = ?"
                params.append(company)
            if role:
                query += " AND a.role_or_track = ?"
                params.append(role)
            query += " ORDER BY p.created_at DESC"
            ids = [row[0] for row in conn.execute(query, params).fetchall()]
        return [self.get_material_proposal(proposal_id) for proposal_id in ids]

    def get(self, record_id: str) -> Optional[ApplicationRecord]:
        """Fetches a single record by ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM applications WHERE id = ?", (record_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def get_application_detail(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Return an application record together with linked proposal summaries."""
        record = self.get(record_id)
        if record is None:
            return None
        proposals = self.list_material_proposals(application_id=record_id)
        versions = self.list_resume_versions(application_id=record_id)
        outcomes = self.list_outcomes(record_id)
        return {
            "application": record.to_dict(),
            "proposals": [
                {
                    "proposal_id": proposal.proposal_id,
                    "status": proposal.status.value,
                    "proposal_hash": proposal.proposal_hash,
                    "patch_count": len(proposal.patches),
                    "accepted_patch_ids": list(proposal.accepted_patch_ids),
                    "conflict_reason": proposal.conflict_reason,
                }
                for proposal in proposals
            ],
            "resume_versions": [version.to_dict() for version in versions],
            "outcomes": [outcome.to_dict() for outcome in outcomes],
        }

    def list_all(self) -> List[ApplicationRecord]:
        """Lists all records ordered by updated_at descending."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM applications ORDER BY updated_at DESC")
            return [self._row_to_record(r) for r in cur.fetchall()]

    def record_outcome(self, outcome: OutcomeRecord) -> Dict[str, Any]:
        """Persist one process outcome idempotently.

        Returns ``{"replayed": bool, "outcome": dict}``. Re-recording the same
        logical outcome (same digest) replays without duplicating history.
        """
        if not isinstance(outcome, OutcomeRecord):
            raise TypeError("outcome must be an OutcomeRecord")
        if outcome.outcome_id != outcome.compute_id():
            raise ValueError("outcome_id does not match the canonical outcome content")
        with self._get_connection() as conn:
            exists_app = conn.execute(
                "SELECT 1 FROM applications WHERE id = ?", (outcome.application_id,)
            ).fetchone()
            if exists_app is None:
                raise ValueError(f"application_id does not exist: {outcome.application_id}")
            existing = conn.execute(
                "SELECT * FROM application_outcomes WHERE outcome_id = ?",
                (outcome.outcome_id,),
            ).fetchone()
            if existing is not None:
                stored = self._row_to_outcome(existing)
                if stored.to_dict() != outcome.to_dict():
                    raise ValueError("outcome_id collision: existing outcome content differs")
                return {"replayed": True, "outcome": stored.to_dict()}
            conn.execute(
                """
                INSERT OR IGNORE INTO application_outcomes (
                    outcome_id, application_id, stage, result, feedback_text,
                    reflection_text, next_action_text, feedback_tags_json,
                    occurred_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.outcome_id, outcome.application_id, outcome.stage.value,
                    outcome.result.value, outcome.feedback_text, outcome.reflection_text,
                    outcome.next_action_text,
                    json.dumps(outcome.feedback_tags, ensure_ascii=False),
                    outcome.occurred_at,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
        return {"replayed": False, "outcome": outcome.to_dict()}

    def list_outcomes(self, application_id: Optional[str] = None) -> List[OutcomeRecord]:
        """Lists outcome records ordered by occurred_at descending."""
        with self._get_connection() as conn:
            if application_id:
                rows = conn.execute(
                    "SELECT * FROM application_outcomes WHERE application_id = ? ORDER BY occurred_at DESC",
                    (application_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM application_outcomes ORDER BY occurred_at DESC"
                ).fetchall()
        return [self._row_to_outcome(row) for row in rows]

    def outcome_insights(self) -> Dict[str, Any]:
        """Aggregate outcome feedback into actionable cross-application insight."""
        outcomes = self.list_outcomes()
        by_result: Dict[str, int] = {}
        by_stage: Dict[str, int] = {}
        tag_counter: Dict[str, int] = {}
        applications = set()
        for outcome in outcomes:
            by_result[outcome.result.value] = by_result.get(outcome.result.value, 0) + 1
            by_stage[outcome.stage.value] = by_stage.get(outcome.stage.value, 0) + 1
            applications.add(outcome.application_id)
            for tag in outcome.feedback_tags:
                tag_counter[tag] = tag_counter.get(tag, 0) + 1
        return {
            "total_outcomes": len(outcomes),
            "applications_with_outcomes": len(applications),
            "by_result": dict(sorted(by_result.items(), key=lambda kv: (-kv[1], kv[0]))),
            "by_stage": dict(sorted(by_stage.items(), key=lambda kv: (-kv[1], kv[0]))),
            "top_feedback_tags": sorted(tag_counter.items(), key=lambda kv: (-kv[1], kv[0])),
        }

    def save_resume_version(self, version: ResumeVersion) -> None:
        """Persist immutable version metadata; conflicting content is rejected."""
        if not isinstance(version, ResumeVersion):
            raise TypeError("version must be a ResumeVersion")
        if version.application_id:
            with self._get_connection() as conn:
                if conn.execute("SELECT 1 FROM applications WHERE id = ?", (version.application_id,)).fetchone() is None:
                    raise ValueError(f"application_id does not exist: {version.application_id}")
                existing = conn.execute("SELECT * FROM resume_versions WHERE version_id = ?", (version.version_id,)).fetchone()
                if existing is not None:
                    stored = self._row_to_resume_version(existing)
                    if stored.to_dict() != version.to_dict():
                        raise ValueError("version_id collision: existing version content differs")
                    return
                conn.execute(
                    """
                    INSERT INTO resume_versions (
                        version_id, application_id, proposal_id, profile_hash, jd_hash,
                        theme, output_paths_json, artifact_status_json, artifact_hashes_json,
                        accept_phase, label, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version.version_id, version.application_id, version.proposal_id,
                        version.profile_hash, version.jd_hash, version.theme,
                        json.dumps(version.output_paths, ensure_ascii=False, sort_keys=True),
                        json.dumps(version.artifact_status, ensure_ascii=False, sort_keys=True),
                        json.dumps(version.artifact_hashes, ensure_ascii=False, sort_keys=True),
                        version.accept_phase,
                        version.label, version.created_at,
                    ),
                )
                conn.commit()
            return
        with self._get_connection() as conn:
            existing = conn.execute("SELECT * FROM resume_versions WHERE version_id = ?", (version.version_id,)).fetchone()
            if existing is not None and self._row_to_resume_version(existing).to_dict() != version.to_dict():
                raise ValueError("version_id collision: existing version content differs")
            conn.execute(
                "INSERT OR IGNORE INTO resume_versions (version_id, application_id, proposal_id, profile_hash, jd_hash, theme, output_paths_json, artifact_status_json, artifact_hashes_json, accept_phase, label, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (version.version_id, None, version.proposal_id, version.profile_hash, version.jd_hash, version.theme, json.dumps(version.output_paths, ensure_ascii=False, sort_keys=True), json.dumps(version.artifact_status, ensure_ascii=False, sort_keys=True), json.dumps(version.artifact_hashes, ensure_ascii=False, sort_keys=True), version.accept_phase, version.label, version.created_at),
            )
            conn.commit()

    def get_resume_version(self, version_id: str) -> Optional[ResumeVersion]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM resume_versions WHERE version_id = ?", (version_id,)).fetchone()
        return self._row_to_resume_version(row) if row is not None else None

    def list_resume_versions(self, application_id: Optional[str] = None) -> List[ResumeVersion]:
        with self._get_connection() as conn:
            if application_id:
                rows = conn.execute("SELECT * FROM resume_versions WHERE application_id = ? ORDER BY created_at DESC", (application_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM resume_versions ORDER BY created_at DESC").fetchall()
        return [self._row_to_resume_version(row) for row in rows]

    @staticmethod
    def _row_to_outcome(row: sqlite3.Row) -> OutcomeRecord:
        d = dict(row)
        return OutcomeRecord.from_dict({
            "outcome_id": d["outcome_id"],
            "application_id": d["application_id"],
            "stage": d["stage"],
            "result": d["result"],
            "feedback_text": d["feedback_text"],
            "reflection_text": d["reflection_text"],
            "next_action_text": d["next_action_text"],
            "feedback_tags": json.loads(d["feedback_tags_json"] or "[]"),
            "occurred_at": d["occurred_at"],
        })

    @staticmethod
    def _row_to_resume_version(row: sqlite3.Row) -> ResumeVersion:
        data = dict(row)
        return ResumeVersion.from_dict({
            "version_id": data["version_id"],
            "application_id": data["application_id"],
            "proposal_id": data["proposal_id"],
            "profile_hash": data["profile_hash"],
            "jd_hash": data["jd_hash"],
            "theme": data["theme"],
            "output_paths": json.loads(data["output_paths_json"] or "{}"),
            "artifact_status": json.loads(data.get("artifact_status_json") or "{}"),
            "artifact_hashes": json.loads(data.get("artifact_hashes_json") or "{}"),
            "accept_phase": data.get("accept_phase") or "completed",
            "label": data["label"],
            "created_at": data["created_at"],
        })

    def delete(self, record_id: str) -> bool:
        """Deletes a record by ID."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM applications WHERE id = ?", (record_id,))
            conn.commit()
            return cur.rowcount > 0

    def _row_to_record(self, row: sqlite3.Row) -> ApplicationRecord:
        d = dict(row)
        history = json.loads(d.pop("status_history_json") or "[]")
        evidence = json.loads(d.pop("evidence_snapshot_json") or "{}")
        offer_raw = d.pop("offer_details_json")
        offer = json.loads(offer_raw) if offer_raw else None

        stat_str = d.pop("status")
        stat = AppStatus.from_string(stat_str)

        target_level = d.pop("target_level", "") or ""
        portal_url = d.pop("portal_url", "") or ""
        recruiter_contact = d.pop("recruiter_contact", "") or ""

        return ApplicationRecord(
            status=stat,
            status_history=history,
            evidence_snapshot=evidence,
            offer_details=offer,
            target_level=target_level,
            portal_url=portal_url,
            recruiter_contact=recruiter_contact,
            **d,
        )

    def export_json(self, file_path: Union[str, Path]) -> None:
        """Exports all records to a JSON file."""
        records = [r.to_dict() for r in self.list_all()]
        write_json_atomic(records, file_path)

    def import_json(self, file_path: Union[str, Path]) -> int:
        """Imports records from a JSON file, returning imported count."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        if isinstance(data, list):
            for item in data:
                rec = ApplicationRecord.from_dict(item)
                self.save(rec)
                count += 1
        return count


class ApplicationTracker:
    """
    Unified Application Lifecycle Tracker: manages local application pipelines,
    schedule collisions, deadlines, duplicate guards, and compensation comparisons.
    """

    def __init__(self, store: Optional[ApplicationStore] = None, db_path: Optional[Union[str, Path]] = None):
        if store is not None:
            self.store = store
        elif db_path is not None:
            self.store = ApplicationStore(db_path)
        else:
            self.store = ApplicationStore(":memory:")
        self._records_cache: List[ApplicationRecord] = []

    @property
    def records(self) -> List[ApplicationRecord]:
        """Provides backwards compatibility with direct self.records list consumption."""
        db_records = self.store.list_all()
        # Merge any in-memory only records with db records
        seen_ids = {r.id for r in db_records}
        combined = list(db_records)
        for r in self._records_cache:
            if r.id not in seen_ids:
                combined.append(r)
                seen_ids.add(r.id)
        return combined

    @records.setter
    def records(self, new_records: List[ApplicationRecord]) -> None:
        self._records_cache = list(new_records)
        for r in new_records:
            self.store.save(r)

    def add_record(self, record: ApplicationRecord, check_collision: bool = True) -> ApplicationRecord:
        """
        Adds or updates an application record with optional collision & cooldown verification.
        """
        if check_collision:
            self._verify_collision_guard(record)

        self.store.save(record)
        # Update cache
        self._records_cache = [r for r in self._records_cache if r.id != record.id]
        self._records_cache.append(record)
        return record

    def attach_evidence_snapshot(self, record_id: str, snapshot: Dict[str, Any]) -> bool:
        """Persist a career-review evidence snapshot through the configured store."""
        return self.store.attach_evidence_snapshot(record_id, snapshot)

    def _verify_collision_guard(self, record: ApplicationRecord) -> None:
        """Checks duplicate submission and cooling period constraints."""
        try:
            from core.duplicate_guard import (
                ApplicationRecord as GuardRecord,
                ApplicationChannel,
                DuplicateApplicationGuard,
            )
            # Map channel string to ApplicationChannel
            def _map_channel(ch_val: Any) -> ApplicationChannel:
                ch_map = {
                    "内推": ApplicationChannel.INTERNAL_REFERRAL,
                    "官网": ApplicationChannel.DIRECT_CAREERS_SITE,
                    "猎头": ApplicationChannel.HEADHUNTER,
                    "boss": ApplicationChannel.BOSS_ZHIPIN,
                    "拉勾": ApplicationChannel.LAGOU,
                    "猎聘": ApplicationChannel.LIEPIN,
                    "校招": ApplicationChannel.CAMPUS_TALK,
                }
                for k, v in ch_map.items():
                    if k in str(ch_val).lower():
                        return v
                return ApplicationChannel.OTHER

            def _map_status(stat_val: Any) -> str:
                return AppStatus.from_string(stat_val).to_guard_status()

            channel_enum = _map_channel(record.channel)

            guard_history = []
            for r in self.records:
                if r.id != record.id:
                    guard_history.append(
                        GuardRecord(
                            record_id=r.id,
                            company_name=r.target_name,
                            role_title=r.role_or_track,
                            channel=_map_channel(r.channel),
                            applied_date=r.applied_date or r.updated_at[:10],
                            status=_map_status(r.status),
                        )
                    )

            result = DuplicateApplicationGuard.check_application(
                new_company=record.target_name,
                new_role=record.role_or_track,
                new_channel=channel_enum,
                applied_date=record.applied_date or record.updated_at[:10],
                history=guard_history,
            )
            if result.has_collision:
                record.collision_risk = f"[{result.risk_level}] {'; '.join(result.reasons)}"
                record.cooling_days_left = result.cooldown_days_remaining
        except Exception:
            pass

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
                    "warning": f"【冲突预警】{day} 存在 {len(recs)} 场考核/笔试重叠，需提前协调时间！",
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
                            "urgency": "紧急" if delta <= 2 else "临近",
                        })
                except Exception:
                    pass
        return sorted(upcoming, key=lambda x: x["days_left"])

    def compare_offers(self) -> Dict[str, Any]:
        """
        Compares all received offers across total package, hourly wage, and working hours.
        Integrates core.offer_comparator for precision calculation.
        """
        from core.offer_comparator import MultiOfferComparator, OfferEntity

        offer_recs = [r for r in self.records if r.status == AppStatus.OFFER or r.offer_details]
        if not offer_recs:
            return {
                "total_offers": 0,
                "comparison": [],
                "best_hourly_offer": None,
                "best_total_offer": None,
                "summary": "当前投递管线中暂无已录入的 Offer 记录。",
            }

        comparator = MultiOfferComparator()
        compared = []
        incomplete = []
        for r in offer_recs:
            details = r.offer_details or {}
            base_raw = details.get("base_monthly", details.get("base_salary"))
            months_raw = details.get("months", details.get("salary_months"))
            missing = []
            if base_raw is None:
                missing.append("base_monthly")
            if months_raw is None:
                missing.append("months")
            if missing:
                incomplete.append({
                    "record_id": r.id,
                    "company": r.target_name,
                    "role": r.role_or_track,
                    "missing_fields": missing,
                    "details": details,
                })
                continue

            base_monthly = float(base_raw)
            months = float(months_raw)
            annual_stock = float(details.get("stock_annual", details.get("annual_stock", 0)))
            annual_bonus = float(details.get("bonus_annual", details.get("annual_bonus", 0)))
            weekly_hours = float(details.get("weekly_hours", 45))

            entity = OfferEntity(
                company_name=r.target_name,
                role_title=r.role_or_track,
                base_monthly_salary=base_monthly,
                salary_months=months,
                annual_bonus_expected=annual_bonus,
                equity_rsu_annual=annual_stock,
                weekly_work_hours=weekly_hours,
            )
            ev_metrics = comparator.evaluate_single_offer(entity)
            compared.append({
                "record_id": r.id,
                "company": r.target_name,
                "role": r.role_or_track,
                "nominal_annual": ev_metrics.annual_total_package,
                "effective_hourly_wage": ev_metrics.effective_hourly_rate,
                "annual_work_hours": ev_metrics.annual_work_hours,
                "details": details,
            })

        if not compared:
            return {
                "total_offers": len(offer_recs),
                "comparison": [],
                "incomplete": incomplete,
                "best_hourly_offer": None,
                "best_total_offer": None,
                "summary": "Offer 记录缺少可比较的基础薪资或发薪月数，请补齐后再比较。",
            }

        compared.sort(key=lambda x: x["effective_hourly_wage"], reverse=True)
        best_hourly = compared[0]
        best_total = max(compared, key=lambda x: x["nominal_annual"])

        return {
            "total_offers": len(offer_recs),
            "comparable_offers": len(compared),
            "comparison": compared,
            "incomplete": incomplete,
            "best_hourly_offer": best_hourly,
            "best_total_offer": best_total,
            "summary": (
                f"共比对 {len(compared)} 份 Offer。折算等效时薪最高为 {best_hourly['company']} "
                f"({best_hourly['effective_hourly_wage']} 元/时)；名义年薪总包最高为 {best_total['company']} "
                f"({best_total['nominal_annual']/10000:.1f} 万元)。"
            ),
        }

    def generate_board_markdown(self) -> str:
        """
        Renders a clean Markdown status board.
        """
        lines = [
            "# OfferGet 全局申请推进看板 (Application Tracker Board)",
            "",
            "| ID | 目标机构/高校 | 岗位/轨道 | 状态 | 关键考核时间 | 截止日 | 渠道 | 风险/状态说明 |",
            "|:---|:---|:---|:---:|:---:|:---:|:---:|:---|",
        ]
        for r in self.records:
            risk_info = r.collision_risk or r.notes or "正常推进"
            lines.append(
                f"| `{r.id}` | **{r.target_name}** | {r.role_or_track} | `{r.status.value if hasattr(r.status, 'value') else r.status}` | "
                f"{r.exam_or_interview_time or '—'} | {r.deadline or '—'} | {r.channel} | {risk_info} |"
            )
        return "\n".join(lines)
