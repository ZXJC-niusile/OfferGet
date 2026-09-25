"""Deterministic comparisons for application-linked resume version metadata."""

from __future__ import annotations

from typing import Any, Dict

from core.application_tracker import ResumeVersion


def compare_resume_versions(before: ResumeVersion, after: ResumeVersion) -> Dict[str, Any]:
    """Compare metadata only; explicitly state that content diff is unavailable."""
    if not isinstance(before, ResumeVersion) or not isinstance(after, ResumeVersion):
        raise TypeError("before and after must be ResumeVersion instances")
    changed = {}
    for field in ("application_id", "proposal_id", "profile_hash", "jd_hash", "theme", "label"):
        old = getattr(before, field)
        new = getattr(after, field)
        if old != new:
            changed[field] = {"before": old, "after": new}
    old_outputs = dict(before.output_paths)
    new_outputs = dict(after.output_paths)
    added = sorted(set(new_outputs) - set(old_outputs))
    removed = sorted(set(old_outputs) - set(new_outputs))
    changed_outputs = sorted(key for key in set(old_outputs) & set(new_outputs) if old_outputs[key] != new_outputs[key])
    return {
        "before_version_id": before.version_id,
        "after_version_id": after.version_id,
        "changed_metadata": changed,
        "outputs": {
            "added": added,
            "removed": removed,
            "changed": changed_outputs,
        },
        "profile_content_changed": before.profile_hash != after.profile_hash,
        "jd_content_changed": before.jd_hash != after.jd_hash,
        "content_diff_available": False,
    }
