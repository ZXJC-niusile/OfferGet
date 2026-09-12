"""
ApexResume Core Engine
~~~~~~~~~~~~~~~~~~~~~~
Deterministic verification, cross-platform PDF rendering, and smart auto-fit compression.
"""

from .render import BrowserRenderer
from .audit import ResumeAuditor
from .autofit import AutoFitEngine

__all__ = ["BrowserRenderer", "ResumeAuditor", "AutoFitEngine"]
