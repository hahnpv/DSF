"""
Smoke tests for the untested CLI surface (H3): the `mc` subcommands, the
CZML generator behind `dsf cesium`, and the pure helpers behind
`dsf terrain`.

These commands are pure Python (no dsf_core extension), so they are invoked
in-process with click's CliRunner — unlike the sim tests, which must run in
subprocesses (see conftest.py). Window-opening commands (plot/map/globe) are
only exercised via --help, which must not require a display.
"""
import json
import os
import time

import pytest
from click.testing import CliRunner

from dsf.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


# ── group + per-command help (imports and registration) ────────────────────

def test_cli_group_help_lists_commands(runner):
    res = runner.invoke(cli, ["--help"])
    assert res.exit_code == 0
    for cmd in ("run", "watch", "gui", "plot", "map", "globe",
                "terrain", "cesium", "mc"):
        assert cmd in res.output


@pytest.mark.parametrize("cmd", ["plot", "map", "globe", "terrain", "cesium"])
def test_view_command_help(runner, cmd):
    """--help must work headless (argument validation, no window)."""
    res = runner.invoke(cli, [cmd, "--help"])
    assert res.exit_code == 0


def test_view_command_rejects_missing_file(runner):
    res = runner.invoke(cli, ["plot", "/nonexistent/file.h5"])
    assert res.exit_code != 0


# ── dsf mc ──────────────────────────────────────────────────────────────────

MC_DRAWS = {
    "master_seed": 42,
    "draws": [
        {"mass.sigma": {"distribution": "gaussian", "n_sigma_draw": 0.5},
         "wind.mag": {"distribution": "uniform", "drawn": 3.2}},
        {"mass.sigma": {"distribution": "gaussian", "n_sigma_draw": -2.7},
         "wind.mag": {"distribution": "uniform", "drawn": 1.1}},
    ],
}


def test_mc_template(runner, tmp_path):
    deck = tmp_path / "veh.xml"
    deck.write_text(
        '<sim dt="0.1" tmax="1">'
        '<vehicle id="V1" class="Vehicle"><mass id="M1" class="Mass"/></vehicle>'
        "</sim>")
    res = runner.invoke(cli, ["mc", "template", str(deck)])
    assert res.exit_code == 0
    assert "<monte_carlo" in res.output
    assert 'id="V1"' in res.output
    assert '<dispersion block="M1"' in res.output.replace("<!-- ", "<!--")


def test_mc_template_no_sim_node(runner, tmp_path):
    deck = tmp_path / "bad.xml"
    deck.write_text("<notsim/>")
    res = runner.invoke(cli, ["mc", "template", str(deck)])
    assert res.exit_code == 0
    assert "No <sim> node found" in res.output


def test_mc_status_no_state(runner, tmp_path):
    res = runner.invoke(cli, ["mc", "status", str(tmp_path)])
    assert res.exit_code == 0
    assert "No MC state found" in res.output


def test_mc_results_missing_draws(runner, tmp_path):
    res = runner.invoke(cli, ["mc", "results", str(tmp_path)])
    assert res.exit_code == 0
    assert "No mc_draws.json found" in res.output


def test_mc_results_reports_stats(runner, tmp_path):
    (tmp_path / "mc_draws.json").write_text(json.dumps(MC_DRAWS))
    res = runner.invoke(cli, ["mc", "results", str(tmp_path)])
    assert res.exit_code == 0
    assert "MC Results: 2 cases" in res.output
    assert "Master seed: 42" in res.output
    assert "mass.sigma" in res.output
    assert "wind.mag" in res.output


def test_mc_extremes(runner, tmp_path):
    (tmp_path / "mc_draws.json").write_text(json.dumps(MC_DRAWS))
    res = runner.invoke(cli, ["mc", "extremes", str(tmp_path)])
    assert res.exit_code == 0
    assert "Case    1" in res.output          # the -2.7 sigma draw
    assert "-2.70" in res.output

    res = runner.invoke(cli, ["mc", "extremes", str(tmp_path), "-t", "5.0"])
    assert "No cases with draws exceeding 5.0" in res.output


def test_mc_plot_no_cases_errors(runner, tmp_path):
    res = runner.invoke(cli, ["mc", "plot", str(tmp_path)])
    assert res.exit_code != 0


# ── dsf cesium: CZML generation (headless core of the command) ──────────────

def test_generate_czml_no_h5_returns_error_document(tmp_path):
    from dsf.cli.cesium_view import generate_czml
    deck = tmp_path / "sim.xml"
    deck.write_text('<sim><vehicle name="V" id="V"/></sim>')
    doc = json.loads(generate_czml(str(deck)))
    assert isinstance(doc, list)
    assert doc[0]["id"] == "document"


# ── dsf terrain: pure helpers ───────────────────────────────────────────────

def test_find_newest_h5_prefers_bare_stem(tmp_path):
    from dsf.cli.terrain_view import find_newest_h5
    xml = tmp_path / "run.xml"
    xml.write_text("<sim/>")
    (tmp_path / "run0.h5").write_text("")
    bare = tmp_path / "run.h5"
    bare.write_text("")
    assert find_newest_h5(str(xml)) == str(bare)


def test_find_newest_h5_falls_back_to_newest(tmp_path):
    from dsf.cli.terrain_view import find_newest_h5
    xml = tmp_path / "run.xml"
    xml.write_text("<sim/>")
    old = tmp_path / "run0.h5"
    old.write_text("")
    new = tmp_path / "run1.h5"
    new.write_text("")
    past = time.time() - 100
    os.utime(old, (past, past))
    assert find_newest_h5(str(xml)) == str(new)


def test_find_newest_h5_none_when_empty(tmp_path):
    from dsf.cli.terrain_view import find_newest_h5
    xml = tmp_path / "run.xml"
    xml.write_text("<sim/>")
    assert find_newest_h5(str(xml)) is None


def test_parse_terrain_dir_from_xml(tmp_path):
    from dsf.cli.terrain_view import parse_terrain_dir_from_xml
    deck = tmp_path / "deck.xml"
    deck.write_text(
        '<sim><vehicle><terrain data_dir="/data/tiles"/></vehicle></sim>')
    assert parse_terrain_dir_from_xml(str(deck)) == "/data/tiles"

    deck2 = tmp_path / "deck2.xml"
    deck2.write_text(
        '<sim><vehicle><model class="TerrainModel" data_dir="/dted"/></vehicle></sim>')
    assert parse_terrain_dir_from_xml(str(deck2)) == "/dted"

    deck3 = tmp_path / "deck3.xml"
    deck3.write_text("<sim/>")
    assert parse_terrain_dir_from_xml(str(deck3)) == ""
