"""Dependency-free JSON interoperability with RenderCV's CV data model.

This adapter maps common factual fields into OfferGet's canonical profile. It
does not render files or validate against RenderCV's full Pydantic schema; any
unsupported sections are returned to the caller rather than silently discarded.
RenderCV YAML can be converted to JSON by its own CLI before using this module.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Union

from core.artifacts import write_json_atomic
from core.profile_adapter import normalize_candidate_profile, require_public_profile, retain_profile_visibility


@dataclass
class RenderCVImportResult:
    profile: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    unsupported_sections: Dict[str, Any] = field(default_factory=dict)


def import_rendercv(data: Union[Dict[str, Any], str, Path]) -> RenderCVImportResult:
    """Convert RenderCV root JSON/config into an OfferGet normalized profile."""
    payload = _load_mapping(data)
    cv = payload.get("cv", payload)
    if not isinstance(cv, dict):
        raise ValueError("RenderCV input must contain an object at 'cv'")

    candidate: Dict[str, Any] = {
        "name": _first_text(cv.get("name")),
        "title": _first_text(cv.get("headline")),
        "location": _first_text(cv.get("location")),
        "email": _first_text(cv.get("email")),
        "phone": _first_text(cv.get("phone")),
        "website": _first_text(cv.get("website")),
    }
    for network in cv.get("social_networks") or []:
        if not isinstance(network, dict):
            continue
        name = str(network.get("network", "")).strip().lower()
        value = _first_text(network.get("username")) or _first_text(network.get("url"))
        if name and value:
            candidate[name] = value

    sections = cv.get("sections") or {}
    if not isinstance(sections, dict):
        raise ValueError("RenderCV 'cv.sections' must be an object")

    experiences: List[Dict[str, Any]] = []
    projects: List[Dict[str, Any]] = []
    education: List[Dict[str, Any]] = []
    publications: List[Dict[str, Any]] = []
    competencies: Dict[str, List[str]] = {}
    unsupported: Dict[str, Any] = {}
    warnings: List[str] = []

    for section_name, section in sections.items():
        entries = section.get("entries", []) if isinstance(section, dict) else section
        if not isinstance(entries, list):
            unsupported[str(section_name)] = copy.deepcopy(section)
            warnings.append(f"section {section_name!r} has unsupported shape")
            continue
        kind = _section_kind(str(section_name))
        mapped_entries = []
        for entry in entries:
            if isinstance(entry, str):
                mapped_entries.append({"text": entry})
            elif isinstance(entry, dict):
                mapped_entries.append(entry)
            else:
                unsupported.setdefault(str(section_name), []).append(copy.deepcopy(entry))
                warnings.append(f"section {section_name!r} contains an unsupported entry")
                continue

        if kind == "experience":
            experiences.extend(mapped for entry in mapped_entries if (mapped := _map_experience(entry)))
        elif kind == "education":
            education.extend(mapped for entry in mapped_entries if (mapped := _map_education(entry)))
        elif kind == "projects":
            projects.extend(mapped for entry in mapped_entries if (mapped := _map_project(entry)))
        elif kind == "publications":
            publications.extend(_map_publication(entry) for entry in mapped_entries if _map_publication(entry))
        elif kind == "skills":
            for entry in mapped_entries:
                label = _first_text(entry.get("label"), entry.get("name"), entry.get("text"), default="Skills")
                values = entry.get("details", entry.get("highlights", entry.get("summary", [])))
                if isinstance(values, list):
                    items = [str(v).strip() for v in values if str(v).strip()]
                else:
                    items = [v.strip() for v in str(values or "").split(",") if v.strip()]
                if items:
                    competencies[label] = items
        else:
            unsupported[str(section_name)] = copy.deepcopy(section)
            warnings.append(f"section {section_name!r} was preserved as unsupported data")

    if education:
        primary_education = education[0]
        candidate.setdefault("school", primary_education.get("school", ""))
        candidate.setdefault("institution", primary_education.get("institution", ""))
        candidate.setdefault("major", primary_education.get("major", ""))
        candidate.setdefault("degree", primary_education.get("degree", ""))
        candidate.setdefault("edu_time", primary_education.get("period", ""))
        candidate["education_badges"] = primary_education.get("education_badges", [])
    profile = normalize_candidate_profile({
        "candidate": candidate,
        "experience": experiences,
        "projects": projects,
        "publications": publications,
        "competencies": competencies,
    })
    if unsupported:
        profile["rendercv_import_metadata"] = {"unsupported_sections": copy.deepcopy(unsupported)}
    return RenderCVImportResult(retain_profile_visibility(payload, profile), warnings, unsupported)


def export_rendercv(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Export supported OfferGet profile facts into a RenderCV JSON document."""
    require_public_profile(profile)
    normalized = normalize_candidate_profile(profile)
    candidate = normalized.get("candidate", {})
    cv: Dict[str, Any] = {
        "name": _first_text(candidate.get("name")) or None,
        "headline": _first_text(candidate.get("title"), candidate.get("title_zh"), candidate.get("title_en")) or None,
        "location": _first_text(candidate.get("location")) or None,
        "email": _first_text(candidate.get("email")) or None,
        "phone": _first_text(candidate.get("phone")) or None,
        "sections": {},
    }
    for field, network in (("github", "GitHub"), ("linkedin", "LinkedIn")):
        value = _first_text(candidate.get(field))
        if value:
            cv.setdefault("social_networks", []).append({"network": network, "username": value})

    sections: Dict[str, Any] = {}
    if normalized.get("experience"):
        sections["Experience"] = {"entries": [
            _export_complex_entry(
                {"company": _first_text(item.get("company"), item.get("org")),
                 "position": _first_text(item.get("role")),
                 "start_date": _first_text(item.get("start_date")) or None,
                 "end_date": _first_text(item.get("end_date")) or None,
                 "location": _first_text(item.get("location")) or None,
                 "highlights": _bullets(item)}
            ) for item in normalized["experience"]
        ]}
    if normalized.get("projects"):
        sections["Projects"] = {"entries": [
            _export_complex_entry({
                "name": _first_text(item.get("name"), item.get("title")),
                "start_date": _first_text(item.get("start_date")) or None,
                "end_date": _first_text(item.get("end_date")) or None,
                "highlights": _bullets(item),
            }) for item in normalized["projects"]
        ]}
    if any(candidate.get(key) for key in ("school", "institution", "major", "degree")):
        education_entry = _export_complex_entry({
            "institution": _first_text(candidate.get("institution"), candidate.get("school")),
            "area": _first_text(candidate.get("major")),
            "degree": _first_text(candidate.get("degree")) or None,
            "highlights": _as_text_list(candidate.get("education_badges", [])),
        })
        sections["Education"] = {"entries": [education_entry]}
    if normalized.get("publications"):
        sections["Publications"] = {"entries": [
            {key: value for key, value in {
                "title": _first_text(item.get("title")),
                "authors": _as_text_list(item.get("authors", item.get("author", []))),
                "summary": _first_text(item.get("summary"), item.get("abstract")) or None,
                "doi": _first_text(item.get("doi")) or None,
                "url": _first_text(item.get("url")) or None,
                "journal": _first_text(item.get("journal"), item.get("venue"), item.get("conference")) or None,
                "date": _first_text(item.get("date"), item.get("year")) or None,
            }.items() if value is not None and value != "" and value != []}
            for item in normalized["publications"] if isinstance(item, dict)
        ]}
    if normalized.get("competencies"):
        sections["Skills"] = {"entries": [
            {"label": str(label), "details": ", ".join(_as_text_list(values))}
            for label, values in normalized["competencies"].items() if _as_text_list(values)
        ]}
    cv["sections"] = sections
    return {"cv": cv}


def write_rendercv_json(profile: Dict[str, Any], path: Union[str, Path]) -> Path:
    """Write supported RenderCV JSON; parent directories are created as needed."""
    target_path = write_json_atomic(export_rendercv(profile), path)
    return Path(target_path)


def _load_mapping(data: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
    if isinstance(data, dict):
        return copy.deepcopy(data)
    path = Path(data)
    if path.suffix.lower() not in {".json", ".jsonc"}:
        raise ValueError("dependency-free RenderCV adapter accepts JSON files; convert YAML with RenderCV first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("RenderCV JSON root must be an object")
    return payload


def _section_kind(name: str) -> str:
    normalized = name.strip().lower().replace("_", " ").replace("-", " ")
    if any(word in normalized for word in ("experience", "employment", "work")):
        return "experience"
    if "education" in normalized or "学" in normalized:
        return "education"
    if any(word in normalized for word in ("project", "科研", "项目")):
        return "projects"
    if any(word in normalized for word in ("publication", "paper", "发表", "论文")):
        return "publications"
    if any(word in normalized for word in ("skill", "competenc", "技能")):
        return "skills"
    return "unsupported"


def _map_experience(entry: Dict[str, Any]) -> Dict[str, Any]:
    org = _first_text(entry.get("company"))
    role = _first_text(entry.get("position"), entry.get("role"))
    bullets = _as_text_list(entry.get("highlights"))
    summary = _first_text(entry.get("summary"))
    if summary:
        bullets.insert(0, summary)
    if not (org or role or bullets):
        return {}
    return {
        "company": org,
        "role": role,
        "period": _date_range(entry),
        "start_date": _first_text(entry.get("start_date")) or None,
        "end_date": _first_text(entry.get("end_date")) or None,
        "location": _first_text(entry.get("location")),
        "bullets": bullets,
    }


def _map_education(entry: Dict[str, Any]) -> Dict[str, Any]:
    school = _first_text(entry.get("institution"))
    major = _first_text(entry.get("area"), entry.get("major"))
    degree = _first_text(entry.get("degree"))
    if not (school or major or degree):
        return {}
    return {
        "school": school,
        "institution": school,
        "major": major,
        "degree": degree,
        "period": _date_range(entry),
        "start_date": _first_text(entry.get("start_date")) or None,
        "end_date": _first_text(entry.get("end_date")) or None,
        "education_badges": _as_text_list(entry.get("highlights")),
    }


def _map_project(entry: Dict[str, Any]) -> Dict[str, Any]:
    name = _first_text(entry.get("name"), entry.get("title"))
    bullets = _as_text_list(entry.get("highlights"))
    summary = _first_text(entry.get("summary"))
    if summary:
        bullets.insert(0, summary)
    if not (name or bullets):
        return {}
    return {
        "name": name,
        "role": _first_text(entry.get("role")),
        "period": _date_range(entry),
        "start_date": _first_text(entry.get("start_date")) or None,
        "end_date": _first_text(entry.get("end_date")) or None,
        "bullets": bullets,
    }


def _map_publication(entry: Dict[str, Any]) -> Dict[str, Any]:
    mapped = {key: copy.deepcopy(entry[key]) for key in ("title", "authors", "summary", "doi", "url", "journal") if entry.get(key) is not None}
    if entry.get("date") is not None:
        mapped["date"] = str(entry["date"])
    return mapped


def _export_complex_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in entry.items() if value is not None and value != "" and value != []}


def _date_range(entry: Dict[str, Any]) -> str:
    start = _first_text(entry.get("start_date"), entry.get("date"))
    end = _first_text(entry.get("end_date"))
    if start and end:
        return f"{start} - {end}"
    return start or end


def _bullets(item: Dict[str, Any]) -> List[str]:
    return _as_text_list(item.get("bullets", item.get("highlights", [])))


def _as_text_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        if isinstance(value, list):
            value = value[0] if value else ""
        if value is not None and str(value).strip():
            return str(value).strip()
    return default
