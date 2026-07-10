"""
Config strict mode, end-to-end through `dsf run`.

The silent-zero pattern — a typo'd attribute or element name reads as 0, a
missing table interpolates 0 — lets a sim run while being quietly wrong.
Validation diffs the deck against what the models actually read, and strict
mode is the DEFAULT:

- a deck with findings is refused (exit != 0) with a verbose banner,
- `--not-strict` or `<sim strict="false">` opts out (findings still warn).

The unit-level walker is covered without sixdof in test/test_util.cpp
(test_config_validation); these tests exercise the full pipeline, so they
skip when the model library is absent. gps_typo.xml is gps_1hr.xml with
`rpt` misspelled `rptt` and `<eccentricity>` misspelled `<eccentricty>`.
"""
import os
import subprocess

import pytest

from tests.conftest import FIXTURES_DIR, REPO_ROOT, require_sixdof

GPS_CLEAN = os.path.join(FIXTURES_DIR, "gps_1hr.xml")
GPS_TYPO = os.path.join(FIXTURES_DIR, "gps_typo.xml")


def run_dsf(args, cwd):
    env = os.environ.copy()
    build_dir = os.path.join(REPO_ROOT, "build")
    env["LD_LIBRARY_PATH"] = f"{build_dir}:{env.get('LD_LIBRARY_PATH', '')}"
    return subprocess.run(["dsf", "run", *args], cwd=cwd,
                          capture_output=True, text=True, env=env)


def test_typo_deck_refused_by_default_with_banner(tmp_path):
    require_sixdof()
    res = run_dsf([GPS_TYPO], str(tmp_path))
    assert res.returncode != 0
    out = res.stdout + res.stderr
    # The findings, with names, so the fix is obvious...
    assert "[config] UNUSED" in out
    assert "rptt" in out
    assert "eccentricty" in out
    # ...and the new-default banner with both opt-outs.
    assert "CONFIG VALIDATION FAILED" in out
    assert "--not-strict" in out
    assert 'strict="false"' in out
    assert "Simulation complete" not in out


def test_typo_deck_not_strict_flag_runs(tmp_path):
    require_sixdof()
    res = run_dsf([GPS_TYPO, "--not-strict"], str(tmp_path))
    assert res.returncode == 0, res.stdout + res.stderr
    out = res.stdout + res.stderr
    assert "[config] UNUSED" in out          # still warned, loudly
    assert "CONFIG VALIDATION FAILED" not in out
    assert "Simulation complete" in out


def test_typo_deck_strict_false_attr_runs(tmp_path):
    require_sixdof()
    deck = tmp_path / "typo_not_strict.xml"
    deck.write_text(
        open(GPS_TYPO).read().replace("<sim ", '<sim strict="false" ', 1))
    res = run_dsf([str(deck)], str(tmp_path))
    assert res.returncode == 0, res.stdout + res.stderr
    assert "Simulation complete" in (res.stdout + res.stderr)


def test_clean_deck_passes_default_strict(tmp_path):
    """The false-positive guard: a correct deck must survive the default."""
    require_sixdof()
    res = run_dsf([GPS_CLEAN], str(tmp_path))
    assert res.returncode == 0, res.stdout + res.stderr
    out = res.stdout + res.stderr
    assert "[config] UNUSED" not in out
    assert "CONFIG VALIDATION FAILED" not in out
    assert "Simulation complete" in out
