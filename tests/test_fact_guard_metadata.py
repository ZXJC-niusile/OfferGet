"""Synthetic adversarial and benign-change coverage for structured fact checks."""
import copy

import pytest

from core.fact_guard import FactVerificationGuard


@pytest.fixture
def profile():
    return {
        "candidate": {"name": "Synthetic Auditor", "school": "Fictional Zebra University", "degree": "BSc", "education_badges": ["GPA 3.8/4.0"]},
        "experience": [{"org": "Fictional Orion Works", "role": "Engineer", "time": "2020-2021", "bullets": ["Maintained 30+ services."]}],
        "projects": [{"name": "Synthetic Notes", "role": "Contributor", "time": "2022", "bullets": ["Wrote documentation."]}],
        "skills": ["Python", "PyTorch"],
    }


def test_original_metadata_replacement_repro_no_longer_passes(profile):
    tailored = copy.deepcopy(profile)
    tailored["candidate"].update(degree="PhD", school="Unattended School")
    tailored["experience"][0].update(org="Unrelated Employer", time="2010-2026")
    tailored["competencies"] = {"Programming": ["Rust", "Kubernetes"]}
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert result["passed"] is False
    assert result["score"] < 100
    assert result["verdict"] == "FACT_REVIEW_REQUIRED"
    unverified = [item for item in result["field_checks"] if item["status"] == "needs_verification"]
    assert {"PhD", "Unattended School", "Unrelated Employer", "2010-2026", "Rust", "Kubernetes"} <= {item["tailored_value"] for item in unverified}
    assert "Maintained 30+ services." in result["verified_bullets"]
    assert result["coverage"]["scope"] == "structured_profile"
    assert result["coverage"]["status"] == "needs_verification"


@pytest.mark.parametrize("section,key,value", [
    ("candidate", "school", "Unattended School"),
    ("candidate", "degree", "PhD"),
    ("candidate", "major", "Fictional Studies"),
    ("candidate", "certifications", ["Invented Certificate"]),
    ("experience", "org", "Unrelated Employer"),
    ("experience", "time", "2010-2026"),
    ("experience", "role", "Director"),
    ("projects", "name", "Unrelated Project"),
    ("projects", "role", "Owner"),
    ("projects", "time", "2010-2026"),
])
def test_metadata_only_changes_are_not_hidden_by_unchanged_bullets(profile, section, key, value):
    tailored = copy.deepcopy(profile)
    target = tailored[section] if section == "candidate" else tailored[section][0]
    target[key] = value
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert not result["passed"]
    assert result["score"] < 100
    assert result["coverage"]["unverified_fields"]
    assert any(check["tailored_source_path"].endswith(key if not isinstance(value, list) else f"{key}[0]") for check in result["field_checks"] if check["status"] == "needs_verification")


def test_unchanged_structured_profile_preserves_raw_skills_and_source_paths(profile):
    original = copy.deepcopy(profile)
    result = FactVerificationGuard(profile).verify_facts(profile)
    assert profile == original
    assert result["passed"]
    assert result["score"] == 100
    assert not result["coverage"]["unverified_fields"]
    assert result["coverage"]["status"] == "limited"
    assert "not independent" in result["coverage"]["limitation"]
    skills = [item for item in result["field_checks"] if item["field"].startswith("skills[")]
    assert {item["tailored_value"] for item in skills} == {"Python", "PyTorch"}
    assert {item["tailored_source_path"] for item in skills} == {"skills[0]", "skills[1]"}


def test_omissions_are_reported_without_accusing_fabrication(profile):
    tailored = {"candidate": {"name": "Synthetic Auditor"}, "skills": ["Python"]}
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert result["passed"]
    assert result["coverage"]["omitted_fields"]
    assert not result["coverage"]["unverified_fields"]
    assert any(item["change_type"] == "removed" and item["status"] == "omitted" for item in result["field_checks"])
    assert not result["drifts"]
    assert not result["unverified_claims"]


def test_structural_aliases_formatting_and_skill_grouping_match(profile):
    tailored = {
        "name": "  SYNTHETIC   Auditor ",
        "education": {"institution": "Fictional Zebra University", "education_level": "BSc", "education_badges": ["GPA 3.8/4.0"]},
        "internships": [{"organization": "Fictional Orion Works", "title": "Engineer", "period": "2020–2021", "bullets": ["Maintained 30+ services."]}],
        "campus_experience": [{"title": "Synthetic Notes", "role": "Contributor", "period": "2022", "bullets": ["Wrote documentation."]}],
        "competencies": {"Tools": ["torch", "python"]},
    }
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert result["passed"], result
    assert not result["coverage"]["unverified_fields"]
    assert result["summary"]["total_bullets_checked"] == 2


def test_nested_education_aliases_and_changed_gpa():
    baseline = {"candidate": {"education": [{"school": "Synthetic College", "degree": "BA", "gpa": 3.7}]}}
    same = {"education": [{"institution": "Synthetic College", "education_level": "BA", "gpa": 3.7}]}
    guard = FactVerificationGuard(baseline)
    assert guard.verify_facts(same)["passed"]
    same["education"][0]["gpa"] = 3.9
    result = guard.verify_facts(same)
    assert not result["passed"]
    assert result["coverage"]["unverified_fields"] == ["education[0].gpa"]


def test_unresolved_translation_needs_review_not_a_fabrication_label(profile):
    tailored = copy.deepcopy(profile)
    tailored["candidate"]["degree"] = "理学学士"
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert result["verdict"] == "FACT_REVIEW_REQUIRED"
    assert not result["drifts"]
    assert not result["role_inflations"]
    assert result["coverage"]["unverified_fields"] == ["education[0].degree"]


def test_contradictory_alias_is_not_silently_discarded(profile):
    tailored = copy.deepcopy(profile)
    tailored["candidate"]["institution"] = "Different University"
    tailored["experience"][0]["company"] = "Different Employer"
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert not result["passed"]
    values = [item["tailored_value"] for item in result["field_checks"] if item["status"] == "needs_verification"]
    assert "Different University" in values
    assert "Different Employer" in values


def test_new_skill_in_any_supported_container_requires_verification(profile):
    for container in ("skills", "competencies"):
        tailored = copy.deepcopy(profile)
        tailored[container] = {"Tools": ["Python", "Rust"]}
        result = FactVerificationGuard(profile).verify_facts(tailored)
        assert not result["passed"]
        assert 'skills["rust"]' in result["coverage"]["unverified_fields"]


def test_unique_record_reordering_is_not_a_fact_change(profile):
    profile["experience"].append({"org": "Second Synthetic Employer", "role": "Writer", "time": "2023", "bullets": ["Wrote documentation."]})
    tailored = copy.deepcopy(profile)
    tailored["experience"].reverse()
    assert FactVerificationGuard(profile).verify_facts(tailored)["passed"]


@pytest.mark.parametrize("tailored", [{}, {"projects": []}, {"experience": []}, {"candidate": {}}, {"theme": "classic-tech"}])
def test_empty_or_presentation_only_input_cannot_receive_perfect_pass(profile, tailored):
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert not result["passed"]
    assert result["score"] == 0
    assert result["verdict"] == "FACT_CHECK_INCOMPLETE"


def test_unrecognized_metadata_cannot_hide_outside_bullet_checks(profile):
    tailored = copy.deepcopy(profile)
    tailored["narrative"] = {"summary": "Awarded an unsupported doctorate"}
    tailored["candidate"]["description"] = "Unsupported distinction"
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert not result["passed"]
    assert {"narrative.summary", "candidate.description"} <= set(result["coverage"]["unverified_fields"])


def test_text_and_explicitly_scoped_input_disclose_bounded_checks(profile):
    guard = FactVerificationGuard(profile)
    result = guard.verify_facts("Maintained 30+ services.", target_scope="experience[0]")
    assert result["coverage"]["scope"] == "bullet_metrics_and_technology_only"
    assert result["coverage"]["status"] == "limited"
    assert guard.verify_facts("")["verdict"] == "FACT_CHECK_INCOMPLETE"


@pytest.mark.parametrize("education", [
    {"institution": "Synthetic School", "major": "History", "degree": "BA", "time": "2020 - 2024"},
    {"school": "Synthetic School", "degree": "BSc", "education_badges": ["GPA 3.8/4.0"]},
])
def test_shared_profile_normalizer_does_not_create_false_metadata_drift(education):
    from core.profile_adapter import normalize_candidate_profile
    baseline = {"name": "Synthetic", "education": education, "skills": ["Python"]}
    result = FactVerificationGuard(baseline).verify_facts(normalize_candidate_profile(baseline))
    assert result["passed"], result["field_checks"]
    assert not result["coverage"]["unverified_fields"]


def test_candidate_education_grid_and_normalized_badges_are_equivalent():
    from core.profile_adapter import normalize_candidate_profile
    baseline = {"candidate": {"name": "Synthetic", "education_grid": [["BSc", "Synthetic School"], ["GPA 3.8/4.0"]]}}
    result = FactVerificationGuard(baseline).verify_facts(normalize_candidate_profile(baseline))
    assert result["passed"], result["field_checks"]


def test_combined_major_does_not_authorize_a_changed_degree():
    baseline = {"candidate": {"name": "Synthetic", "major": "History", "degree": "BA"}}
    tailored = {"candidate": {"name": "Synthetic", "major": "History", "degree": "History PhD"}}
    result = FactVerificationGuard(baseline).verify_facts(tailored)
    assert not result["passed"]
    assert result["coverage"]["unverified_fields"] == ["education[0].degree"]
    assert next(check for check in result["field_checks"] if check["field"] == "education[0].degree")["tailored_value"] == "History PhD"


@pytest.mark.parametrize("baseline", [
    {"name": "Synthetic", "intent": "Writer"},
    {"name": "Synthetic", "target_role": "Writer"},
    {"candidate": {"name": "Synthetic", "title_zh": "撰稿人"}},
    {"candidate": {"name": "Synthetic", "title_zh": "撰稿人", "title_en": "Writer"}},
    {"name": "Synthetic", "papers": [{"title": "Synthetic Paper", "status": "preprint"}]},
    {"name": "Synthetic", "honors": ["Synthetic Award"]},
    {"name": "Synthetic", "exam_score": {"score": 300}},
    {"name": "Synthetic", "education": {"education_grid": [["BSc", "Synthetic School"]]}},
])
def test_supported_normalizer_aliases_remain_source_matched(baseline):
    from core.profile_adapter import normalize_candidate_profile
    normalized = normalize_candidate_profile(baseline)
    result = FactVerificationGuard(baseline).verify_facts(normalized)
    assert result["passed"], result["field_checks"]
    assert not result["coverage"]["unverified_fields"]


@pytest.mark.parametrize("container", ["candidate", "education"])
@pytest.mark.parametrize("alias", ["education_grid", "education_rows"])
def test_conflicting_education_display_aliases_do_not_bypass_verification(container, alias):
    baseline = {container: {"name": "Synthetic", "education_badges": ["BA, School A"], alias: [["BA, School A"]]}}
    tailored = copy.deepcopy(baseline)
    tailored[container][alias] = [["PhD, School B"]]
    result = FactVerificationGuard(baseline).verify_facts(tailored)
    assert not result["passed"]
    assert result["score"] < 100
    changed = [check for check in result["field_checks"] if check["status"] == "needs_verification"]
    assert any(check["tailored_value"] == "PhD, School B" for check in changed)
    assert any(alias in check["tailored_source_path"] for check in changed)


def test_grid_and_rows_disagreement_is_reported_without_badges():
    baseline = {"candidate": {"name": "Synthetic", "education_grid": [["BA, School A"]], "education_rows": [["BA, School A"]]}}
    tailored = copy.deepcopy(baseline)
    tailored["candidate"]["education_rows"] = [["PhD, School B"]]
    assert not FactVerificationGuard(baseline).verify_facts(tailored)["passed"]


def test_unhandled_experience_prose_is_compared_as_metadata(profile):
    tailored = copy.deepcopy(profile)
    tailored["experience"][0]["description"] = "Unverified medical director"
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert not result["passed"]
    assert any(field.endswith(".description") for field in result["coverage"]["unverified_fields"])


def test_english_project_claim_is_not_skipped(profile):
    tailored = copy.deepcopy(profile)
    tailored["projects"][0]["bullets"] = [{"claim_en": "Used Kubernetes to run 400 clusters."}]
    result = FactVerificationGuard(profile).verify_facts(tailored)
    assert not result["passed"]
    assert result["unverified_claims"]
    assert result["summary"]["total_bullets_checked"] == 2


@pytest.mark.parametrize("section,container", [("experience", "highlights"), ("experience", "bullets"), ("projects", "bullets")])
@pytest.mark.parametrize("key", ["text", "claim_zh", "claim_en"])
def test_every_supported_claim_text_field_reaches_heuristics(section, container, key):
    baseline = {"candidate": {"name": "Synthetic"}, section: [{"org" if section == "experience" else "name": "Synthetic Record", "role": "Writer", container: [{"text": "Wrote documentation.", "claim_zh": "撰写文档", "claim_en": "Wrote documentation."}]}]}
    tailored = copy.deepcopy(baseline)
    tailored[section][0][container][0][key] = "Built 500 GPUs."
    result = FactVerificationGuard(baseline).verify_facts(tailored)
    assert not result["passed"]
    assert result["score"] < 100
    assert result["summary"]["total_bullets_checked"] >= 2
    assert result["unverified_claims"] or result["drifts"]


@pytest.mark.parametrize("section,container", [("experience", "highlights"), ("experience", "bullets"), ("projects", "bullets")])
def test_unrecognized_claim_fields_are_not_silently_skipped(section, container):
    baseline = {"candidate": {"name": "Synthetic"}, section: [{"org" if section == "experience" else "name": "Synthetic Record", container: [{"text": "Wrote documentation."}]}]}
    tailored = copy.deepcopy(baseline)
    tailored[section][0][container][0]["unsupported_fact"] = "Unverified doctorate"
    result = FactVerificationGuard(baseline).verify_facts(tailored)
    assert not result["passed"]
    assert any(field.endswith(".unsupported_fact") for field in result["coverage"]["unverified_fields"])


def test_source_highlight_text_metric_is_indexed_and_checked():
    baseline = {"candidate": {"name": "Synthetic"}, "experience": [{"org": "Synthetic Org", "highlights": [{"text": "Maintained 30+ services."}]}]}
    result = FactVerificationGuard(baseline).verify_facts(baseline)
    assert result["passed"], result
    assert result["summary"]["total_bullets_checked"] == 1


@pytest.mark.parametrize("rows", [["BSc | School A", "GPA 3.8"], ["BSc\tSchool A", "GPA 3.8"], ["BSc  School A", "GPA 3.8"]])
def test_supported_string_education_rows_match_normalizer_without_losing_source(rows):
    from core.profile_adapter import normalize_candidate_profile
    baseline = {"candidate": {"name": "Synthetic", "education_rows": rows}}
    result = FactVerificationGuard(baseline).verify_facts(normalize_candidate_profile(baseline))
    assert result["passed"], result["field_checks"]
    check = next(item for item in result["field_checks"] if item["field"] == "education[0].education_badges[0]")
    assert check["baseline_value"] == rows[0]
    assert check["baseline_source_path"] == "candidate.education_rows[0]"


def test_conflicting_string_education_row_remains_unverified():
    baseline = {"candidate": {"name": "Synthetic", "education_rows": ["BSc | School A"], "education_badges": ["BSc", "School A"]}}
    tailored = copy.deepcopy(baseline)
    tailored["candidate"]["education_rows"] = ["PhD | School B"]
    assert not FactVerificationGuard(baseline).verify_facts(tailored)["passed"]
