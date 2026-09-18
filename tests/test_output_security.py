"""
Tests for OfferGet Unified Output Serializer & Security Gate (tests/test_output_security.py)
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.academic_exporter import AcademicExporter
from core.resume_builder import ResumeBuilder
from core.security_gate import (
    escape_html_attribute,
    escape_html_text,
    escape_latex,
    escape_typst,
    sanitize_url,
    validate_output_security,
)


class TestSecurityGateUnit(unittest.TestCase):
    """Unit tests for individual escaping and validation functions in core.security_gate."""

    def test_escape_html_text(self):
        # Basic tags
        self.assertEqual(
            escape_html_text("<script>alert(1)</script>"),
            "&lt;script&gt;alert(1)&lt;/script&gt;",
        )
        self.assertEqual(
            escape_html_text("<img src=x onerror=alert(1)>"),
            "&lt;img src=x onerror=alert(1)&gt;",
        )
        # Quotes and ampersands
        self.assertEqual(
            escape_html_text('A & B "quoted" \'single\''),
            "A &amp; B &quot;quoted&quot; &#x27;single&#x27;",
        )
        # None and empty
        self.assertEqual(escape_html_text(None), "")
        self.assertEqual(escape_html_text(""), "")
        # Number conversion
        self.assertEqual(escape_html_text(12345), "12345")

    def test_escape_html_attribute(self):
        # Attribute breaking
        self.assertEqual(
            escape_html_attribute('value" onfocus="alert(1)'),
            "value&quot; onfocus=&quot;alert(1)",
        )
        self.assertEqual(
            escape_html_attribute("x' or '1'='1"),
            "x&#x27; or &#x27;1&#x27;=&#x27;1",
        )
        self.assertEqual(escape_html_attribute(None), "")
        self.assertEqual(escape_html_attribute(""), "")

    def test_sanitize_url_whitelist(self):
        # Allowed schemes
        self.assertEqual(sanitize_url("http://example.com/cv"), "http://example.com/cv")
        self.assertEqual(sanitize_url("https://secure.site.org"), "https://secure.site.org")
        self.assertEqual(sanitize_url("mailto:test@example.com"), "mailto:test@example.com")

        # Allowed safe data image URIs
        valid_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        self.assertEqual(sanitize_url(valid_png, allow_data_image=True), valid_png)
        valid_jpeg = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
        self.assertEqual(sanitize_url(valid_jpeg, allow_data_image=True), valid_jpeg)

        # Disallow data image when allow_data_image=False
        self.assertEqual(sanitize_url(valid_png, allow_data_image=False), "")

    def test_sanitize_url_blocks_attacks(self):
        # Javascript schemes
        self.assertEqual(sanitize_url("javascript:alert(1)"), "")
        self.assertEqual(sanitize_url("JAVASCRIPT:alert('XSS')"), "")
        self.assertEqual(sanitize_url("javascript:void(0)"), "")
        self.assertEqual(sanitize_url("  javascript:alert(1)  "), "")
        self.assertEqual(sanitize_url("java\nscript:alert(1)"), "")
        self.assertEqual(sanitize_url("java\tscript:alert(1)"), "")

        # VBScript
        self.assertEqual(sanitize_url("vbscript:msgbox(1)"), "")

        # Dangerous data URIs
        self.assertEqual(sanitize_url("data:text/html,<script>alert(1)</script>"), "")
        self.assertEqual(sanitize_url("data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="), "")
        self.assertEqual(sanitize_url("data:image/svg+xml;utf8,<svg onload=alert(1)>"), "")
        self.assertEqual(sanitize_url("data:application/octet-stream;base64,AAAA"), "")

        # Protocol-relative and local files
        self.assertEqual(sanitize_url("//attacker.com/evil.js"), "")
        self.assertEqual(sanitize_url("file:///etc/passwd"), "")
        self.assertEqual(sanitize_url("ftp://example.com/file"), "")

        # None and empty
        self.assertEqual(sanitize_url(None), "")
        self.assertEqual(sanitize_url(""), "")

    def test_escape_typst(self):
        # Typst injection payloads
        self.assertEqual(
            escape_typst('#import "evil": *'),
            r'\#import \"evil\": \*',
        )
        self.assertEqual(
            escape_typst("[bracket content]"),
            r"\[bracket content\]",
        )
        self.assertEqual(
            escape_typst("@label_reference"),
            r"\@label\_reference",
        )
        self.assertEqual(
            escape_typst("$E=mc^2$ math formula"),
            r"\$E=mc^2\$ math formula",
        )
        self.assertEqual(
            escape_typst("*bold* and _italic_ and `code`"),
            r"\*bold\* and \_italic\_ and \`code\`",
        )
        self.assertEqual(
            escape_typst(r"C:\Users\Admin"),
            r"C:\\Users\\Admin",
        )
        self.assertEqual(escape_typst(None), "")

    def test_escape_latex(self):
        # LaTeX injection payloads
        self.assertEqual(
            escape_latex(r"\input{/etc/passwd}"),
            r"\textbackslash{}input\{/etc/passwd\}",
        )
        self.assertEqual(
            escape_latex(r"\write18{calc.exe}"),
            r"\textbackslash{}write18\{calc.exe\}",
        )
        self.assertEqual(
            escape_latex("100% & $50 #1 _var_ {obj} ~tilde ^hat"),
            r"100\% \& \$50 \#1 \_var\_ \{obj\} \textasciitilde{}tilde \textasciicircum{}hat",
        )
        self.assertEqual(escape_latex(None), "")

    def test_validate_output_security(self):
        # Clean HTML
        clean_html = "<!DOCTYPE html><html><body><h1>Alice</h1><p>Software Engineer</p></body></html>"
        self.assertEqual(validate_output_security(clean_html, "html"), [])

        # Benign photo fallback handler is allowed
        benign_html = """
        <img src="data:image/png;base64,AAAA" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';" />
        """
        self.assertEqual(validate_output_security(benign_html, "html"), [])

        # Detect <script>
        xss_script = "<div><script>alert(1)</script></div>"
        risks = validate_output_security(xss_script, "html")
        self.assertTrue(any("script" in r.lower() for r in risks))

        # Detect malicious inline event handler
        xss_onerror = '<img src="invalid" onerror="alert(1)">'
        risks = validate_output_security(xss_onerror, "html")
        self.assertTrue(any("onerror" in r.lower() for r in risks))

        # Detect javascript: protocol in href
        xss_js_href = '<a href="javascript:alert(1)">Click</a>'
        risks = validate_output_security(xss_js_href, "html")
        self.assertTrue(any("javascript:" in r.lower() for r in risks))

        # Detect unreplaced placeholders
        dirty_placeholder = "<h1>Candidate</h1><div>{{SECTIONS_CONTENT}}</div>"
        risks = validate_output_security(dirty_placeholder, "html")
        self.assertTrue(any("placeholder" in r.lower() for r in risks))

        # Typst security validation
        typst_evil = '#import "evil": *\n#sys.command("calc")\n= Candidate'
        typst_risks = validate_output_security(typst_evil, "typst")
        self.assertTrue(any("import" in r.lower() for r in typst_risks))
        self.assertTrue(any("typst" in r.lower() for r in typst_risks))

        # LaTeX security validation
        latex_evil = r"\input{/etc/passwd}" + "\n" + r"\write18{whoami}"
        latex_risks = validate_output_security(latex_evil, "latex")
        self.assertTrue(any("input" in r.lower() for r in latex_risks))
        self.assertTrue(any("write18" in r.lower() for r in latex_risks))


class TestSecurityGateIntegration(unittest.TestCase):
    """Integration tests verifying ResumeBuilder and AcademicExporter defend against real injection payloads."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="offerget_test_sec_int_"))
        self.malicious_profile = {
            "name": "<script>alert('pwn_name')</script>",
            "candidate": {
                "name": "<script>alert('pwn_name')</script>",
                "title": 'Architect" onclick="alert(\'pwn_title\')',
                "email": "javascript:alert('pwn_email')",
                "phone": "+86 138-0000-0000<script>",
                "school": "Exploit University \\input{/etc/passwd}",
                "degree": "Master<img src=x onerror=alert('pwn_deg')>",
                "location": "Beijing<iframe src='http://evil.com'>",
                "edu_time": "2020-2024",
                "reserve_photo": True,
                "education_rows": [
                    [
                        "GPA 4.0<script>alert(1)</script>",
                        "First Prize #import",
                        "CET-6 \\write18",
                    ]
                ],
            },
            "experience": [
                {
                    "org": "Evil Corp <script>alert('org')</script>",
                    "dept": "Security #import",
                    "role": "Lead <img src=x onerror=alert('role')>",
                    "time": "2023 - 2024",
                    "bullets": [
                        "Conducted **<script>alert('bullet')</script>** testing",
                        "Executed #import and \\input{secret} attacks",
                        "Injected [bracket] and @label and $E=mc^2$ math",
                    ],
                }
            ],
            "projects": [
                {
                    "name": "Project XSS <script>",
                    "role": "Owner #import [evil]",
                    "time": "2023",
                    "bullets": [
                        "Achieved **high impact** with \\write18{sh}",
                    ],
                }
            ],
            "competencies": {
                "Injections <script>": [
                    "<img src=x onerror=alert(1)>",
                    "#import evil",
                    "\\input{flag}",
                ]
            },
        }

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_resume_builder_html_defense(self):
        """Verify ResumeBuilder HTML themes escape all malicious payloads without XSS execution risks."""
        builder = ResumeBuilder(self.malicious_profile)

        for theme in ["modern-navy", "silicon-clean", "classic-tech"]:
            res = builder.build_html_theme(theme, self.test_dir, photo=True, autofit=False)
            html_text = res["html"].read_text(encoding="utf-8")

            # Must not contain unescaped dangerous tags
            self.assertNotIn("<script>", html_text)
            self.assertNotIn("</script>", html_text)
            self.assertNotIn("<iframe", html_text)
            self.assertNotIn("href=\"javascript:", html_text)
            self.assertNotIn("onerror=\"alert(", html_text)
            self.assertNotIn("onclick=\"alert(", html_text)

            # Escaped representations must be present safely
            self.assertIn("&lt;script&gt;alert(&#x27;pwn_name&#x27;)&lt;/script&gt;", html_text)
            self.assertIn("&lt;img src=x onerror=alert(&#x27;role&#x27;)&gt;", html_text)

            # Security validation gate must report 0 risks
            risks = validate_output_security(html_text, format_type="html")
            self.assertEqual(risks, [], f"Security gate found risks in theme {theme}: {risks}")

    def test_resume_builder_ats_plain_defense(self):
        """Verify ATS Plain single-column HTML escapes malicious inputs."""
        builder = ResumeBuilder(self.malicious_profile)
        res = builder.build_ats_plain(self.test_dir, photo=True)
        ats_html = res["html"].read_text(encoding="utf-8")

        self.assertNotIn("<script>", ats_html)
        self.assertNotIn("<iframe", ats_html)
        self.assertNotIn("onerror=\"alert(", ats_html)
        self.assertNotIn("onclick=\"alert(", ats_html)

        risks = validate_output_security(ats_html, format_type="html")
        self.assertEqual(risks, [], f"Security gate found risks in ATS HTML: {risks}")

    def test_academic_exporter_typst_defense(self):
        """Verify AcademicExporter Typst escapes control characters like #import, [bracket], @label, $math$."""
        exporter = AcademicExporter()
        typ_src = exporter.generate_typst(self.malicious_profile, reserve_photo=True)

        # Must not have raw executable #import directives
        self.assertNotIn("\n#import", typ_src)
        self.assertNotIn(" #import", typ_src)

        # Must be escaped
        self.assertIn(r"\#import", typ_src)
        self.assertIn(r"\[bracket\]", typ_src)
        self.assertIn(r"\@label", typ_src)
        self.assertIn(r"\$E=mc^2\$", typ_src)

        # Typst security validation gate
        risks = validate_output_security(typ_src, format_type="typst")
        self.assertEqual(risks, [], f"Typst security gate found risks: {risks}")

    def test_academic_exporter_latex_defense(self):
        """Verify AcademicExporter LaTeX escapes \\input, \\write18, &, %, $."""
        exporter = AcademicExporter()
        tex_src = exporter.generate_latex(self.malicious_profile, reserve_photo=True)

        # Must not contain raw executable \\input{/etc/passwd}
        self.assertNotIn(r"\input{/etc/passwd}", tex_src)
        self.assertNotIn(r"\write18", tex_src)

        # Must be escaped
        self.assertIn(r"\textbackslash{}input\{/etc/passwd\}", tex_src)
        self.assertIn(r"\textbackslash{}write18", tex_src)

        # LaTeX security validation gate
        risks = validate_output_security(tex_src, format_type="latex")
        self.assertEqual(risks, [], f"LaTeX security gate found risks: {risks}")

    def test_academic_exporter_html_preview_defense(self):
        """Verify AcademicExporter HTML preview escapes all XSS payloads."""
        exporter = AcademicExporter()
        html_preview = exporter.generate_latex_html_preview(self.malicious_profile, reserve_photo=True)

        self.assertNotIn("<script>", html_preview)
        self.assertNotIn("<iframe", html_preview)
        self.assertNotIn("onerror=\"alert(", html_preview)

        risks = validate_output_security(html_preview, format_type="html")
        self.assertEqual(risks, [], f"Academic HTML preview security gate found risks: {risks}")


if __name__ == "__main__":
    unittest.main()
