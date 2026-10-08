"""Small synthetic fixtures for installed-runtime diagnostics, never user data."""

import json
from importlib.resources import files

FIXTURE_NAMES = (
    "sample_ai_jd.txt",
    "candidate_profile.json",
    "academic_profile.json",
    "sample_advisor.json",
)


def read_fixture(name: str) -> str:
    if name not in FIXTURE_NAMES:
        raise ValueError(f"Unknown diagnostic fixture: {name}")
    return files(__package__).joinpath(name).read_text(encoding="utf-8")


def load_fixture(name: str) -> dict:
    return json.loads(read_fixture(name))


def missing_resources() -> list[str]:
    missing = []
    for package, names in (
        (__package__, FIXTURE_NAMES),
        ("templates", ("offer_strategy.html",)),
    ):
        for name in names:
            if not files(package).joinpath(name).is_file():
                missing.append(f"{package}/{name}")
    return missing
