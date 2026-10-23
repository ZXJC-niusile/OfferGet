"""Installed diagnostics must not depend on source examples/tests or writable packages."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

from presentation.commands import doctor_cmd, selftest_cmd
from presentation.diagnostic_data import FIXTURE_NAMES, missing_resources

ROOT = Path(__file__).resolve().parents[1]


def test_diagnostic_resources_are_complete():
    assert missing_resources() == []
    assert doctor_cmd.check_sample_assets()["valid"] is True


def test_missing_package_resources_are_not_optional(monkeypatch, capsys):
    missing = ["presentation.diagnostic_data/candidate_profile.json"]
    monkeypatch.setattr(selftest_cmd, "missing_resources", lambda: missing)
    monkeypatch.setattr(doctor_cmd, "missing_resources", lambda: missing)
    check = doctor_cmd.check_sample_assets()
    assert check["valid"] is False
    assert "Reinstall" in check["guidance"]
    with pytest.raises(SystemExit) as exc:
        selftest_cmd.cmd_selftest()
    assert exc.value.code == 1
    assert "Missing installed diagnostic resources" in capsys.readouterr().err


def test_smoke_checks_explicitly_skip_optional_rendering(monkeypatch, tmp_path, capsys):
    from core.browser_renderer import BrowserRenderer

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(BrowserRenderer, "diagnose_browser", lambda: {
        "found": False, "browser_path": None,
        "installation_guide": "Install a browser for optional PDF rendering.",
        "checked_candidates": [],
    })
    selftest_cmd.cmd_selftest()
    output = capsys.readouterr().out
    assert "CORE SMOKE CHECKS PASSED" in output
    assert "PDF rendering: NOT RUN" in output
    assert "Headless Browser: NOT FOUND" in output
    assert list(tmp_path.iterdir()) == []
    assert doctor_cmd.cmd_doctor() == 1
    output = capsys.readouterr().out
    assert "Installed Diagnostic Resources ... ✓ Verified" in output
    assert "missing optional browser" in output


def _run(command, cwd, env):
    result = subprocess.run(command, cwd=cwd, env=env, text=True, encoding="utf-8",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120, check=False)
    assert result.returncode == 0, result.stdout
    return result.stdout


@pytest.mark.package
def test_wheel_installed_diagnostics_outside_source_tree(tmp_path):
    # Build without downloads. The build backend must already be provisioned,
    # as it is in CI (pip install setuptools wheel before the test suite).
    source = tmp_path / "source"
    source.mkdir()
    for name in ("core", "presentation", "services", "templates", "themes"):
        shutil.copytree(ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("cli.py", "pyproject.toml", "README.md", "LICENSE"):
        shutil.copyfile(ROOT / name, source / name)
    env = dict(os.environ, PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
               PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    wheels = tmp_path / "wheels"
    _run([sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps",
          "--no-build-isolation", "--wheel-dir", str(wheels), str(source)], tmp_path, env)
    wheel, = wheels.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert all(f"presentation/diagnostic_data/{name}" in names for name in FIXTURE_NAMES)
        assert "templates/offer_strategy.html" in names
        assert not any(name.startswith(("examples/", "tests/")) for name in names)

    installation = tmp_path / "isolated"
    # Host pip can install into a fresh pip-free interpreter. This retains a
    # real isolated wheel installation without copying/hashing pip's own tree.
    venv.EnvBuilder(with_pip=False).create(installation)
    python = installation / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run([sys.executable, "-m", "pip", "--python", str(python), "install",
          "--no-index", "--no-deps", str(wheel)], tmp_path, env)
    site = Path(_run([str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"], tmp_path, env).strip())
    # Forbid network access and package writes, including on privileged hosts
    # where chmod alone would not model a read-only system installation.
    (site / "sitecustomize.py").write_text('''import os
from pathlib import Path
import sys
site = Path(__file__).resolve().parent

def guard(event, args):
    if event in {"socket.connect", "socket.getaddrinfo"}:
        raise RuntimeError("Network is forbidden in diagnostic smoke tests")
    if event == "open" and isinstance(args[0], (str, bytes)):
        target = Path(os.fsdecode(args[0])).resolve()
        if site in target.parents:
            mode, flags = args[1], args[2]
            if (mode and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
                raise RuntimeError("Installed resources are read-only")
sys.addaudithook(guard)
''', encoding="utf-8")
    before = {str(p.relative_to(site)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in site.rglob("*") if p.is_file()}
    # Remove the build checkout entirely before running either installed entrypoint.
    shutil.rmtree(source)
    outside = tmp_path / "outside"
    outside.mkdir()
    info = json.loads(_run([str(python), "-I", "-B", "-c",
                           ("import cli, json; from core.browser_renderer import BrowserRenderer; "
                           "print(json.dumps({'cli': cli.__file__, 'browser': BrowserRenderer.diagnose_browser()['found']}))")], outside, env))
    assert site in Path(info["cli"]).parents
    result = subprocess.run([str(python), "-I", "-B", "-m", "cli", "doctor"], cwd=outside,
                            env=env, text=True, encoding="utf-8", capture_output=True, timeout=30, check=False)
    assert result.returncode == (0 if info["browser"] else 1), result.stdout + result.stderr
    assert "Installed Diagnostic Resources ... ✓ Verified" in result.stdout
    assert "Missing:" not in result.stdout
    output = _run([str(python), "-I", "-B", "-m", "cli", "selftest"], outside, env)
    assert "CORE SMOKE CHECKS PASSED" in output
    assert "PDF rendering: NOT RUN" in output
    assert list(outside.iterdir()) == []
    after = {str(p.relative_to(site)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in site.rglob("*") if p.is_file()}
    assert after == before
