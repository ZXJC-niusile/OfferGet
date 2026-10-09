"""Evidence-gated material proposals with explicit human confirmation.

The proposal is intentionally independent from persistence. Callers may store the
serialized object in a session, application record, or another repository.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from core.profile_adapter import ProfileContext, build_profile_context


class MaterialProposalStatus(str, Enum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONFLICTED = "conflicted"


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def profile_fingerprint(profile: Union[Dict[str, Any], ProfileContext]) -> str:
    ctx = ProfileContext.from_profile(profile)
    return _canonical_hash(ctx.normalized_profile)


def jd_fingerprint(jd_text: str) -> str:
    return hashlib.sha256((jd_text or "").strip().encode("utf-8")).hexdigest()


@dataclass
class MaterialProposal:
    proposal_id: str
    source_profile_hash: str
    source_jd_hash: str
    application_id: Optional[str] = None
    patches: List[Dict[str, Any]] = field(default_factory=list)
    status: MaterialProposalStatus = MaterialProposalStatus.DRAFT
    accepted_patch_ids: List[int] = field(default_factory=list)
    proposal_hash: str = ""
    conflict_reason: str = ""
    applied_phase: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            self.status = MaterialProposalStatus(self.status)
        if not self.proposal_hash:
            self.proposal_hash = self.compute_hash()

    def compute_hash(self) -> str:
        payload = {
            "proposal_id": self.proposal_id,
            "source_profile_hash": self.source_profile_hash,
            "source_jd_hash": self.source_jd_hash,
            "application_id": self.application_id,
            "patches": self.patches,
        }
        return _canonical_hash(payload)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["patches"] = copy.deepcopy(self.patches)
        data["applied_phase"] = self.applied_phase
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MaterialProposal":
        return cls(
            proposal_id=str(data.get("proposal_id", "")),
            source_profile_hash=str(data.get("source_profile_hash", "")),
            source_jd_hash=str(data.get("source_jd_hash", "")),
            application_id=data.get("application_id"),
            patches=copy.deepcopy(data.get("patches", [])),
            status=MaterialProposalStatus(data.get("status", MaterialProposalStatus.DRAFT.value)),
            accepted_patch_ids=list(data.get("accepted_patch_ids", [])),
            proposal_hash=str(data.get("proposal_hash", "")),
            conflict_reason=str(data.get("conflict_reason", "")),
            applied_phase=str(data.get("applied_phase", "")),
        )

    def check_sources(
        self,
        profile: Union[Dict[str, Any], ProfileContext],
        jd_text: str,
    ) -> tuple[bool, str]:
        current_profile = profile_fingerprint(profile)
        current_jd = jd_fingerprint(jd_text)
        if current_profile != self.source_profile_hash:
            return False, "source_profile_changed"
        if current_jd != self.source_jd_hash:
            return False, "source_jd_changed"
        return True, ""

    def accept(
        self,
        profile: Union[Dict[str, Any], ProfileContext],
        jd_text: str,
        patch_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        if self.status == MaterialProposalStatus.REJECTED:
            raise ValueError("rejected proposal cannot be accepted")

        current, reason = self.check_sources(profile, jd_text)
        if not current:
            if self.status != MaterialProposalStatus.ACCEPTED:
                self.status = MaterialProposalStatus.CONFLICTED
                self.conflict_reason = reason
            raise ValueError(f"proposal source changed: {reason}")

        if self.status == MaterialProposalStatus.ACCEPTED:
            # Re-accepting an already accepted proposal:
            # Must strictly preserve originally accepted patch selection
            if patch_ids is not None:
                if set(patch_ids) != set(self.accepted_patch_ids):
                    raise ValueError(
                        f"proposal is already accepted with patch_ids={self.accepted_patch_ids}, "
                        f"cannot alter approved selection to {patch_ids}"
                    )
            return [copy.deepcopy(self.patches[i]) for i in self.accepted_patch_ids]

        selected = list(range(len(self.patches))) if patch_ids is None else list(patch_ids)
        if any(i < 0 or i >= len(self.patches) for i in selected):
            raise ValueError("patch_ids contains an unknown patch index")
        self.accepted_patch_ids = selected
        self.status = MaterialProposalStatus.ACCEPTED
        return [copy.deepcopy(self.patches[i]) for i in selected]

    def reject(self) -> None:
        if self.status == MaterialProposalStatus.ACCEPTED:
            raise ValueError("accepted proposal cannot be rejected")
        self.status = MaterialProposalStatus.REJECTED


def apply_material_proposal(
    proposal: MaterialProposal,
    profile: Union[Dict[str, Any], ProfileContext],
    jd_text: str,
    patch_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Accept selected patches and return a new profile version.

    The source profile is never mutated. Only explicit experience/project bullet
    paths are accepted; an old or ambiguous path fails closed. Pre-validates
    all target paths atomically before committing the proposal's accepted status.
    """
    if proposal.status == MaterialProposalStatus.REJECTED:
        raise ValueError("rejected proposal cannot be accepted")

    current, reason = proposal.check_sources(profile, jd_text)
    if not current:
        if proposal.status != MaterialProposalStatus.ACCEPTED:
            proposal.status = MaterialProposalStatus.CONFLICTED
            proposal.conflict_reason = reason
        raise ValueError(f"proposal source changed: {reason}")

    if proposal.status == MaterialProposalStatus.ACCEPTED:
        if patch_ids is not None and set(patch_ids) != set(proposal.accepted_patch_ids):
            raise ValueError(
                f"proposal is already accepted with patch_ids={proposal.accepted_patch_ids}, "
                f"cannot alter approved selection to {patch_ids}"
            )
        selected = list(proposal.accepted_patch_ids)
    else:
        selected = list(range(len(proposal.patches))) if patch_ids is None else list(patch_ids)
        if any(i < 0 or i >= len(proposal.patches) for i in selected):
            raise ValueError("patch_ids contains an unknown patch index")

    result = copy.deepcopy(
        profile.normalized_profile if isinstance(profile, ProfileContext)
        else build_profile_context(profile).normalized_profile
    )
    # Apply in proposal order even when the user selects indexes out of order.
    patches_to_apply = [copy.deepcopy(proposal.patches[i]) for i in sorted(set(selected))]
    source_lengths = {
        (section, index): len(entry["bullets"])
        for section in ("experience", "projects")
        for index, entry in enumerate(result.get(section, []))
        if isinstance(entry, dict) and isinstance(entry.get("bullets"), list)
    }
    appended_slots = {}

    for patch in patches_to_apply:
        target = str(patch.get("target_path", ""))
        match = re.fullmatch(r"(experience|projects)\[(\d+)\]\.bullets\[(\d+)\]", target)
        if not match:
            raise ValueError(f"unsupported proposal target path: {target}")
        section, entry_idx, bullet_idx = match.group(1), int(match.group(2)), int(match.group(3))
        entries = result.get(section)
        if not isinstance(entries, list) or entry_idx >= len(entries):
            raise ValueError(f"proposal target is no longer available: {target}")
        bullets = entries[entry_idx].get("bullets") if isinstance(entries[entry_idx], dict) else None
        if not isinstance(bullets, list):
            # Preserve the public target-validation error contract.
            raise ValueError(f"proposal target is no longer available: {target}")  # noqa: TRY004
        expected_before = patch.get("before", "")
        source_length = source_lengths[(section, entry_idx)]
        slot = (section, entry_idx, bullet_idx)
        if bullet_idx >= source_length and slot not in appended_slots:
            # A later approved supplement may skip earlier, unapproved additions.
            # Still require a contiguous append plan, not an arbitrary target index.
            planned_slots = {
                str(item.get("target_path", "")) for item in proposal.patches
                if item.get("before") == ""
            }
            if expected_before or bullet_idx - source_length >= len(planned_slots) or any(
                f"{section}[{entry_idx}].bullets[{index}]" not in planned_slots
                for index in range(source_length, bullet_idx + 1)
            ):
                raise ValueError(f"proposal target is no longer available: {target}")
            appended_slots[slot] = len(bullets)
            bullets.append(patch.get("after", ""))
            continue
        bullet_idx = appended_slots.get(slot, bullet_idx)
        if slot in appended_slots and expected_before == "" and bullets[bullet_idx] == patch.get("after"):
            continue
        if bullets[bullet_idx] != expected_before:
            proposal.status = MaterialProposalStatus.CONFLICTED
            proposal.conflict_reason = f"target_changed:{target}"
            raise ValueError(f"proposal target changed: {target}")
        bullets[bullet_idx] = patch.get("after", "")

    # All patches applied and verified without error: now record accepted state
    proposal.accepted_patch_ids = selected
    proposal.status = MaterialProposalStatus.ACCEPTED
    proposal.applied_phase = "verified"
    return result


def create_material_proposal(
    review_result: Dict[str, Any],
    profile: Union[Dict[str, Any], ProfileContext],
    jd_text: str,
    proposal_id: str,
    application_id: Optional[str] = None,
) -> MaterialProposal:
    # Keep unchanged facts in the review/audit, not in a new approval queue.
    # Compare exact text only: whitespace and punctuation edits still need approval.
    # Stored proposals are restored unchanged, preserving hashes and patch indexes.
    patches = [
        copy.deepcopy(patch)
        for patch in review_result.get("tailored_profile", {}).get("applied_patches", [])
        if patch.get("validation_status") in {"applied", "already_applied", "pending_user_confirmation"}
        and not ("before" in patch and "after" in patch and patch["before"] == patch["after"])
    ]
    return MaterialProposal(
        proposal_id=proposal_id,
        source_profile_hash=profile_fingerprint(profile),
        source_jd_hash=jd_fingerprint(jd_text),
        application_id=application_id,
        patches=patches,
    )
