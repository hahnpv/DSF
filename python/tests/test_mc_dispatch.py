"""
Tests for the dsf.mc Monte Carlo dispatcher (no sims are run — pure
draw/XML-patching logic, so no model library or C++ extension is needed).

Pins the dispersion-honesty contract (ROADMAP R3): the values recorded in
mc_draws.json are transmitted into each case's XML verbatim, so the C++
engine applies exactly what the dispatcher reports. The C++ half of the
contract is pinned by test/test_monte_carlo.cpp (cpp_mc_tests).
"""

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from dsf.mc import MonteCarlo, draw_stats, extreme_draws, load_draws


DECK = """<sim dt="0.1" tmax="1.0" library="libfake.so">
  <vehicle class="Vehicle" id="V1">
    <prop id="Engine" class="RocketProp" thrust="1000.0"/>
  </vehicle>
  <monte_carlo n="8" seed="42" workers="2" output_dir="{outdir}">
    <dispersion block="Engine" property="thrust" distribution="gaussian" sigma="50.0"/>
    <dispersion block="Engine" property="isp" distribution="uniform" min="290.0" max="310.0"/>
  </monte_carlo>
</sim>
"""


@pytest.fixture
def mc(tmp_path):
    deck = tmp_path / "deck.xml"
    deck.write_text(DECK.format(outdir=str(tmp_path / "mc_out")))
    return MonteCarlo(str(deck))


def test_pre_draw_deterministic(mc, tmp_path):
    """Same master seed → identical pre-draws (reproducible batches)."""
    deck2 = tmp_path / "deck2.xml"
    deck2.write_text(DECK.format(outdir=str(tmp_path / "mc_out2")))
    mc2 = MonteCarlo(str(deck2))
    assert mc.draws == mc2.draws
    assert len(mc.draws) == 8


def test_case_xml_carries_the_draws(mc):
    """The per-case XML transmits this case's pre-drawn values on the
    <dispersion> elements — the C++ engine applies them verbatim, which is
    what makes mc_draws.json honest."""
    for case_id in (0, 3, 7):
        xml_path, case_dir, case_seed = mc._make_case_xml(case_id)
        root = ET.parse(xml_path).getroot()
        sim = root if root.tag == "sim" else root.find(".//sim")

        # Case identity for the C++ engine (and dsf run's SimSession).
        assert int(sim.get("case_id")) == case_id
        assert int(sim.get("seed")) == case_seed

        dnodes = sim.find("monte_carlo").findall("dispersion")
        gauss = next(d for d in dnodes if d.get("property") == "thrust")
        uni = next(d for d in dnodes if d.get("property") == "isp")

        recorded = mc.draws[case_id]
        assert float(gauss.get("n_sigma_draw")) == recorded["Engine.thrust"]["n_sigma_draw"]
        assert float(uni.get("drawn")) == recorded["Engine.isp"]["drawn"]
        # Uniform draws must respect the deck's bounds.
        assert 290.0 <= float(uni.get("drawn")) <= 310.0


def test_construction_needs_no_executable(tmp_path):
    """Draw/analysis use must not require the C++ `dynamic` binary — it is
    resolved lazily by run()."""
    deck = tmp_path / "deck.xml"
    deck.write_text(DECK.format(outdir=str(tmp_path / "mc_out")))
    mc = MonteCarlo(str(deck))
    assert mc.dynamic_bin is None


def test_draw_stats_and_extremes_roundtrip(mc, tmp_path):
    """The shared helpers (used by both MonteCarlo and the CLI) agree with
    the recorded draws."""
    outdir = tmp_path / "batch"
    outdir.mkdir()
    (outdir / "mc_draws.json").write_text(json.dumps({
        "master_seed": mc.master_seed,
        "n_cases": mc.n_cases,
        "dispersions": mc.dispersions,
        "draws": mc.draws,
    }))

    data = load_draws(outdir)
    assert data["n_cases"] == 8
    assert data["draws"] == mc.draws

    stats = draw_stats(data["draws"])
    assert stats["Engine.thrust"]["distribution"] == "gaussian"
    # n_sigma draws over 8 cases: bounded sanity, not distribution tests.
    assert -5.0 < stats["Engine.thrust"]["mean"] < 5.0
    assert 290.0 <= stats["Engine.isp"]["min"] <= stats["Engine.isp"]["max"] <= 310.0

    # extremes: threshold 0 flags every nonzero gaussian draw, sorted by |σ|.
    ex = extreme_draws(data["draws"], threshold_sigma=0.0)
    assert ex and all(e["parameter"] == "Engine.thrust" for e in ex)
    mags = [abs(e["n_sigma"]) for e in ex]
    assert mags == sorted(mags, reverse=True)
    # MonteCarlo.extremes delegates to the same helper.
    assert mc.extremes(threshold_sigma=0.0) == extreme_draws(mc.draws, 0.0)


def test_load_draws_missing_dir(tmp_path):
    assert load_draws(tmp_path) is None


# ── path anchoring (relative refs survive the move into case dirs) ──

PATH_DECK = """<sim dt="0.1" tmax="1.0" library="{library}" units="m/s">
  <terrain id="Terrain" class="TerrainModel" data_dir="{terrain}"/>
  <vehicle class="Vehicle" id="V1" name="GPS_BIIA-23_(PRN_18)">
    <aero id="A1" class="Aero" filename="table.dat"/>
  </vehicle>
  <monte_carlo n="2" seed="42" workers="1" output_dir="{outdir}">
    <dispersion block="A1" property="area" distribution="gaussian" sigma="1.0"/>
  </monte_carlo>
</sim>
"""


def _path_case(tmp_path, library="../lib/libfake.so"):
    """A deck laid out like the real examples: shared assets live OUTSIDE
    the deck dir, reached by relative paths that escape it."""
    deck_dir = tmp_path / "examples" / "cruise"
    deck_dir.mkdir(parents=True)
    (tmp_path / "examples" / "lib").mkdir()
    (tmp_path / "examples" / "lib" / "libfake.so").write_text("elf")
    (tmp_path / "examples" / "terrain").mkdir()
    (deck_dir / "table.dat").write_text("mach cl cd\n")

    deck = deck_dir / "deck.xml"
    deck.write_text(PATH_DECK.format(library=library, terrain="../terrain",
                                     outdir="mc_out/"))
    mc = MonteCarlo(str(deck))
    xml_path, case_dir, _ = mc._make_case_xml(0)
    root = ET.parse(xml_path).getroot()
    return tmp_path, root, Path(case_dir)


def test_relative_paths_are_anchored_on_the_deck_dir(tmp_path):
    """The case runs two levels below the deck, so a relative reference in
    the deck resolves to nothing from there — every case would die on load."""
    _, root, _ = _path_case(tmp_path)
    lib = root.get("library")
    terrain = root.find("terrain").get("data_dir")

    assert lib == str(tmp_path / "examples" / "lib" / "libfake.so")
    assert terrain == str(tmp_path / "examples" / "terrain")
    assert ".." not in lib and ".." not in terrain
    assert Path(lib).exists() and Path(terrain).exists()


def test_deck_local_data_files_are_anchored_too(tmp_path):
    _, root, case_dir = _path_case(tmp_path)
    fname = root.find(".//aero").get("filename")
    assert fname == str(tmp_path / "examples" / "cruise" / "table.dat")
    assert Path(fname).exists()
    # the sibling symlink stays as a fallback for CWD-relative reads
    assert (case_dir / "table.dat").exists()


def test_bare_soname_is_left_for_the_dynamic_linker(tmp_path):
    """`library="libsixdof.so"` must stay bare so LD_LIBRARY_PATH resolves
    it — rewriting it would pin one build of the model library."""
    _, root, _ = _path_case(tmp_path, library="libsixdof.so")
    assert root.get("library") == "libsixdof.so"


def test_non_path_attributes_are_untouched(tmp_path):
    """Incidental slashes and names must not be mistaken for paths."""
    _, root, _ = _path_case(tmp_path)
    assert root.get("units") == "m/s"
    assert root.find("vehicle").get("name") == "GPS_BIIA-23_(PRN_18)"
    assert root.get("dt") == "0.1"


def test_absolute_paths_pass_through_unchanged(tmp_path):
    _, root, _ = _path_case(tmp_path, library="/usr/lib/libfake.so")
    assert root.get("library") == "/usr/lib/libfake.so"
