"""
Remote MC batch submission: staging, path remapping, records, and fetch.

Transport-free — ssh/rsync are monkeypatched throughout, so these exercise
the contracts that decide whether a remote batch can run at all (which
references get rewritten vs shipped, where results land) rather than the
network.
"""

import json
import shutil
from pathlib import Path

import pytest
from dsf import remote

MC_XML = """<?xml version="1.0"?>
<!-- keep this comment: pushed XML must stay reviewable -->
<sim dt="0.01" tmax="600.0" library="{library}" output="csv">
    <terrain id="Terrain" class="TerrainModel" data_dir="{terrain}" />
    <vehicle id="Vehicle" class="Vehicle" name="Missile">
        <aero id="MissileAero" class="MissileAero" filename="cruise_aero.dat" area="1.2" />
    </vehicle>
    <monte_carlo n="{n}" seed="42" workers="8" output_dir="{out}/">
        <dispersion block="MissileMass" property="mass"
                    distribution="gaussian" sigma="50.0" />
    </monte_carlo>
</sim>
"""


@pytest.fixture
def case(tmp_path):
    """A case dir laid out like the real examples: XML three levels below a
    repo root, with the build and shared data outside it."""
    root = tmp_path / "sixdof"
    case_dir = root / "examples" / "guided_munition" / "cruise"
    case_dir.mkdir(parents=True)
    (root / "build").mkdir()
    (root / "build" / "libsixdof.so.1.0.0").write_text("elf")
    (root / "build" / "libsixdof.so").symlink_to(root / "build" / "libsixdof.so.1.0.0")
    (root / "data" / "terrain").mkdir(parents=True)
    (case_dir / "cruise_aero.dat").write_text("mach cl cd\n")
    (case_dir / "stale_run.h5").write_text("old output")

    xml = case_dir / "case.xml"
    xml.write_text(
        MC_XML.format(
            library="../../../build/libsixdof.so",
            terrain="../../../data/terrain",
            n=250,
            out="mc_results",
        )
    )
    maps = [{"local": str(root), "remote": "/opt/sixdof"}]
    return {"root": root, "dir": case_dir, "xml": xml, "maps": maps}


# ── path classification ───


def test_escaping_refs_are_remapped_and_local_ones_are_not(case, tmp_path):
    info = remote.stage_batch(case["xml"], tmp_path / "staging", case["maps"], echo=lambda *a: None)
    pushed = (tmp_path / "staging" / "case.xml").read_text()

    assert 'library="/opt/sixdof/build/libsixdof.so"' in pushed
    assert 'data_dir="/opt/sixdof/data/terrain"' in pushed
    # a reference INSIDE the case dir is payload, not a remap target
    assert 'filename="cruise_aero.dat"' in pushed
    assert "../../.." not in pushed
    assert {lbl for lbl, _, _ in info["rewrites"]} == {"sim.library", "terrain.data_dir"}


def test_symlinked_library_keeps_its_logical_name(case, tmp_path):
    """The soname symlink must NOT be resolved to libsixdof.so.1.0.0 — the
    remote's build may carry a different version suffix."""
    remote.stage_batch(case["xml"], tmp_path / "staging", case["maps"], echo=lambda *a: None)
    pushed = (tmp_path / "staging" / "case.xml").read_text()
    assert "libsixdof.so.1.0.0" not in pushed
    assert 'library="/opt/sixdof/build/libsixdof.so"' in pushed


def test_pushed_xml_preserves_comments_and_formatting(case, tmp_path):
    remote.stage_batch(case["xml"], tmp_path / "staging", case["maps"], echo=lambda *a: None)
    pushed = (tmp_path / "staging" / "case.xml").read_text()
    assert "keep this comment" in pushed
    assert pushed.startswith('<?xml version="1.0"?>')


def test_unmapped_relative_escape_is_fatal(case, tmp_path):
    with pytest.raises(RuntimeError, match="match no --map root"):
        remote.stage_batch(case["xml"], tmp_path / "staging", maps=[], echo=lambda *a: None)


def test_unmapped_absolute_path_is_kept_with_a_warning(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    xml = case_dir / "case.xml"
    xml.write_text(
        MC_XML.format(
            library="libsixdof.so",  # bare soname: LD_LIBRARY_PATH
            terrain="/usr/share/terrain",  # absolute, unmapped
            n=10,
            out="mc_results",
        )
    )
    info = remote.stage_batch(xml, tmp_path / "staging", maps=[], echo=lambda *a: None)

    pushed = (tmp_path / "staging" / "case.xml").read_text()
    assert 'data_dir="/usr/share/terrain"' in pushed
    assert 'library="libsixdof.so"' in pushed  # no slash: not a path reference
    assert info["kept_absolute"] == [("terrain", "data_dir", "/usr/share/terrain")]


def test_incidental_slashes_are_not_treated_as_paths(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    xml = case_dir / "case.xml"
    xml.write_text(
        '<sim dt="0.01" tmax="10.0" units="m/s" note="Kp/Ki tuning">\n'
        '  <monte_carlo n="5" output_dir="mc_results/" />\n'
        "</sim>\n"
    )
    info = remote.stage_batch(xml, tmp_path / "staging", maps=[], echo=lambda *a: None)
    assert info["rewrites"] == []
    assert info["kept_absolute"] == []


def test_map_to_remote_prefers_the_most_specific_root():
    maps = [{"local": "/x", "remote": "/R"}, {"local": "/x/sub", "remote": "/S"}]
    assert remote.map_to_remote("/x/sub/file.dat", maps) == "/S/file.dat"
    assert remote.map_to_remote("/x/other.dat", maps) == "/R/other.dat"
    assert remote.map_to_remote("/elsewhere/f", maps) is None


# ── payload selection ───


def test_only_sibling_data_files_ship(case, tmp_path):
    info = remote.stage_batch(case["xml"], tmp_path / "staging", case["maps"], echo=lambda *a: None)
    assert set(info["shipped"]) == {"case.xml", "cruise_aero.dat"}
    # prior run output stays home — it is bulk, and the remote regenerates it
    assert not (tmp_path / "staging" / "stale_run.h5").exists()


def test_mc_block_is_required(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    xml = case_dir / "plain.xml"
    xml.write_text('<sim dt="0.01" tmax="10.0"></sim>\n')
    with pytest.raises(RuntimeError, match="No <monte_carlo> block"):
        remote.stage_batch(xml, tmp_path / "staging", maps=[], echo=lambda *a: None)


def test_absolute_output_dir_is_rejected(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    xml = case_dir / "case.xml"
    xml.write_text(
        MC_XML.format(library="libsixdof.so", terrain="terrain", n=10, out="/scratch/mc")
    )
    with pytest.raises(RuntimeError, match="is absolute"):
        remote.stage_batch(xml, tmp_path / "staging", maps=[], echo=lambda *a: None)


def test_case_count_and_output_dir_are_read_from_the_block(case, tmp_path):
    info = remote.stage_batch(case["xml"], tmp_path / "staging", case["maps"], echo=lambda *a: None)
    assert info["n_cases"] == 250
    assert info["output_dir"] == "mc_results"


# ── launch ───


def test_launch_detaches_and_returns_the_pid(case, monkeypatch):
    sent = {}

    class _Res:
        stdout = "48211\n"
        returncode = 0

    def fake_shell(cfg, command, **kw):
        sent["command"] = command
        return _Res()

    monkeypatch.setattr(remote, "remote_shell", fake_shell)
    cfg = {"host": "box", "workspace": "/ws", "dsf_cmd": "dsf", "maps": []}
    pid = remote.launch_batch(cfg, "/ws/b1", "case.xml", workers=32)

    assert pid == "48211"
    # must survive the ssh session: dsf mc run is a blocking foreground command
    assert "setsid" in sent["command"] and "nohup" in sent["command"]
    assert "-j 32" in sent["command"]
    assert "cd /ws/b1" in sent["command"]


# ── fetch ───


def _fetch_setup(tmp_path, monkeypatch):
    record = {
        "name": "b1",
        "host": "box",
        "remote_dir": "/ws/b1",
        "remote_output_dir": "/ws/b1/mc_results",
        "local_dir": str(tmp_path),
        "output_dir": "mc_results",
        "n_cases": 3,
    }
    cfg = {"host": "box", "workspace": "/ws", "dsf_cmd": "dsf", "maps": []}
    calls = []
    monkeypatch.setattr(
        remote, "_rsync", lambda src, dst, extra=(): calls.append((src, dst, list(extra)))
    )
    return cfg, record, calls


def test_summary_fetch_excludes_case_bulk(tmp_path, monkeypatch):
    cfg, record, calls = _fetch_setup(tmp_path, monkeypatch)
    out = remote.fetch_batch(cfg, record, echo=lambda *a: None)

    src, dst, extra = calls[0]
    assert src == "box:/ws/b1/mc_results/"
    assert dst == str(tmp_path / "mc_results") + "/"
    assert "--exclude=*" in extra
    assert any("mc_draws.json" in e for e in extra)
    assert not any("case_" in e for e in extra)
    assert out == tmp_path / "mc_results"


def test_full_fetch_takes_everything(tmp_path, monkeypatch):
    cfg, record, calls = _fetch_setup(tmp_path, monkeypatch)
    remote.fetch_batch(cfg, record, full=True, echo=lambda *a: None)
    _, _, extra = calls[0]
    assert extra == []


def test_case_fetch_cherry_picks_padded_dirs(tmp_path, monkeypatch):
    cfg, record, calls = _fetch_setup(tmp_path, monkeypatch)
    remote.fetch_batch(cfg, record, cases=[3, 17], echo=lambda *a: None)
    _, _, extra = calls[0]
    assert "--include=/case_0003/" in extra
    assert "--include=/case_0017/**" in extra
    assert "--exclude=*" in extra


def test_fetch_shelves_existing_results(tmp_path, monkeypatch):
    cfg, record, calls = _fetch_setup(tmp_path, monkeypatch)
    old = tmp_path / "mc_results"
    old.mkdir()
    (old / "mc_draws.json").write_text('{"prior": true}')

    remote.fetch_batch(cfg, record, echo=lambda *a: None)

    shelf = tmp_path / "mc_results.prefetch0"
    assert json.loads((shelf / "mc_draws.json").read_text()) == {"prior": True}
    assert (tmp_path / "mc_results").exists()


# ── state / records ───


def test_batch_state_survives_a_torn_read(tmp_path, monkeypatch):
    record = {"remote_output_dir": "/ws/b1/mc_results"}
    cfg = {"host": "box"}

    class _Torn:
        returncode = 0
        stdout = '{"status": "run'  # caught mid-write by the running batch

    monkeypatch.setattr(remote, "remote_shell", lambda *a, **k: _Torn())
    assert remote.batch_state(cfg, record) is None


def test_batch_records_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(remote, "BATCHES_PATH", tmp_path / "batches.json")
    cfg = {"host": "box", "workspace": "/ws", "dsf_cmd": "dsf", "maps": []}
    xml = tmp_path / "case" / "case.xml"
    xml.parent.mkdir()
    xml.write_text("<sim/>")
    info = {
        "xml": "case.xml",
        "n_cases": 250,
        "output_dir": "mc_results",
        "rewrites": [],
        "shipped": [],
    }

    rec = remote.record_batch(cfg, "b1", "/ws/b1", xml, info, pid="123")
    assert rec["remote_output_dir"] == "/ws/b1/mc_results"
    assert rec["local_dir"] == str(xml.parent)

    remote.record_batch(cfg, "b2", "/ws/b2", xml, info)
    assert remote.find_batch()["name"] == "b2"
    assert remote.find_batch("b1")["pid"] == "123"
    with pytest.raises(RuntimeError, match="unknown batch"):
        remote.find_batch("nope")


def test_config_requires_host_and_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(remote, "CONFIG_PATH", tmp_path / "remote.json")
    with pytest.raises(RuntimeError, match="dsf remote setup"):
        remote.load_config()

    remote.save_config({"host": "box", "workspace": "/ws"})
    cfg = remote.load_config()
    assert cfg["dsf_cmd"] == "dsf" and cfg["maps"] == []

    remote.save_config({"host": "box"})
    with pytest.raises(RuntimeError, match="'workspace'"):
        remote.load_config()


def test_parse_map_rejects_malformed_specs():
    assert remote.parse_map("/a=/b") == {"local": "/a", "remote": "/b"}
    assert remote.parse_map("/a=/b/") == {"local": "/a", "remote": "/b"}
    for bad in ("/a", "=/b", "/a="):
        with pytest.raises(ValueError):
            remote.parse_map(bad)


# ── payload discovery (refs at any depth, not just siblings) ───

NESTED_XML = """<?xml version="1.0"?>
<sim dt="0.01" tmax="10.0" library="libsixdof.so">
    <terrain id="T" class="TerrainModel" data_dir="data/bathymetry/" />
    <aero id="A" class="Aero" filename="config/6dofTables.dat" />
    <aero id="B" class="Aero" filename="beside.dat" />
    <monte_carlo n="2" seed="42" output_dir="mc_results/" />
</sim>
"""


@pytest.fixture
def nested_case(tmp_path):
    """Both forms the real examples use: a table under config/ and a local
    data directory — neither is a sibling FILE."""
    d = tmp_path / "deck"
    (d / "config").mkdir(parents=True)
    (d / "data" / "bathymetry").mkdir(parents=True)
    (d / "config" / "6dofTables.dat").write_text("tables\n")
    (d / "data" / "bathymetry" / "n47w122.dt2").write_text("tile\n")
    (d / "beside.dat").write_text("aero\n")
    (d / "deck.xml").write_text(NESTED_XML)
    return d / "deck.xml"


def test_subdirectory_table_ships(nested_case, tmp_path):
    """A sibling-only scan dropped this silently and the batch died N times
    on the remote."""
    staging = tmp_path / "staging"
    info = remote.stage_batch(nested_case, staging, maps=[], echo=lambda *a: None)
    assert "config/6dofTables.dat" in info["shipped"]
    assert (staging / "config" / "6dofTables.dat").read_text() == "tables\n"


def test_local_data_directory_ships_whole(nested_case, tmp_path):
    staging = tmp_path / "staging"
    info = remote.stage_batch(nested_case, staging, maps=[], echo=lambda *a: None)
    assert "data/bathymetry" in info["shipped"]
    assert (staging / "data" / "bathymetry" / "n47w122.dt2").exists()


def test_sibling_files_still_ship(nested_case, tmp_path):
    staging = tmp_path / "staging"
    info = remote.stage_batch(nested_case, staging, maps=[], echo=lambda *a: None)
    assert "beside.dat" in info["shipped"]
    assert info["shipped"].count("beside.dat") == 1   # not shipped twice


def test_escaping_data_is_remapped_not_shipped(case, tmp_path):
    """Shared terrain lives on the remote already — remap it, never push it."""
    staging = tmp_path / "staging"
    info = remote.stage_batch(case["xml"], staging, case["maps"], echo=lambda *a: None)
    assert not (staging / "data").exists()
    assert any(lbl == "terrain.data_dir" for lbl, _, _ in info["rewrites"])


def test_bulk_payload_is_reported(nested_case, tmp_path):
    """Without a shared store the data still ships, so its size must be
    visible as it goes — that is what makes an unexpected 10 GB
    interruptible."""
    big = nested_case.parent / "data" / "bathymetry" / "big.dt2"
    big.write_bytes(b"x" * (remote.BULK_PAYLOAD_BYTES + 1))
    lines = []
    info = remote.stage_batch(nested_case, tmp_path / "staging", maps=[],
                              shared_root=None, echo=lines.append)

    assert info["payload_bytes"] > remote.BULK_PAYLOAD_BYTES
    assert any("Ctrl-C" in ln for ln in lines)
    assert any("data/bathymetry/" in ln and "MB" in ln for ln in lines)


def test_small_payload_is_not_warned_about(nested_case, tmp_path):
    lines = []
    remote.stage_batch(nested_case, tmp_path / "staging", maps=[], echo=lines.append)
    assert not any("payload is" in ln for ln in lines)


# ── remote preflight ───

def test_verify_remote_refs_reports_missing_targets(monkeypatch):
    info = {"rewrites": [("sim.library", "../x.so", "/opt/sixdof/build/x.so"),
                         ("terrain.data_dir", "../t", "/opt/sixdof/data/terrain")]}

    class _Res:
        returncode = 0
        stdout = "MISSING:/opt/sixdof/data/terrain\n"
        stderr = ""

    monkeypatch.setattr(remote, "remote_shell", lambda *a, **k: _Res())
    assert remote.verify_remote_refs({"host": "box"}, info) == ["/opt/sixdof/data/terrain"]


def test_verify_remote_refs_noop_without_rewrites(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("must not ssh when there is nothing to check")

    monkeypatch.setattr(remote, "remote_shell", _boom)
    assert remote.verify_remote_refs({"host": "box"}, {"rewrites": []}) == []


# ── bulk data: shared store instead of per-batch copies ───

BULK_XML = """<?xml version="1.0"?>
<sim dt="0.01" tmax="10.0" library="libsixdof.so">
    <terrain id="T" class="TerrainModel" data_dir="data/bathymetry/" />
    <aero id="A" class="Aero" filename="aero.dat" />
    <monte_carlo n="2" seed="42" output_dir="mc_results/" />
</sim>
"""


@pytest.fixture
def bulk_deck(tmp_path):
    d = tmp_path / "deck"
    (d / "data" / "bathymetry").mkdir(parents=True)
    (d / "data" / "bathymetry" / "tile.dt2").write_bytes(b"x" * (remote.BULK_PAYLOAD_BYTES + 1))
    (d / "aero.dat").write_text("small\n")
    (d / "deck.xml").write_text(BULK_XML)
    return d / "deck.xml"


def test_bulk_data_is_routed_to_the_shared_store(bulk_deck, tmp_path):
    """Tiles must not be copied into the batch — the deck points at the
    store, so the next batch naming them reuses the upload."""
    staging = tmp_path / "staging"
    info = remote.stage_batch(bulk_deck, staging, maps=[], shared_root="/ws/_shared",
                              echo=lambda *a: None)

    assert [e["rel"] for e in info["shared"]] == ["data/bathymetry"]
    assert not (staging / "data").exists()
    pushed = (staging / "deck.xml").read_text()
    assert f'data_dir="/ws/_shared/{info["shared"][0]["key"]}"' in pushed
    assert "aero.dat" in info["shipped"]      # small payload still rides along


def test_same_dataset_gets_the_same_key_across_decks(tmp_path):
    """Two decks in different directories naming identical data must agree
    on the key, or the dedup never fires."""
    keys = []
    for name in ("deck_a", "deck_b"):
        d = tmp_path / name / "data" / "bathymetry"
        d.mkdir(parents=True)
        (d / "tile.dt2").write_bytes(b"x" * 4096)
        keys.append(remote.content_key(d))
    assert keys[0] == keys[1]


def test_changed_dataset_gets_a_new_key(tmp_path):
    d = tmp_path / "bathymetry"
    d.mkdir()
    (d / "tile.dt2").write_bytes(b"x" * 4096)
    before = remote.content_key(d)
    (d / "tile.dt2").write_bytes(b"x" * 8192)
    assert remote.content_key(d) != before


def test_small_payload_never_goes_to_the_store(tmp_path):
    refs = [Path("aero.dat")]
    (tmp_path / "aero.dat").write_text("small")
    inline, shared = remote.plan_shared(refs, tmp_path, "/ws/_shared")
    assert inline == refs and shared == []


def test_no_store_without_a_shared_root(bulk_deck, tmp_path):
    """Without a configured store the old behaviour stands: it ships."""
    info = remote.stage_batch(bulk_deck, tmp_path / "staging", maps=[],
                              shared_root=None, echo=lambda *a: None)
    assert info["shared"] == []
    assert "data/bathymetry" in info["shipped"]


def test_push_shared_skips_what_is_already_there(monkeypatch):
    info = {"shared": [{"rel": "data/bathymetry", "local": "/l/data/bathymetry",
                        "remote": "/ws/_shared/bathymetry-abc", "bytes": 12, "key": "bathymetry-abc"}]}
    rsyncs = []

    class _Present:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(remote, "remote_shell", lambda *a, **k: _Present())
    monkeypatch.setattr(remote, "_rsync", lambda *a, **k: rsyncs.append(a))
    lines = []
    assert remote.push_shared({"host": "box"}, info, echo=lines.append, progress=False) == []
    assert rsyncs == [], "an entry already in the store must not be re-uploaded"
    assert any("reuse" in ln for ln in lines)


def test_push_shared_lands_via_incoming_then_renames(monkeypatch):
    """A store entry must never be half-populated: the next batch decides to
    skip the upload purely by finding the directory there."""
    info = {"shared": [{"rel": "data/bathymetry", "local": "/l/data/bathymetry",
                        "remote": "/ws/_shared/bathymetry-abc", "bytes": 12, "key": "bathymetry-abc"}]}
    commands, rsyncs = [], []

    class _Absent:
        returncode = 1
        stdout = ""

    def fake_shell(cfg, command, **kw):
        commands.append(command)
        return _Absent()

    monkeypatch.setattr(remote, "remote_shell", fake_shell)
    monkeypatch.setattr(remote, "_rsync", lambda src, dst, **k: rsyncs.append((src, dst)))
    remote.push_shared({"host": "box"}, info, echo=lambda *a: None, progress=False)

    assert rsyncs and rsyncs[0][1].endswith(".incoming/")
    mv = [c for c in commands if c.startswith("mv ")]
    assert mv and mv[0].endswith("/ws/_shared/bathymetry-abc")


def test_discard_remote_removes_partials(monkeypatch):
    commands = []
    monkeypatch.setattr(remote, "remote_shell",
                        lambda cfg, command, **k: commands.append(command))
    remote.discard_remote({"host": "box"}, ["/ws/b1", "/ws/_shared/x.incoming", None])
    assert commands == ["rm -rf /ws/b1", "rm -rf /ws/_shared/x.incoming"]


# ── interrupting the transfer ───

def test_ctrl_c_during_transfer_cleans_both_ends(tmp_path, monkeypatch):
    """Ctrl-C mid-push must leave no partial batch on the remote and no
    staging copy locally."""
    import tempfile

    from click.testing import CliRunner

    from dsf.cli import remote_cli

    deck_dir = tmp_path / "deck"
    deck_dir.mkdir()
    xml = deck_dir / "deck.xml"
    xml.write_text(MC_XML.format(library="libsixdof.so", terrain="terrain", n=4,
                                 out="mc_results"))

    monkeypatch.setattr(remote, "load_config",
                        lambda: {"host": "box", "workspace": "/ws", "dsf_cmd": "dsf", "maps": []})
    monkeypatch.setattr(remote, "stage_batch",
                        lambda *a, **k: {"xml": "deck.xml", "n_cases": 4,
                                         "output_dir": "mc_results", "rewrites": [],
                                         "shipped": ["deck.xml"], "kept_absolute": [],
                                         "payload_bytes": 10, "shared": []})
    monkeypatch.setattr(remote, "verify_remote_refs", lambda *a, **k: [])
    monkeypatch.setattr(remote, "push_shared", lambda *a, **k: [])

    def _interrupt(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(remote, "push_batch", _interrupt)
    discarded = []
    monkeypatch.setattr(remote, "discard_remote",
                        lambda cfg, paths: discarded.extend(paths))
    launched = []
    monkeypatch.setattr(remote, "launch_batch", lambda *a, **k: launched.append(a) or "1")

    staged = []
    real_mkdtemp = tempfile.mkdtemp
    monkeypatch.setattr(tempfile, "mkdtemp",
                        lambda **kw: staged.append(real_mkdtemp(**kw)) or staged[-1])

    result = CliRunner().invoke(remote_cli.remote, ["run", str(xml), "--no-sync-check"])

    assert result.exit_code == 130
    assert launched == [], "an interrupted transfer must not start the batch"
    assert len(discarded) == 1 and discarded[0].startswith("/ws/")
    assert staged and not Path(staged[0]).exists()
    assert "Cancelled" in result.output


# ── garbage collection ───

def _gc_shell(listing, refs):
    class _Res:
        returncode = 0
        stdout = listing + "---REFS---" + refs
        stderr = ""

    return lambda *a, **k: _Res()


def test_scan_shared_store_splits_listing_from_references(monkeypatch):
    monkeypatch.setattr(remote, "remote_shell", _gc_shell(
        "12582912\t/ws/_shared/bathy-aaa\n4096\t/ws/_shared/terrain-bbb\n",
        '\n_shared/bathy-aaa\n_shared/bathy-aaa\n'))
    entries, referenced = remote.scan_shared_store({"workspace": "/ws"})

    assert [e["key"] for e in entries] == ["bathy-aaa", "terrain-bbb"]
    assert entries[0]["bytes"] == 12582912
    assert referenced == {"bathy-aaa"}


def test_gc_reports_without_deleting_by_default(monkeypatch):
    monkeypatch.setattr(remote, "remote_shell", _gc_shell(
        "4096\t/ws/_shared/live-aaa\n8192\t/ws/_shared/dead-bbb\n",
        "\n_shared/live-aaa\n"))
    removed = []
    monkeypatch.setattr(remote, "discard_remote", lambda cfg, paths: removed.extend(paths))

    lines = []
    removable, freed = remote.gc_shared({"workspace": "/ws"}, echo=lines.append)

    assert [e["key"] for e in removable] == ["dead-bbb"] and freed == 8192
    assert removed == [], "report mode must not delete"
    assert any("--delete" in ln for ln in lines)


def test_gc_delete_removes_orphans_and_incoming(monkeypatch):
    monkeypatch.setattr(remote, "remote_shell", _gc_shell(
        "4096\t/ws/_shared/live-aaa\n8192\t/ws/_shared/dead-bbb\n"
        "512\t/ws/_shared/half-ccc.incoming\n",
        "\n_shared/live-aaa\n"))
    removed = []
    monkeypatch.setattr(remote, "discard_remote", lambda cfg, paths: removed.extend(paths))

    removable, freed = remote.gc_shared({"workspace": "/ws"}, delete=True,
                                        echo=lambda *a: None)

    assert removed == ["/ws/_shared/dead-bbb", "/ws/_shared/half-ccc.incoming"]
    assert freed == 8704


def test_gc_keeps_an_entry_referenced_by_any_deck(monkeypatch):
    """One surviving reference is enough — collecting it would break that
    batch's decks."""
    monkeypatch.setattr(remote, "remote_shell", _gc_shell(
        "4096\t/ws/_shared/shared-aaa\n", "\n_shared/shared-aaa\n"))
    removable, freed = remote.gc_shared({"workspace": "/ws"}, delete=True,
                                        echo=lambda *a: None)
    assert removable == [] and freed == 0


def test_batch_usage_excludes_the_store(monkeypatch):
    class _Res:
        returncode = 0
        stdout = "1024\t/ws/batch_a/\n2048\t/ws/batch_b/\n"
        stderr = ""

    monkeypatch.setattr(remote, "remote_shell", lambda *a, **k: _Res())
    usage = remote.batch_disk_usage({"workspace": "/ws"})
    assert [(b["name"], b["bytes"]) for b in usage] == [("batch_a", 1024), ("batch_b", 2048)]


# ── garbage collection, end to end ───
#
# The tests above mock the shell, so they pin the DECISION but never prove a
# real rm -rf lands on the right directory. These run the actual thing
# against a real workspace with localhost standing in for the remote —
# everything but the ssh hop is the production path.


@pytest.fixture
def local_remote(monkeypatch, tmp_path):
    """cfg whose 'remote' is this filesystem: same commands, no ssh."""
    import subprocess

    class _Res:
        def __init__(self, cp):
            self.returncode, self.stdout, self.stderr = cp.returncode, cp.stdout, cp.stderr

    def shell(cfg, command, tty=False, check=True):
        cp = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
        if check and cp.returncode != 0:
            raise RuntimeError(cp.stderr)
        return _Res(cp)

    def strip_host(path):
        return path.split(":", 1)[1] if path.startswith("box:") else path

    def rsync(src, dst, extra=(), progress=False):
        return subprocess.run(
            ["rsync", "-az", "--safe-links", *extra, strip_host(src), strip_host(dst)],
            check=True, capture_output=True, text=True)

    monkeypatch.setattr(remote, "remote_shell", shell)
    monkeypatch.setattr(remote, "_rsync", rsync)
    monkeypatch.setattr(remote, "BULK_PAYLOAD_BYTES", 1024)   # keep the fixtures small
    ws = tmp_path / "ws"
    ws.mkdir()
    return {"host": "box", "workspace": str(ws), "dsf_cmd": "dsf", "maps": []}


GC_DECK = """<sim dt="0.01" tmax="10.0" library="libsixdof.so">
  <terrain id="T" class="TerrainModel" data_dir="data/tiles/" />
  <monte_carlo n="2" seed="42" output_dir="mc_out/" />
</sim>
"""


def _push(cfg, tmp_path, name, filler):
    """Stage and push a batch whose terrain goes to the shared store."""
    d = tmp_path / "decks" / name / "data" / "tiles"
    d.mkdir(parents=True)
    (d / "tile.dt2").write_bytes(filler)
    xml = tmp_path / "decks" / name / f"{name}.xml"
    xml.write_text(GC_DECK)

    staging = tmp_path / "staging" / name
    info = remote.stage_batch(xml, staging, maps=[],
                              shared_root=f"{cfg['workspace']}/_shared",
                              echo=lambda *a: None)
    remote.push_shared(cfg, info, echo=lambda *a: None, progress=False)
    remote.push_batch(cfg, staging, name)
    return info


def test_gc_end_to_end_collects_only_real_orphans(local_remote, tmp_path):
    cfg = local_remote
    ws = Path(cfg["workspace"])
    shared = ws / "_shared"

    live = _push(cfg, tmp_path, "batch_live", b"x" * 4096)
    dead = _push(cfg, tmp_path, "batch_dead", b"y" * 8192)
    shutil.rmtree(ws / "batch_dead")                      # its data is now orphaned
    (shared / "tiles-deadbeef.incoming").mkdir()          # interrupted upload debris
    (shared / "tiles-deadbeef.incoming" / "half.dt2").write_bytes(b"z" * 64)

    assert len(list(shared.iterdir())) == 3

    # report mode must not touch the filesystem
    removable, freed = remote.gc_shared(cfg, echo=lambda *a: None)
    assert {e["key"] for e in removable} == {dead["shared"][0]["key"], "tiles-deadbeef.incoming"}
    assert len(list(shared.iterdir())) == 3, "report mode deleted something"

    removable, freed = remote.gc_shared(cfg, delete=True, echo=lambda *a: None)
    left = sorted(p.name for p in shared.iterdir())
    assert left == [live["shared"][0]["key"]]
    assert freed >= 8192
    assert (ws / "batch_live").exists(), "gc must never remove batch output"

    # and it is idempotent
    assert remote.gc_shared(cfg, delete=True, echo=lambda *a: None) == ([], 0)


def test_gc_end_to_end_keeps_data_two_batches_share(local_remote, tmp_path):
    """The dedup case: removing an entry because ONE referring batch went
    away would break the batches that still point at it."""
    cfg = local_remote
    ws = Path(cfg["workspace"])

    a = _push(cfg, tmp_path, "batch_a", b"x" * 4096)
    b = _push(cfg, tmp_path, "batch_b", b"x" * 4096)      # identical data -> same key
    assert a["shared"][0]["key"] == b["shared"][0]["key"]

    shutil.rmtree(ws / "batch_a")
    removable, freed = remote.gc_shared(cfg, delete=True, echo=lambda *a: None)

    assert removable == [] and freed == 0
    assert (ws / "_shared" / b["shared"][0]["key"] / "tile.dt2").exists()
