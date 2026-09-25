import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.rendercv_adapter import export_rendercv, import_rendercv, write_rendercv_json

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestRenderCVAdapter(unittest.TestCase):
    def setUp(self):
        self.rendercv = {
            "cv": {
                "name": "Alex Example",
                "headline": "Backend Engineer",
                "location": "Shanghai",
                "email": "alex@example.com",
                "phone": "+1 555 0100",
                "social_networks": [{"network": "GitHub", "username": "https://github.com/alex"}],
                "sections": {
                    "Experience": {"entries": [{
                        "company": "Example Inc.", "position": "Engineer",
                        "start_date": "2021-01", "end_date": "2024-01",
                        "highlights": ["Reduced p95 latency by 20%"],
                    }]},
                    "Education": {"entries": [{
                        "institution": "Example University", "area": "Computer Science",
                        "degree": "MSc", "start_date": "2018", "end_date": "2020",
                        "highlights": ["Honors"],
                    }]},
                    "Projects": {"entries": [{
                        "name": "Search Service", "summary": "Built search backend",
                        "highlights": ["Indexed 1M records"],
                    }]},
                    "Skills": {"entries": [{"label": "Languages", "details": "Python, Go"}]},
                    "Awards": {"entries": [{"name": "Best Project"}]},
                },
            },
            "design": {"theme": "classic"},
        }

    def test_import_maps_core_facts_and_reports_unsupported_sections(self):
        result = import_rendercv(self.rendercv)
        profile = result.profile
        self.assertEqual(profile["candidate"]["name"], "Alex Example")
        self.assertEqual(profile["experience"][0]["company"], "Example Inc.")
        self.assertEqual(profile["experience"][0]["bullets"], ["Reduced p95 latency by 20%"])
        self.assertEqual(profile["projects"][0]["name"], "Search Service")
        self.assertEqual(profile["competencies"]["Languages"], ["Python", "Go"])
        self.assertEqual(profile["candidate"]["school"], "Example University")
        self.assertIn("Awards", result.unsupported_sections)
        self.assertTrue(any("Awards" in warning for warning in result.warnings))
        self.assertIn("unsupported_sections", profile["rendercv_import_metadata"])

    def test_export_roundtrip_and_json_file(self):
        imported = import_rendercv(self.rendercv)
        exported = export_rendercv(imported.profile)
        cv = exported["cv"]
        self.assertEqual(cv["name"], "Alex Example")
        self.assertEqual(cv["sections"]["Experience"]["entries"][0]["company"], "Example Inc.")
        self.assertEqual(cv["sections"]["Projects"]["entries"][0]["name"], "Search Service")
        with tempfile.TemporaryDirectory() as tmp:
            path = write_rendercv_json(imported.profile, Path(tmp) / "nested" / "cv.json")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), exported)

    def test_json_path_supported_yaml_rejected_without_extra_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "cv.json"
            json_path.write_text(json.dumps(self.rendercv), encoding="utf-8")
            self.assertEqual(import_rendercv(json_path).profile["candidate"]["name"], "Alex Example")
            yaml_path = Path(tmp) / "cv.yaml"
            yaml_path.write_text("cv: {}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "accepts JSON"):
                import_rendercv(yaml_path)

    def test_invalid_sections_shape_fails_closed(self):
        invalid = {"cv": {"sections": ["not", "a", "mapping"]}}
        with self.assertRaisesRegex(ValueError, "must be an object"):
            import_rendercv(invalid)

    def test_cli_import_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "rendercv.json"
            profile = Path(tmp) / "profile.json"
            exported = Path(tmp) / "exported.json"
            source.write_text(json.dumps(self.rendercv), encoding="utf-8")
            base = [sys.executable, str(PROJECT_ROOT / "cli.py"), "rendercv"]
            imported = subprocess.run(
                base + ["import", str(source), "--output", str(profile), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertTrue(profile.exists())
            export = subprocess.run(
                base + ["export", str(profile), "--output", str(exported), "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT,
            )
            self.assertEqual(export.returncode, 0, export.stderr)
            self.assertTrue(exported.exists())
            self.assertIn("Experience", json.loads(exported.read_text(encoding="utf-8"))["cv"]["sections"])


if __name__ == "__main__":
    unittest.main()
