"""Small synthetic fixtures for installed-runtime diagnostics, never user data."""

import json
from importlib.resources import files

FIXTURE_NAMES = (
    "sample_ai_jd.txt",
    "candidate_profile.json",
)


def read_fixture(name: str) -> str:
    if name not in FIXTURE_NAMES:
        raise ValueError(f"Unknown diagnostic fixture: {name}")
    return files(__package__).joinpath(name).read_text(encoding="utf-8")


def load_fixture(name: str) -> dict:
    return json.loads(read_fixture(name))


def missing_resources() -> list[str]:
    missing = []
    for name in FIXTURE_NAMES:
        if not files(__package__).joinpath(name).is_file():
            missing.append(f"{__package__}/{name}")
    return missing
