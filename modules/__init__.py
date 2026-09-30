"""
OfferGet Modules Package (Legacy Namespace Alias to core.jd_analyst)
"""
from __future__ import annotations
import sys
from core import jd_analyst

sys.modules["modules.jd_analyst"] = jd_analyst
sys.modules["modules.jd_analyst.models"] = sys.modules.get("core.jd_analyst.models", getattr(jd_analyst, "models", None))
