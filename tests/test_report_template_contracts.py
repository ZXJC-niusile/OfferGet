"""Preserve report rendering while retiring the unused illustrative mockup."""

from pathlib import Path

import pytest

from core import report_generator as reports
from core.paths import get_template_path


def _render(tmp_path, template_path=None):
    output = reports.generate_report({}, {}, template_path=template_path,
                                     output_path=tmp_path / "report.html")
    return Path(output).read_text(encoding="utf-8")


def test_default_and_legacy_selectors_keep_identical_evidence_aware_output(tmp_path):
    default = _render(tmp_path)
    assert _render(tmp_path, "") == default
    assert _render(tmp_path, reports.get_canonical_default_template_path()) == default
    assert "legacy report resource" not in default.lower()
    assert "Evidence Ledger SSOT Verified" not in default
    assert "1,024 H800 GPUs" not in default
    assert "38M RMB" not in default


def test_legacy_path_is_a_renderer_alias_even_if_resource_is_edited(monkeypatch, tmp_path):
    resource = tmp_path / "templates" / "offer_strategy.html"
    resource.parent.mkdir()
    resource.write_text("<!DOCTYPE html><html><body>LEGACY_SENTINEL</body></html>", encoding="utf-8")
    monkeypatch.setattr(reports, "PROJECT_ROOT", tmp_path)
    assert reports.is_default_template(resource)
    assert "LEGACY_SENTINEL" not in _render(tmp_path, resource)


def test_external_basename_collision_is_rendered_with_escaped_input(tmp_path):
    custom = tmp_path / "offer_strategy.html"
    custom.write_text("<!DOCTYPE html><html><body>CUSTOM_SENTINEL {{COMPANY}} {{MATCH_SCORE_NUM}}</body></html>", encoding="utf-8")
    assert not reports.is_default_template(custom)
    output = reports.generate_report({"metadata": {"company": "A&B <Company>"}},
                                     {"overall_match_score": 0}, template_path=custom,
                                     output_path=tmp_path / "out.html")
    assert "CUSTOM_SENTINEL A&amp;B &lt;Company&gt; 0" in Path(output).read_text(encoding="utf-8")


def test_missing_explicit_path_does_not_fall_back(tmp_path):
    with pytest.raises(FileNotFoundError):
        _render(tmp_path, tmp_path / "missing.html")
    assert not (tmp_path / "report.html").exists()


def test_legacy_resource_helpers_and_notice_remain_available():
    resource = reports.get_canonical_default_template_path()
    assert resource == reports.resolve_report_template() == get_template_path()
    assert reports._is_default_template(resource)
    notice = reports.read_default_template_content()
    assert notice == resource.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in notice
    assert "compatibility notice" in notice
    assert "OfferStrategyReporter" in notice
    assert "docs/REPORT_TEMPLATES.md" in notice
    assert "{{" not in notice
    assert "Evidence Ledger SSOT Verified" not in notice
    assert "1,024 H800 GPUs" not in notice
    assert "38M RMB" not in notice


def test_selftest_selects_active_renderer_without_legacy_resource(monkeypatch, tmp_path, capsys):
    from presentation.commands import selftest_cmd
    from services.report_service import ReportService

    original = ReportService.generate_offer_strategy_report
    selected = []

    def capture(self, *args, **kwargs):
        selected.append(kwargs.get("template_path"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ReportService, "generate_offer_strategy_report", capture)
    selftest_cmd._run_smoke_checks(tmp_path)
    assert selected == [None]
    assert "CORE SMOKE CHECKS PASSED" in capsys.readouterr().out
