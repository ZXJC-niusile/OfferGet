"""
Resume Application Services (services/resume_service.py)
=======================================================
Domain services for generating multi-template resumes, auditing quality, and versioning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ResumeService:
    """Domain service for generating multi-template resumes and auditing layout/XSS health."""

    @property
    def supported_themes(self) -> List[str]:
        from core.resume_builder import ResumeBuilder

        return list(ResumeBuilder.THEMES)

    def build_resume(
        self,
        profile_or_path: Union[Dict[str, Any], str, Path],
        theme: str = "modern-navy",
        output_dir: Union[str, Path] = "dist/resume",
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
        photo_mode: Optional[str] = None,
        *,
        pages: str = "auto",
        adaptive_fill: bool = True,
        diff_ledger: bool = True,
        baseline_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Path]:
        """Build a theme, forwarding layout/evidence controls to ResumeBuilder.

        Preserve the service defaults (modern-navy, dist/resume, photo=True).
        Theme-specific support and privacy restrictions remain with the builder.
        baseline_profile is already-loaded data; only the CLI loads --baseline.
        """
        from core.resume_builder import ResumeBuilder

        builder = ResumeBuilder(profile_or_path, photo_path=photo_path, anonymize=anonymize, photo_mode=photo_mode)
        return builder.build_theme(
            theme=theme,
            output_dir=output_dir,
            photo=photo,
            autofit=autofit,
            anonymize=anonymize,
            pages=pages,
            adaptive_fill=adaptive_fill,
            diff_ledger=diff_ledger,
            baseline_profile=baseline_profile,
        )

    def build_all(
        self,
        profile_or_path: Union[Dict[str, Any], str, Path],
        output_dir: Union[str, Path] = "dist/resume",
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
        photo_mode: Optional[str] = None,
        *,
        pages: str = "auto",
        adaptive_fill: bool = True,
        diff_ledger: bool = True,
        baseline_profile: Optional[Dict[str, Any]] = None,
        include_docx: bool = False,
    ) -> Dict[str, Dict[str, Path]]:
        """Build the standard variants, optionally including DOCX.

        Existing output/photo defaults are unchanged. Layout/evidence controls
        follow build_resume; include_docx matches the builder's opt-in default.
        """
        from core.resume_builder import ResumeBuilder

        builder = ResumeBuilder(profile_or_path, photo_path=photo_path, anonymize=anonymize, photo_mode=photo_mode)
        return builder.build_all(
            output_dir=output_dir,
            photo=photo,
            photo_path=photo_path,
            autofit=autofit,
            anonymize=anonymize,
            pages=pages,
            adaptive_fill=adaptive_fill,
            diff_ledger=diff_ledger,
            baseline_profile=baseline_profile,
            include_docx=include_docx,
        )

    def audit_resume(self, html_path: Union[str, Path]) -> Dict[str, Any]:
        """Audits generated resume HTML quality, layout health, and security."""
        from core.resume_builder import audit_resume_quality

        return audit_resume_quality(html_path)


class ResumeVersionService:
    """Queries immutable application-linked resume version metadata."""

    def __init__(self, db_path: Union[str, Path] = "offerget_applications.db"):
        from core.application_tracker import ApplicationStore

        self.store = ApplicationStore(db_path)

    def __enter__(self) -> "ResumeVersionService":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        self.store.close()

    def list(self, application_id: Optional[str] = None) -> List[Any]:
        return self.store.list_resume_versions(application_id)

    def get(self, version_id: str) -> Any:
        return self.store.get_resume_version(version_id)

    def compare(self, before_id: str, after_id: str) -> Dict[str, Any]:
        from core.resume_version_diff import compare_resume_versions

        before = self.get(before_id)
        after = self.get(after_id)
        if before is None or after is None:
            missing = before_id if before is None else after_id
            raise KeyError(missing)
        return compare_resume_versions(before, after)
