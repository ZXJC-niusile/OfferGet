"""Version-bound JSON snapshots of JD decoding and matching for review resumes."""

from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

from core.fingerprints import content_fingerprint
from core.jd_compat import to_canonical
from core.jd_analyst.models import GapItem, GapState, MatcherResult


@lru_cache(maxsize=1)
def _engine_fingerprint():
    # Include the domain implementation so an upgrade never reuses old rules.
    root = Path(__file__).resolve().parent
    return content_fingerprint({str(p.relative_to(root)): content_fingerprint(p.read_bytes())
                                for p in sorted(root.rglob("*.py"))})


def analysis_key(jd_text, raw_profile):
    return content_fingerprint({"engine": _engine_fingerprint(),
                                "jd": jd_text, "profile": raw_profile})


def save_analysis(key, decoded_jd, matcher_result):
    payload = {"decoded_jd": asdict(decoded_jd), "matcher_result": asdict(matcher_result)}
    return {"schema_version": 1, "key": key, "payload": payload,
            "digest": content_fingerprint(payload)}


def load_analysis(snapshot, key):
    """Ignore obsolete or damaged caches; session/answer checks remain separate."""
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1 or snapshot.get("key") != key:
        return None
    payload = snapshot.get("payload")
    if not isinstance(payload, dict) or snapshot.get("digest") != content_fingerprint(payload):
        return None
    try:
        decoded = to_canonical(payload["decoded_jd"])
        values = dict(payload["matcher_result"])
        values["gap_matrix"] = [GapItem(**{**gap, "state": GapState(gap["state"])})
                                for gap in values["gap_matrix"]]
        return decoded, MatcherResult(**values)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
