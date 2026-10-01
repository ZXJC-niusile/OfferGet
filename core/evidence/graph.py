"""
OfferGet Evidence Graph State Machine (core/evidence/graph.py)
==============================================================
OfferGet native evidence graph state machine (ADR-011):
1. Finite state machine governing atomic resume claim lifecycles:
   DRAFT -> VERIFIED -> GROUNDED -> USED_IN_RESUME -> INTERVIEW_DEFENDED (or INVALIDATED)
2. Immutable audit trails with state progression history.
3. Strict application gate: any claim used in resume must be at least GROUNDED
   and verified before candidate application can be marked READY_TO_APPLY.
4. Exportable immutable evidence snapshots for persistent tracking.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class EvidenceNodeState(str, Enum):
    """Lifecycle states of an evidence claim in the Evidence Graph."""
    DRAFT = "draft"                         # 初始草稿/自述，未核实
    VERIFIED = "verified"                   # 经真实性/抗夸大网关核对无虚构
    GROUNDED = "grounded"                   # 经历级作用域锚定 (有明确公司/项目/角色上下文)
    USED_IN_RESUME = "used_in_resume"       # 选入简历子弹点排版
    INTERVIEW_DEFENDED = "interview_defended" # 答辩模拟追问验证通过
    INVALIDATED = "invalidated"             # 证伪/存疑废弃，不可使用

    def __str__(self) -> str:
        return str(self.value)


# Valid linear forward transitions
_VALID_TRANSITIONS: Dict[EvidenceNodeState, Set[EvidenceNodeState]] = {
    EvidenceNodeState.DRAFT: {
        EvidenceNodeState.VERIFIED,
        EvidenceNodeState.INVALIDATED,
    },
    EvidenceNodeState.VERIFIED: {
        EvidenceNodeState.GROUNDED,
        EvidenceNodeState.INVALIDATED,
    },
    EvidenceNodeState.GROUNDED: {
        EvidenceNodeState.USED_IN_RESUME,
        EvidenceNodeState.INVALIDATED,
    },
    EvidenceNodeState.USED_IN_RESUME: {
        EvidenceNodeState.INTERVIEW_DEFENDED,
        EvidenceNodeState.INVALIDATED,
    },
    EvidenceNodeState.INTERVIEW_DEFENDED: {
        EvidenceNodeState.INVALIDATED,
    },
    EvidenceNodeState.INVALIDATED: set(),
}


@dataclass
class EvidenceNode:
    """A tracked proposition or bullet point within the Evidence Graph."""
    claim_id: str
    text: str
    state: EvidenceNodeState = EvidenceNodeState.DRAFT
    scope: str = ""                         # e.g. "未来科技 / 算法实习生" or "开源项目 / 负责人"
    source_ids: List[str] = field(default_factory=list)  # e.g. ["SRC-001", "GITHUB-REPO"]
    defended_rounds: int = 0               # Number of adversarial defense rounds passed
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def advance(self, to_state: Union[EvidenceNodeState, str], note: str = "") -> None:
        """Transitions this node to a new state enforcing monotonic unidirectional progression."""
        target = EvidenceNodeState(to_state) if isinstance(to_state, str) else to_state
        if target == self.state:
            return

        allowed = _VALID_TRANSITIONS.get(self.state, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid evidence state transition: cannot advance from '{self.state}' to '{target}' "
                f"for claim '{self.claim_id}'"
            )

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        self.history.append({
            "from_state": self.state.value,
            "to_state": target.value,
            "timestamp": now,
            "note": note,
        })
        self.state = target

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "state": self.state.value,
            "scope": self.scope,
            "source_ids": list(self.source_ids),
            "defended_rounds": self.defended_rounds,
            "history": copy.deepcopy(self.history),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> EvidenceNode:
        return cls(
            claim_id=str(d.get("claim_id", "")),
            text=str(d.get("text", "")),
            state=EvidenceNodeState(d.get("state", EvidenceNodeState.DRAFT.value)),
            scope=str(d.get("scope", "")),
            source_ids=list(d.get("source_ids", [])),
            defended_rounds=int(d.get("defended_rounds", 0)),
            history=list(d.get("history", [])),
            created_at=str(d.get("created_at", "")),
        )


class EvidenceGraph:
    """
    Evidence Graph coordinating verifiable fact validation, scoped grounding,
    and interview defense progression.
    """

    def __init__(self, nodes: Optional[List[EvidenceNode]] = None):
        self._nodes: Dict[str, EvidenceNode] = {}
        if nodes:
            for n in nodes:
                if not n.claim_id:
                    raise ValueError("EvidenceNode claim_id must not be empty")
                if n.claim_id in self._nodes:
                    raise ValueError(f"Duplicate evidence claim_id: '{n.claim_id}'")
                self._nodes[n.claim_id] = copy.deepcopy(n)

    @classmethod
    def from_profile_context(cls, profile_context: Any) -> "EvidenceGraph":
        """Build an evidence graph from the shared ProfileContext claim index.

        Claims carrying explicit verified metrics become VERIFIED. Experience and
        project claims with a declared role scope are then GROUNDED. Other claims
        remain DRAFT until a caller supplies stronger evidence.
        """
        context = profile_context
        if not hasattr(context, "claims"):
            from core.profile_adapter import build_profile_context

            context = build_profile_context(profile_context)

        graph = cls()
        grouped: Dict[str, Dict[str, Any]] = {}
        for claim in context.claims:
            claim_id = str(claim.claim_id or claim.source_path)
            if not claim_id:
                continue
            item = grouped.setdefault(
                claim_id,
                {
                    "text": claim.text,
                    "scope": claim.role_scope.strip(),
                    "source_ids": [],
                    "verified": False,
                },
            )
            if claim.text and len(claim.text) > len(item["text"]):
                item["text"] = claim.text
            if claim.role_scope and not item["scope"]:
                item["scope"] = claim.role_scope.strip()
            if claim.source_path not in item["source_ids"]:
                item["source_ids"].append(claim.source_path)
            item["verified"] = item["verified"] or claim.verification == "verified"

        for claim_id, item in grouped.items():
            graph.add_claim(
                item["text"],
                claim_id=claim_id,
                scope=item["scope"],
                source_ids=item["source_ids"],
            )
            if item["verified"]:
                graph.verify_claim(claim_id, note="ProfileEvidenceIndex verified_metrics")
                if item["scope"]:
                    graph.ground_claim(claim_id, item["scope"], note="ProfileEvidenceIndex role scope")
        return graph

    @property
    def nodes(self) -> Dict[str, EvidenceNode]:
        return {k: copy.deepcopy(v) for k, v in self._nodes.items()}

    def add_claim(
        self,
        text: str,
        claim_id: Optional[str] = None,
        state: EvidenceNodeState = EvidenceNodeState.DRAFT,
        scope: str = "",
        source_ids: Optional[List[str]] = None,
    ) -> EvidenceNode:
        """Adds a new claim node to the graph."""
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Evidence claim text must not be empty")
        if not claim_id:
            h = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:8]
            claim_id = f"CLM-{h}"
        if state != EvidenceNodeState.DRAFT:
            raise ValueError("New evidence claims must start in DRAFT state")
        if claim_id in self._nodes:
            raise ValueError(f"Claim '{claim_id}' already exists in EvidenceGraph")

        node = EvidenceNode(
            claim_id=claim_id,
            text=clean_text,
            state=state,
            scope=scope.strip(),
            source_ids=list(source_ids) if source_ids else [],
        )
        self._nodes[claim_id] = node
        return copy.deepcopy(node)

    def get_node(self, claim_id: str) -> Optional[EvidenceNode]:
        node = self._nodes.get(claim_id)
        return copy.deepcopy(node) if node is not None else None

    def verify_claim(self, claim_id: str, source_ids: Optional[List[str]] = None, note: str = "") -> EvidenceNode:
        """Advances a claim from DRAFT to VERIFIED."""
        node = self._nodes.get(claim_id)
        if not node:
            raise KeyError(f"Claim '{claim_id}' not found in EvidenceGraph")
        if node.state != EvidenceNodeState.DRAFT:
            raise ValueError(f"Claim '{claim_id}' is not in DRAFT state")
        if source_ids:
            for sid in source_ids:
                if sid not in node.source_ids:
                    node.source_ids.append(sid)
        node.advance(EvidenceNodeState.VERIFIED, note=note or "Verified by factual evidence")
        return copy.deepcopy(node)

    def ground_claim(self, claim_id: str, scope: str, note: str = "") -> EvidenceNode:
        """Grounds a claim to a concrete experience/project scope."""
        node = self._nodes.get(claim_id)
        if not node:
            raise KeyError(f"Claim '{claim_id}' not found in EvidenceGraph")
        if not scope.strip():
            raise ValueError(f"Cannot ground claim '{claim_id}' without an explicit scope")
        if node.state != EvidenceNodeState.VERIFIED:
            raise ValueError(f"Claim '{claim_id}' must be VERIFIED before grounding")
        node.advance(EvidenceNodeState.GROUNDED, note=note or f"Grounded in scope '{scope}'")
        node.scope = scope.strip()
        return copy.deepcopy(node)

    def use_in_resume(self, claim_id: str, note: str = "") -> EvidenceNode:
        """Marks a grounded claim as selected and formatted for the final resume."""
        node = self._nodes.get(claim_id)
        if not node:
            raise KeyError(f"Claim '{claim_id}' not found in EvidenceGraph")
        node.advance(EvidenceNodeState.USED_IN_RESUME, note=note or "Selected for resume bullet point")
        return copy.deepcopy(node)

    def mark_used_for_resume(self, claim_ids: List[str]) -> Tuple[List[str], Dict[str, str]]:
        """Promote grounded claims to USED_IN_RESUME and report rejected claims."""
        accepted: List[str] = []
        rejected: Dict[str, str] = {}
        for claim_id in dict.fromkeys(claim_ids):
            node = self._nodes.get(claim_id)
            if node is None:
                rejected[claim_id] = "claim_not_found"
            elif node.state in {EvidenceNodeState.USED_IN_RESUME, EvidenceNodeState.INTERVIEW_DEFENDED}:
                accepted.append(claim_id)
            elif node.state != EvidenceNodeState.GROUNDED:
                rejected[claim_id] = f"state_{node.state.value}"
            else:
                self.use_in_resume(claim_id)
                accepted.append(claim_id)
        return accepted, rejected

    def defend_claim(self, claim_id: str, rounds: int = 1, note: str = "") -> EvidenceNode:
        """Marks a claim as successfully defended in mock interview / defense simulation."""
        try:
            round_count = int(rounds)
        except (TypeError, ValueError) as exc:
            raise ValueError("Defense rounds must be a positive integer") from exc
        if round_count < 1:
            raise ValueError("Defense rounds must be a positive integer")
        node = self._nodes.get(claim_id)
        if not node:
            raise KeyError(f"Claim '{claim_id}' not found in EvidenceGraph")
        if node.state != EvidenceNodeState.USED_IN_RESUME:
            raise ValueError(f"Claim '{claim_id}' must be USED_IN_RESUME before defense")
        node.advance(
            EvidenceNodeState.INTERVIEW_DEFENDED,
            note=note or f"Passed {round_count} adversarial defense round(s)",
        )
        node.defended_rounds += round_count
        return copy.deepcopy(node)

    def invalidate_claim(self, claim_id: str, reason: str = "") -> EvidenceNode:
        """Marks a claim as invalidated/falsified so it cannot be used in application."""
        node = self._nodes.get(claim_id)
        if not node:
            raise KeyError(f"Claim '{claim_id}' not found in EvidenceGraph")
        node.advance(EvidenceNodeState.INVALIDATED, note=reason or "Claim invalidated during audit")
        return copy.deepcopy(node)

    def can_apply(self, claim_ids: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
        """
        Determines whether the current set of resume claims meets the truth threshold.
        Returns: (is_ready, list_of_blocking_reasons)
        """
        blocking_reasons: List[str] = []
        selected = set(claim_ids) if claim_ids is not None else None
        selected_nodes = [
            n for n in self._nodes.values()
            if selected is None or n.claim_id in selected
        ]
        active_nodes = [
            n for n in selected_nodes
            if n.state != EvidenceNodeState.INVALIDATED
        ]
        used_nodes = [n for n in active_nodes if n.state in {EvidenceNodeState.USED_IN_RESUME, EvidenceNodeState.INTERVIEW_DEFENDED}]

        if not used_nodes:
            blocking_reasons.append("没有经过核验与锚定的有效经历主张，且没有选入简历的主张")

        if selected is not None:
            for claim_id in sorted(selected):
                if claim_id not in self._nodes:
                    blocking_reasons.append(f"主张 [{claim_id}] 不存在于 EvidenceGraph")

        # Every non-invalidated claim must be grounded before application.
        for n in selected_nodes:
            if n.state == EvidenceNodeState.INVALIDATED:
                blocking_reasons.append(f"主张 [{n.claim_id}] 已被判定存疑废弃: {n.text[:30]}")
            elif n.state == EvidenceNodeState.DRAFT:
                blocking_reasons.append(f"主张 [{n.claim_id}] 仍处于未核实草稿状态: {n.text[:30]}")
            elif n.state == EvidenceNodeState.VERIFIED:
                blocking_reasons.append(f"主张 [{n.claim_id}] 尚未完成经历级锚定: {n.text[:30]}")
            elif not n.scope:
                blocking_reasons.append(f"主张 [{n.claim_id}] 缺少经历级作用域: {n.text[:30]}")

        is_ready = len(blocking_reasons) == 0
        return is_ready, blocking_reasons

    def get_readiness_report(self, claim_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Returns comprehensive readiness statistics and verdict."""
        counts = {s.value: 0 for s in EvidenceNodeState}
        for n in self._nodes.values():
            counts[n.state.value] += 1

        is_ready, blockers = self.can_apply(claim_ids=claim_ids)
        verdict = "READY_TO_APPLY" if is_ready else ("UNVERIFIED_BLOCK" if counts[EvidenceNodeState.INVALIDATED.value] > 0 else "DEFENSE_PENDING")

        return {
            "total_claims": len(self._nodes),
            "state_counts": counts,
            "verdict": verdict,
            "is_ready_to_apply": is_ready,
            "blockers": blockers,
            "selected_claim_ids": list(claim_ids) if claim_ids is not None else None,
        }

    def audit_snapshot(self, claim_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Creates an immutable, verifiable audit snapshot suitable for embedding
        into an ApplicationRecord or persistent telemetry.
        """
        nodes_list = [n.to_dict() for n in sorted(self._nodes.values(), key=lambda x: x.claim_id)]
        content_hash = hashlib.sha256(json.dumps(nodes_list, sort_keys=True).encode("utf-8")).hexdigest()

        return {
            "snapshot_type": "evidence_graph_audit",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "graph_hash": content_hash,
            "total_nodes": len(nodes_list),
            "verified_count": sum(1 for n in self._nodes.values() if n.state in {EvidenceNodeState.VERIFIED, EvidenceNodeState.GROUNDED, EvidenceNodeState.USED_IN_RESUME, EvidenceNodeState.INTERVIEW_DEFENDED}),
            "readiness": self.get_readiness_report(claim_ids=claim_ids),
            "nodes": nodes_list,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> EvidenceGraph:
        nodes = [EvidenceNode.from_dict(item) for item in d.get("nodes", [])]
        return cls(nodes)
