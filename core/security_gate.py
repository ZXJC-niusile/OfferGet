"""
OfferGet Unified Output Serializer & Security Gate (core/security_gate.py)
==========================================================================
Provides security sanitization, character escaping, URL scheme verification,
and output validation across HTML, LaTeX, Typst, and Markdown resume outputs:

1. HTML Sanitization:
   - `escape_html_text`: Escapes HTML text contents (&, <, >, ", ').
   - `escape_html_attribute`: Escapes HTML attribute values.
   - `sanitize_url`: Strict whitelist verification for URLs (http, https, mailto, safe image data URIs).

2. Markup Escaping:
   - `escape_latex`: Escapes LaTeX control characters (\\, &, %, $, #, _, {, }, ~, ^).
   - `escape_typst`: Escapes Typst control characters (#, [, ], \", *, _, @, $, `, \\).

3. Output Security Validation:
   - `validate_output_security`: Checks generated outputs for residual XSS vectors,
     unauthorized event handlers, dangerous pseudo-protocols, and unreplaced placeholders.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any, List, Optional, Union

__all__ = [
    "escape_html_text",
    "escape_html_attribute",
    "sanitize_url",
    "escape_latex",
    "escape_typst",
    "validate_output_security",
]


def escape_html_text(text: Any) -> str:
    """
    Escapes special characters in text for safe inclusion inside HTML body elements.
    Converts &, <, >, ", and ' to safe HTML entities.
    """
    if text is None:
        return ""
    s = str(text)
    return html.escape(s, quote=True)


def escape_html_attribute(val: Any) -> str:
    """
    Escapes special characters for safe inclusion inside HTML attribute values (e.g. href, title, alt).
    """
    if val is None:
        return ""
    s = str(val)
    return html.escape(s, quote=True)


_DATA_IMAGE_REGEX = re.compile(
    r"^data:image\/(?:jpeg|png|webp|gif);base64,[A-Za-z0-9+/=\s]+$",
    re.IGNORECASE,
)


def sanitize_url(url: Any, allow_data_image: bool = True) -> str:
    """
    Strict URL scheme whitelist validator.
    Only allows:
      - http://
      - https://
      - mailto:
      - safe data:image/(jpeg|png|webp|gif);base64,... (if allow_data_image=True)

    Rejects and returns empty string "" for:
      - Any URL containing javascript:, vbscript:, or data:text/html
      - file:, ftp:, or protocol-relative // URLs
      - Invalid or non-whitelisted data URIs (e.g. svg, html, octet-stream)
    """
    if url is None:
        return ""
    raw_url = str(url).strip()
    if not raw_url:
        return ""

    # Strip whitespace and control characters to detect obfuscated protocols
    no_ctrl = re.sub(r"[\s\x00-\x1f\x7f-\x9f]+", "", raw_url.lower())
    if "javascript:" in no_ctrl or "vbscript:" in no_ctrl or "data:text/html" in no_ctrl:
        return ""
    if "data:text/" in no_ctrl:
        return ""

    # Check for safe base64 data image URI
    if raw_url.lower().startswith("data:"):
        if allow_data_image and _DATA_IMAGE_REGEX.match(raw_url):
            return raw_url
        return ""

    # Check for mailto:
    if raw_url.lower().startswith("mailto:"):
        # Ensure it doesn't contain dangerous pseudo-scripts or forbidden control chars
        if re.match(r"^mailto:[^\s\"'<>]+$", raw_url, re.IGNORECASE):
            return raw_url
        return ""

    # Check for http:// and https://
    if re.match(r"^https?://[^\s\"'<>]+", raw_url, re.IGNORECASE):
        return raw_url

    return ""


_LATEX_MAPPING = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(text: Any) -> str:
    """
    Escapes special LaTeX characters: \\, &, %, $, #, _, {, }, ~, ^.
    Uses single-pass character-by-character mapping to avoid re-escaping generated braces.
    """
    if text is None:
        return ""
    s = str(text)
    return "".join(_LATEX_MAPPING.get(c, c) for c in s)


_TYPST_MAPPING = {
    "\\": "\\\\",
    "#": "\\#",
    "[": "\\[",
    "]": "\\]",
    '"': '\\"',
    "*": "\\*",
    "_": "\\_",
    "@": "\\@",
    "$": "\\$",
    "`": "\\`",
}


def escape_typst(text: Any) -> str:
    """
    Escapes special Typst characters: #, [, ], \", *, _, @, $, `, \\.
    Uses single-pass character-by-character mapping to safely neutralize control characters.
    """
    if text is None:
        return ""
    s = str(text)
    return "".join(_TYPST_MAPPING.get(c, c) for c in s)


def validate_output_security(content: str, format_type: str = "html") -> List[str]:
    """
    Audits serialized document output for security risks:
    - Dangerous <script>, <iframe>, <object>, <embed> tags
    - Inline on* event handlers (allowing only verified safe internal image fallback)
    - Dangerous javascript:, vbscript:, data:text/html URI schemes
    - Unreplaced {{...}} template placeholders
    - Format-specific code injection vectors (for Typst/LaTeX)

    Returns a list of detected risk descriptions, or an empty list [] if safe.
    """
    risks: List[str] = []
    if not content:
        return risks

    # 1. Universal check: Unreplaced template placeholders
    placeholders = re.findall(r"\{\{[^}]+\}\}", content)
    if placeholders:
        for p in sorted(set(placeholders)):
            risks.append(f"Unreplaced placeholder detected: {p}")

    fmt = (format_type or "html").lower()

    if fmt == "html":
        # 2. Dangerous HTML tags
        tag_checks = [
            (r"<script\b", "Script tag (<script>)"),
            (r"<\s*/\s*script\s*>", "Closing script tag (</script>)"),
            (r"<iframe\b", "Inline frame (<iframe>)"),
            (r"<object\b", "Embedded object (<object>)"),
            (r"<embed\b", "Plugin embed (<embed>)"),
            (r"<form\b", "Form tag (<form>)"),
        ]
        for pat, desc in tag_checks:
            if re.search(pat, content, re.IGNORECASE):
                risks.append(f"Dangerous HTML pattern detected: {desc}")

        # 3. Dangerous URI schemes in HTML
        uri_checks = [
            (r"href\s*=\s*[\"']?\s*javascript:", "javascript: URI in href"),
            (r"src\s*=\s*[\"']?\s*javascript:", "javascript: URI in src"),
            (r"href\s*=\s*[\"']?\s*vbscript:", "vbscript: URI in href"),
            (r"src\s*=\s*[\"']?\s*vbscript:", "vbscript: URI in src"),
            (r"href\s*=\s*[\"']?\s*data:text/html", "data:text/html URI in href"),
            (r"src\s*=\s*[\"']?\s*data:text/html", "data:text/html URI in src"),
            (r"href\s*=\s*[\"']?\s*data:image/svg\+xml", "data:image/svg+xml URI in href"),
            (r"src\s*=\s*[\"']?\s*data:image/svg\+xml", "data:image/svg+xml URI in src"),
        ]
        for pat, desc in uri_checks:
            if re.search(pat, content, re.IGNORECASE):
                risks.append(f"Dangerous URI pattern detected: {desc}")

        # 4. Inline event handlers on* (e.g. onload=, onerror=, onclick=) inside HTML tags
        tag_matches = re.finditer(r"<([a-zA-Z][a-zA-Z0-9:-]*)\b([^>]*)/?>", content)
        for tm in tag_matches:
            tag_name = tm.group(1).lower()
            tag_attrs = tm.group(2)
            handler_matches = re.finditer(
                r"\b(on[a-zA-Z]+)\s*=\s*(?:([\"'])(.*?)\2|([^\s>]+))",
                tag_attrs,
                re.IGNORECASE,
            )
            for m in handler_matches:
                event_name = m.group(1).lower()
                event_val = m.group(3) if m.group(2) else (m.group(4) or "")
                # Permit the designated benign internal photo fallback snippet on <img> tags
                if tag_name == "img" and event_name == "onerror" and "this.style.display" in event_val and "nextElementSibling" in event_val:
                    continue
                risks.append(f"Dangerous inline event handler '{event_name}' in <{tag_name}>: {event_val[:40]}")

    elif fmt in ("typst", "typ"):
        # Check for dangerous Typst code injections if unescaped at top-level
        if re.search(r"^\s*#import\b", content, re.MULTILINE):
            risks.append("Unescaped top-level Typst '#import' detected")
        if re.search(r"#(?:sys|plugin|eval)\b", content):
            risks.append("Dangerous Typst built-in expression detected")

    elif fmt in ("latex", "tex"):
        # Check for unescaped dangerous LaTeX primitives
        if re.search(r"(?<!\\)\\input\{", content):
            risks.append("Unescaped LaTeX \\input directive detected")
        if re.search(r"\\write18\b", content):
            risks.append("Dangerous LaTeX shell-escape (\\write18) detected")

    return risks
