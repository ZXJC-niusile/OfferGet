"""Regressions for the concrete failures found during the project audit."""
from unittest.mock import patch

import pytest

from core.browser_renderer import BrowserRenderer, RenderResult
from core.security_gate import validate_output_security


@pytest.mark.parametrize("handler", [
    'onerror="this.style.display=1;nextElementSibling;alert(1)"',
    'ONERROR="this.style.display=1;nextElementSibling;fetch(\'https://example.test\')"',
    'onerror="if (1 > 0) alert(1)"',
    'onerror="&#97;lert(1)"',
    'onerror=alert(1)',
    'onerror="" onerror="alert(1)"',
])
def test_photo_fallback_cannot_whitelist_script(handler):
    assert validate_output_security(f'<img src="invalid" {handler}>')
    assert not validate_output_security('&lt;img onerror="alert(1)"&gt;')


@pytest.mark.parametrize("result", [
    RenderResult(False, 0, "browser failed"),
    RenderResult(True, 0, "invalid count"),
    RenderResult(True, True, "boolean count"),
])
def test_overflow_measurement_does_not_turn_failure_into_zero_overflow(tmp_path, result):
    renderer = BrowserRenderer(browser_path="mock-browser")
    with patch("core.browser_renderer.shutil.which", return_value=None), \
         patch.object(renderer, "render_pdf", return_value=result):
        with pytest.raises(RuntimeError, match="Cannot measure document overflow"):
            renderer.measure_overflow(tmp_path / "source.html")


def test_empty_contact_fields_do_not_render_stray_separators():
    from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
    vm = ResumeViewModel.from_profile({"name": "Synthetic"}, photo_mode="no-photo")
    header = HtmlThemeRenderer().render_header(vm, "modern-career")
    assert "•" not in header
    assert 'data-field="identity.email"' not in header
    vm = ResumeViewModel.from_profile({"name": "Synthetic", "email": "test@example.test"}, photo_mode="no-photo")
    header = HtmlThemeRenderer().render_header(vm, "modern-career")
    assert "•" not in header
    assert 'data-field="identity.email"' in header
