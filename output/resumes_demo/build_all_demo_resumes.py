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
    print("OfferGet Resume Generation Pipeline (范增煜)")
    print("==================================================")

    builder = ResumeBuilder(profile_path)
    results = builder.build_all(
        output_dir=DEMO_DIR,
        photo=True,
        autofit=True,
        photo_path=r"C:\Users\26325\Desktop\81d2cd3e8862f04e701b65d4d8bf3122.jpg",
    )

    import shutil

    print("-" * 50)
    for theme_name, files in results.items():
        pdf_path = files.get("pdf", Path(""))
        print(f"  ✓ {theme_name:<16} -> {pdf_path.name}")

    # Synchronize flagship modern-navy theme to user-friendly target names
    flagship_pdf = results.get("modern-navy", {}).get("pdf")
    flagship_html = results.get("modern-navy", {}).get("html")

    if flagship_pdf and flagship_pdf.exists():
        target_names = [
            "范增煜-运营实习生-中文简历.pdf",
            "范增煜中文简历_运营2026.9.pdf",
            "resume_operations_fanzengyu.pdf",
        ]
        for name in target_names:
            dst = DEMO_DIR / name
            shutil.copy2(flagship_pdf, dst)
            print(f"  ★ Generated named resume: {dst.name}")

        # Also copy to User Desktop for instant access
        desktop_dir = Path(r"C:\Users\26325\Desktop")
        if desktop_dir.exists() and desktop_dir.is_dir():
            try:
                shutil.copy2(flagship_pdf, desktop_dir / "范增煜-运营实习生-中文简历.pdf")
                print(f"  ★ Copied to Desktop -> C:\\Users\\26325\\Desktop\\范增煜-运营实习生-中文简历.pdf")
            except Exception as e:
                print(f"  ⚠ Desktop copy skipped: {e}")

    if flagship_html and flagship_html.exists():
        shutil.copy2(flagship_html, DEMO_DIR / "范增煜-运营实习生-中文简历.html")
        shutil.copy2(flagship_html, DEMO_DIR / "resume_operations_fanzengyu.html")

    print("==================================================")
    print("🎉 All 6 resume variants built successfully!")


if __name__ == "__main__":
    main()
