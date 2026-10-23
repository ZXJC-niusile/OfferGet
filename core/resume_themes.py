"""Canonical resume theme catalog shared by builders and command handlers."""

HTML_THEMES = (
    "modern-navy",
    "silicon-clean",
    "classic-tech",
    "asu-dense",
    "sidebar-clean",
    "academic-postgraduate",
    "engineering-sb2nov",
    "modern-corporate",
    "modern-career",
)
DOCX_THEMES = ("ats-docx",)
PDF_THEMES = HTML_THEMES + ("ats-plain", "academic-latex", "academic-typst")
THEMES = PDF_THEMES + DOCX_THEMES
