#!/usr/bin/env python3
"""OfferGet Resume Generation Runner for 范增煜 (Demo Resumes).

Uses the unified core.resume_builder.ResumeBuilder engine to generate
all 6 resume variants with photo placeholders and single-page compaction.
"""

import sys
from pathlib import Path

# Ensure OfferGet root is in sys.path
DEMO_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DEMO_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.resume_builder import ResumeBuilder


def main():
    profile_path = DEMO_DIR / "candidate_profile.json"
    print("==================================================")
    print("OfferGet Resume Generation Pipeline (范增煜 运营岗定制)")
    print("==================================================")

    builder = ResumeBuilder(profile_path)
    results = builder.build_all(output_dir=DEMO_DIR, photo=True, autofit=True)

    print("-" * 50)
    for theme_name, files in results.items():
        pdf_path = files.get("pdf", Path(""))
        print(f"  ✓ {theme_name:<16} -> {pdf_path.name}")
    print("==================================================")
    print("🎉 All 6 resume variants built successfully!")


if __name__ == "__main__":
    main()
