"""Reversible mappings must preserve arbitrary synthetic input exactly."""

import json

import pytest

from core.anonymizer import PrivacyAnonymizer


@pytest.mark.parametrize("level", ["standard", "strict"])
def test_distinct_and_overlapping_project_urls_roundtrip(level):
    profile = {
        "candidate": {"name": "Synthetic Person", "github": "https://github.com/synthetic"},
        "projects": [
            {"name": "First Synthetic Project", "github": "https://github.com/synthetic/a"},
            {"name": "Second Synthetic Project", "github": "https://github.com/synthetic/ab"},
            {"name": "Third Synthetic Project", "github": "https://github.com/synthetic/a/issues"},
        ],
    }
    anonymizer = PrivacyAnonymizer()
    masked, reverse = anonymizer.anonymize(profile, level)
    assert len({item["github"] for item in masked["projects"]}) == 3
    assert anonymizer.deanonymize(masked, reverse) == profile
    assert anonymizer.anonymize(profile, level) == (masked, reverse)
    assert anonymizer.anonymize(dict(reversed(list(profile.items()))), level) == (masked, reverse)


@pytest.mark.parametrize("text", [
    "北京大学 and Peking University; 智谱AI and Zhipu AI; +86 18600008899 and +86 186-0000-8899",
    "Synthetic Source; existing Dr. Alex Chen; candidate.ai@example.com; https://github.com/candidate-ai",
    "alpha and beta and gamma",
    "alphaSuffix and beta",  # Adjacent text could form another readable alias.
])
def test_alias_collisions_and_replacement_chains_roundtrip(text):
    anonymizer = PrivacyAnonymizer({"alpha": "beta", "beta": "gamma", "gamma": "delta", "Synthetic Source": "Dr. Alex Chen"})
    masked, reverse = anonymizer.anonymize(text)
    assert anonymizer.deanonymize(masked, reverse) == text
    assert anonymizer.anonymize(text) == (masked, reverse)


def test_reverse_replacement_does_not_reprocess_restored_text():
    anonymizer = PrivacyAnonymizer()
    assert anonymizer.deanonymize("FIRST SECOND", {"FIRST": "SECOND", "SECOND": "original"}) == "SECOND original"


def test_alias_like_text_survives_saved_map(tmp_path):
    anonymizer = PrivacyAnonymizer({"secret": "alias", "other": "alias"})
    text = "secret other literal alias [OFFERGET_012345]"
    masked, reverse = anonymizer.anonymize(text)
    path = tmp_path / "private-map.json"
    anonymizer.save_map(reverse, path)
    assert anonymizer.deanonymize(masked, json.loads(path.read_text())) == text
    assert masked.count("literal alias") == 1


def test_empty_custom_entity_is_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        PrivacyAnonymizer({"": "empty"}).anonymize("hello")


@pytest.mark.parametrize("alias", ["__private", "alias_to_real"])
def test_custom_alias_cannot_shadow_reverse_map_metadata(alias):
    anonymizer = PrivacyAnonymizer({"Synthetic Secret": alias})
    masked, reverse = anonymizer.anonymize("Synthetic Secret", "standard")
    assert anonymizer.deanonymize(masked, reverse) == "Synthetic Secret"
    assert anonymizer.deanonymize(masked, {"alias_to_real": reverse}) == "Synthetic Secret"
