"""Static packaging/recipe checks, not model activation or quality evaluations."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_skill_metadata_and_entrypoint_budget():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    assert re.search(r"^name: offerget$", frontmatter, re.MULTILINE)
    assert re.search(r"^description: .+", frontmatter, re.MULTILINE)
    assert len(text.encode("utf-8")) < 7000
    assert len(text.splitlines()) < 120


@pytest.mark.parametrize("path", ["SKILL.md", "references/task-workflows.md", "references/skill-design.md"])
def test_skill_local_reference_links_resolve(path):
    document = ROOT / path
    for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
        if "://" not in link and not link.startswith("#"):
            assert (document.parent / link.split("#", 1)[0]).is_file(), link


def test_readme_has_no_machine_specific_file_links():
    assert "file:///" not in (ROOT / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("command", [
    ["resume", "build"], ["profile", "parse"], ["review"],
    ["proposal", "show"], ["proposal", "accept"], ["diff", "audit"],
])
def test_documented_recipe_command_help(command, monkeypatch, capsys):
    import cli
    # Root CLI startup is covered by a real subprocess smoke test. Each recipe
    # still traverses the real entrypoint/parser without another interpreter.
    monkeypatch.setattr(sys, "argv", ["offerget", *command, "--help"])
    with pytest.raises(SystemExit) as stopped:
        cli.main()
    assert stopped.value.code == 0
    assert "usage:" in capsys.readouterr().out.lower()


def test_visibility_boundary_remains_in_router_and_export_recipe():
    router = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    workflow = (ROOT / "references/task-workflows.md").read_text(encoding="utf-8")
    for text in (router, workflow):
        assert "reference-only" in text
        assert "on-request" in text
        assert "variant-specific" in text
        assert "reject" in text
    assert "Disclosure preflight before every export" in workflow
    assert "separate disclosure-safe profile" in workflow
    assert "wildcard tags keep all items" in workflow
    assert "repeat the disclosure preflight" in workflow
