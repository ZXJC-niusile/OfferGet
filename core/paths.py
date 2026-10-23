"""Standard path and resource resolution for OfferGet.

Resolves repository roots, templates, themes, examples, and outputs consistently
across local dev checkouts, editable installations, and packaged runtimes.
"""

from __future__ import annotations

from pathlib import Path

# Robust project root determination
_CURRENT_FILE = Path(__file__).resolve()
# core/paths.py -> parent is core/ -> parent is project root
_PROJECT_ROOT = _CURRENT_FILE.parent.parent


def get_project_root() -> Path:
    """Returns the OfferGet project root directory."""
    return _PROJECT_ROOT


def get_template_path(name: str = "offer_strategy.html") -> Path:
    """Resolves an HTML template path from templates/ directory."""
    root = get_project_root()
    direct = root / "templates" / name
    if direct.is_file():
        return direct.resolve()
    # Check if name is already an existing path
    custom = Path(name)
    if custom.is_file():
        return custom.resolve()
    # Try relative to root
    rel = (root / name).resolve()
    if rel.is_file():
        return rel
    return direct.resolve()


def get_theme_dir() -> Path:
    """Returns the resume themes directory."""
    return (get_project_root() / "themes").resolve()


def get_theme_path(theme_name: str) -> Path:
    """Resolves a resume theme HTML template by name."""
    theme_clean = theme_name.strip()
    if not theme_clean.endswith(".html"):
        theme_clean = f"{theme_clean}.html"
    return (get_theme_dir() / theme_clean).resolve()


def get_example_path(filename: str) -> Path:
    """Resolves a file in the examples/ directory."""
    return (get_project_root() / "examples" / filename).resolve()


def get_output_dir(sub_dir: str = "") -> Path:
    """Returns and ensures an output directory (default: output/)."""
    out = get_project_root() / "output"
    if sub_dir:
        out = out / sub_dir
    out.mkdir(parents=True, exist_ok=True)
    return out.resolve()


def get_desktop_dir() -> Path:
    """Resolves the user's Desktop directory reliably across platforms (including Windows OneDrive redirection)."""
    home = Path.home()
    desktop = home / "Desktop"
    onedrive_desktop = home / "OneDrive" / "Desktop"
    if not desktop.exists() and onedrive_desktop.is_dir():
        return onedrive_desktop
    return desktop


def get_default_resume_output_dir() -> Path:
    """Returns and ensures the default resume output directory: Desktop/个人简历.

    Creates the directory on the user's Desktop upon invocation. If writing to Desktop
    fails (e.g. in restricted CI environments), safely falls back to output/个人简历.
    """
    desktop = get_desktop_dir()
    target = desktop / "个人简历"
    try:
        target.mkdir(parents=True, exist_ok=True)
        return target.resolve()
    except OSError:
        fallback = get_project_root() / "output" / "个人简历"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback.resolve()


__all__ = [
    "get_project_root",
    "get_template_path",
    "get_theme_dir",
    "get_theme_path",
    "get_example_path",
    "get_output_dir",
    "get_desktop_dir",
    "get_default_resume_output_dir",
]

