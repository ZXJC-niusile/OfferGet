"""Shared pytest fixtures across OfferGet test modules."""

from __future__ import annotations

import pytest

from scripts.qa_common import synthetic_portrait_png


@pytest.fixture
def portrait(tmp_path):
    """Clearly synthetic head-and-shoulders test illustration, never a real person."""
    path = tmp_path / "synthetic-portrait.png"
    path.write_bytes(synthetic_portrait_png())
    return path
