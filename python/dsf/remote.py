"""
Remote Monte Carlo runs — submit DSF batches to a bigger box over ssh.

The client (laptop) pushes a case directory, launches `dsf mc run` detached
on the remote, polls `dsf mc status`, and pulls results back. SSH and rsync
are the only transport: no server, no open ports, no daemon. There is
nothing to install remotely beyond a working DSF.

Two path problems make this more than "rsync a directory", and both are
handled at staging time:

  * References that stay INSIDE the case dir (aero tables named by
    `filename="cruise_aero.dat"`) are payload — they travel with the batch.

  * References that ESCAPE it (`library="../../../build/libsixdof.so"`,
    `data_dir="../../../data/terrain"`) point at build artifacts and
    multi-GB shared data that already exist on the remote. Shipping them is
    wrong (a laptop .so will not run there) or ruinous (terrain tiles). They
    are REWRITTEN to remote-absolute paths using the configured root maps —
    e.g. local ~/sixdof -> remote /opt/sixdof. Only the pushed
    copy of the XML is rewritten; the local original is never touched.

An escaping reference with no matching map is a hard error at staging: the
alternative is a batch that dies 1000 times on the remote for want of one
path.

Config lives in ~/.dsf/remote.json; batch bookkeeping in
~/.dsf/remote_batches.json.
"""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

CONFIG_PATH = Path.home() / ".dsf" / "remote.json"
BATCHES_PATH = Path.home() / ".dsf" / "remote_batches.json"

# Data files the MC dispatcher symlinks into each case dir (mc.py
# _make_case_xml), plus the config itself — these travel with the batch.
PAYLOAD_SUFFIXES = (".dat", ".dt2", ".tbl", ".xml", ".csv", ".json")

# Aggregate artifacts a summary fetch pulls back: everything `dsf mc
# results` / `extremes` / `status` read, none of the per-case bulk.
SUMMARY_FILES = (".dsf_mc.json", "mc_draws.json", "mc_index.json")

# Aero/table payloads run to a few MB. Past this it is bulk data — terrain
# or bathymetry tiles — which belongs on the remote once, reached by a --map
# root, not pushed with every batch.
BULK_PAYLOAD_BYTES = 10 * 1024 * 1024


# ─── config ───


def load_config():
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"No remote configured ({CONFIG_PATH} missing). Run:\n"
            "  dsf remote setup --host <ssh-host> --workspace <dir> "
            "--map <local-root>=<remote-root>"
        )
    cfg = json.loads(CONFIG_PATH.read_text())
    for key in ("host", "workspace"):
        if not cfg.get(key):
            raise RuntimeError(f"{CONFIG_PATH} is missing required key '{key}'")
    cfg.setdefault("dsf_cmd", "dsf")
    cfg.setdefault("maps", [])
    return cfg


def save_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")


def parse_map(spec):
    """'~/sixdof=/opt/sixdof' -> {'local':..., 'remote':...}."""
    if "=" not in spec:
        raise ValueError(f"bad --map {spec!r} — expected <local-root>=<remote-root>")
    local, remote = spec.split("=", 1)
    if not local or not remote:
        raise ValueError(f"bad --map {spec!r} — both sides are required")
    return {"local": str(Path(local).expanduser().resolve()), "remote": remote.rstrip("/")}


# ─── transport ───


def _run(cmd, check=True):
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def remote_shell(cfg, command, tty=False, check=True):
    """Run `command` on the remote through a LOGIN shell.

    `bash -lc` so the user's profile applies: DSF needs conda/PATH and
    LD_LIBRARY_PATH for the model libs a sim dlopen's, none of which a bare
    non-interactive ssh exec would set.
    """
    ssh = ["ssh"]
    if tty and sys.stdout.isatty():
        ssh.append("-t")
    ssh += [cfg["host"], f"bash -lc {shlex.quote(command)}"]
    if tty:
        return subprocess.call(ssh)
    return _run(ssh, check=check)


def remote_dsf(cfg, args, tty=False):
    """Run `dsf <args...>` remotely; prints output, returns the exit code."""
    cmd = cfg["dsf_cmd"] + " " + " ".join(shlex.quote(a) for a in args)
    if tty:
        return remote_shell(cfg, cmd, tty=True)
    res = remote_shell(cfg, cmd, check=False)
    if res.stdout:
        print(res.stdout.rstrip())
    if res.stderr.strip():
        print(res.stderr.rstrip(), file=sys.stderr)
    return res.returncode


def _rsync(src, dst, extra=(), progress=False):
    """rsync with the flags every transfer here needs.

    --safe-links: the MC dispatcher symlinks data files into every case dir
    with ABSOLUTE targets. Those are meaningless on the other machine, so
    skip them rather than transfer dangling links (or, with -L, copy a
    multi-MB aero table into 1000 case dirs).

    progress: stream a live byte counter instead of capturing output, so a
    transfer that turns out to be far bigger than expected is visible while
    it runs and can be interrupted.
    """
    cmd = ["rsync", "-az", "--safe-links", *extra, src, dst]
    if progress:
        cmd.insert(1, "--info=progress2")
        return subprocess.run(cmd, check=True)
    return _run(cmd)


def interactive():
    """True when someone is at the terminal to watch a transfer and stop it."""
    return sys.stdout.isatty()


# ─── version sync ───


def _git_head(path):
    res = _run(["git", "-C", str(path), "rev-parse", "HEAD"], check=False)
    return res.stdout.strip() if res.returncode == 0 else None


def sync_check(cfg):
    """Compare DSF/sixdof git HEADs across the two machines.

    Returns (verdict, lines): 'ok' | 'mismatch' | 'unknown'. Unlike traj,
    the physics here is a COMPILED artifact — matching SHAs only prove the
    sources agree, not that either side rebuilt. The caller says so.
    """
    lines = []
    verdict = "ok"
    checked = 0

    for m in cfg.get("maps", []):
        local_root, remote_root = Path(m["local"]), m["remote"]
        local_sha = _git_head(local_root)
        if local_sha is None:
            continue  # not a git checkout — nothing to compare
        res = remote_shell(cfg, f"git -C {shlex.quote(remote_root)} rev-parse HEAD", check=False)
        remote_sha = res.stdout.strip() if res.returncode == 0 else None
        if not remote_sha:
            lines.append(f"{remote_root}: not a git checkout on the remote — skipped")
            continue
        checked += 1
        if local_sha == remote_sha:
            lines.append(f"{local_root.name}: {local_sha[:12]} (match)")
        else:
            verdict = "mismatch"
            lines.append(
                f"{local_root.name}: local {local_sha[:12]} != "
                f"remote {remote_sha[:12]}  ({local_root} vs {remote_root})"
            )

    if not checked:
        return "unknown", lines or ["no git-backed root maps to compare"]
    return verdict, lines


# ─── staging ───


def _logical(path):
    """Normalize '..' segments WITHOUT following symlinks.

    Path.resolve() would rewrite build/libsixdof.so to its versioned target
    (libsixdof.so.1.0.0), pinning the pushed XML to a soname the remote's
    own build may not carry. The logical path is what the config author
    wrote and what must be reproduced on the other machine.
    """
    return Path(os.path.normpath(str(path)))


def map_to_remote(local_path, maps):
    """Remote-absolute equivalent of a local path under a configured root.

    Returns None if the path falls under no map. Longest local root wins, so
    nested maps (/x and /x/sub) resolve to the most specific. Matching tries
    the logical path first, then the symlink-resolved one — a map root that
    is itself a symlink (~/sixdof -> /mnt/data/sixdof) still matches —
    but the rewrite always carries the LOGICAL tail.
    """
    logical = _logical(local_path)
    candidates = [logical]
    real = Path(local_path).resolve()
    if real != logical:
        candidates.append(real)

    for m in sorted(maps, key=lambda m: len(m["local"]), reverse=True):
        root = Path(m["local"])
        for cand in candidates:
            try:
                rel = cand.relative_to(root)
            except ValueError:
                continue
            return f"{m['remote']}/{rel}" if str(rel) != "." else m["remote"]
    return None


def _all_path_refs(xml_path):
    """Every attribute value that names a real path, classified.

    Yields (element, attribute, value, logical_path, kind) where kind is
    'absolute' | 'escaping' | 'local'. Scans every attribute of every
    element: DSF spreads path references across `library`, `filename`,
    `data_dir`, and model-specific attrs, so an allowlist of attribute names
    would silently miss one.

    A relative value counts as a path only if it EXISTS under the deck dir —
    that is what keeps incidental slashes (`units="m/s"`) out. Slash-free
    values are never paths here: a bare soname must stay bare so the remote's
    dynamic linker resolves it against its own build.
    """
    case_dir = _logical(Path(xml_path).parent.resolve())
    tree = ET.parse(str(xml_path))
    out = []
    for elem in tree.getroot().iter():
        for attr, value in elem.attrib.items():
            if not value or "/" not in value:
                continue
            candidate = Path(value)
            if candidate.is_absolute():
                out.append((elem, attr, value, _logical(candidate), "absolute"))
                continue
            logical = _logical(case_dir / candidate)
            try:
                logical.relative_to(case_dir)
            except ValueError:
                out.append((elem, attr, value, logical, "escaping"))
                continue
            if logical.exists():
                out.append((elem, attr, value, logical, "local"))
    return out


def _escaping_refs(xml_path):
    """Refs the remote cannot resolve as written: escapes and absolutes."""
    return [
        (e, a, v, p, kind == "absolute")
        for e, a, v, p, kind in _all_path_refs(xml_path)
        if kind in ("escaping", "absolute")
    ]


def deck_local_refs(xml_path):
    """Paths the deck names that live INSIDE its own directory — payload.

    A plain sibling scan misses these: a table in a subdirectory
    (`filename="config/6dofTables.dat"`) and a local data directory
    (`data_dir="data/bathymetry/"`) are both real forms in the examples, and
    neither is a sibling file. Returns paths relative to the deck dir,
    deduped, in first-appearance order.
    """
    case_dir = _logical(Path(xml_path).parent.resolve())
    seen, out = set(), []
    for _e, _a, _v, logical, kind in _all_path_refs(xml_path):
        if kind != "local":
            continue
        rel = str(logical.relative_to(case_dir))
        if rel in seen:
            continue
        seen.add(rel)
        out.append(Path(rel))
    return out


def content_key(path):
    """Short stable key for a file or directory tree.

    Hashes a manifest of (relative path, size) rather than file CONTENT: a
    terrain set is gigabytes, and re-reading all of it on every submission
    to decide whether to skip an upload would cost more than the upload
    saves. Names plus sizes distinguish real datasets from each other; they
    would not catch an edit that preserves every file size, which is why the
    key is a cache identity, not a checksum.
    """
    path = Path(path)
    if path.is_file():
        manifest = [f"{path.name}:{path.stat().st_size}"]
    else:
        manifest = sorted(
            f"{f.relative_to(path)}:{f.stat().st_size}"
            for f in path.rglob("*")
            if f.is_file()
        )
    digest = hashlib.sha1("\n".join(manifest).encode()).hexdigest()[:12]
    return f"{path.name}-{digest}"


def plan_shared(refs, deck_dir, shared_root, threshold=None):
    """Split deck-local payload into (ships with the batch, goes to the store).

    Anything at or above the threshold is placed in a content-addressed
    shared store on the remote instead of being copied into this batch.
    Batches that reference the same dataset — the same terrain or bathymetry
    tiles, whether a later run of the same deck or a different deck entirely
    — then resolve to one upload rather than one per batch.
    """
    threshold = BULK_PAYLOAD_BYTES if threshold is None else threshold
    inline, shared = [], []
    for rel in refs:
        src = Path(deck_dir) / rel
        size = _path_size(src)
        if shared_root and size >= threshold:
            key = content_key(src)
            shared.append(
                {
                    "rel": str(rel),
                    "local": str(src),
                    "remote": f"{str(shared_root).rstrip('/')}/{key}",
                    "bytes": size,
                    "key": key,
                }
            )
        else:
            inline.append(rel)
    return inline, shared


def push_shared(cfg, info, echo=print, progress=None):
    """Upload shared-store entries that are not on the remote yet.

    Transfers land in a `.incoming` directory and are renamed into place
    only on success: a store entry must never be half-populated, because the
    next batch decides to skip the upload purely by finding the directory
    there. Returns the paths still in flight (for cleanup on interrupt).
    """
    progress = interactive() if progress is None else progress
    in_flight = []
    for entry in info.get("shared", []):
        target, staging_target = entry["remote"], entry["remote"] + ".incoming"
        probe = remote_shell(cfg, f"test -d {shlex.quote(target)}", check=False)
        if probe.returncode == 0:
            echo(f"  = reuse  {entry['rel']}  ({_fmt_size(entry['bytes'])}) "
                 f"already on the remote as {entry['key']}")
            continue
        echo(f"  ^ upload {entry['rel']}  ({_fmt_size(entry['bytes'])}) "
             f"-> shared store {entry['key']}")
        remote_shell(cfg, f"rm -rf {shlex.quote(staging_target)} && "
                          f"mkdir -p {shlex.quote(staging_target)}")
        in_flight.append(staging_target)
        _rsync(entry["local"].rstrip("/") + "/", f"{cfg['host']}:{staging_target}/",
               progress=progress)
        remote_shell(cfg, f"mv {shlex.quote(staging_target)} {shlex.quote(target)}")
        in_flight.pop()
    return in_flight


def scan_shared_store(cfg):
    """What is in the shared store, and which entries are still referenced.

    Asks the REMOTE, not the local batch records: a workspace can be fed by
    more than one client, and a laptop's ~/.dsf bookkeeping says nothing
    about what another one pushed. A store entry is referenced iff some
    pushed deck still names it.

    Returns (entries, referenced) where entries is [{'key', 'path',
    'bytes'}] and referenced is the set of keys in use.
    """
    ws = cfg["workspace"].rstrip("/")
    probe = (
        f"du -sb {shlex.quote(ws)}/_shared/* 2>/dev/null; "
        "echo '---REFS---'; "
        f"grep -rhoE '_shared/[^\"]+' {shlex.quote(ws)}/*/*.xml 2>/dev/null"
    )
    res = remote_shell(cfg, probe, check=False)
    listing, _, refs = res.stdout.partition("---REFS---")

    entries = []
    for line in listing.splitlines():
        size, _, path = line.partition("\t")
        path = path.strip()
        if not path or not size.strip().isdigit():
            continue
        entries.append({"key": path.rsplit("/", 1)[-1], "path": path,
                        "bytes": int(size.strip())})

    referenced = set()
    for hit in refs.split():
        tail = hit.split("_shared/", 1)[-1]
        if tail:
            referenced.add(tail.split("/")[0].rstrip('"'))
    return entries, referenced


def gc_shared(cfg, delete=False, echo=print):
    """Report (and optionally remove) shared-store entries nothing references.

    Unreferenced means no pushed deck in the workspace names the entry, so
    removing it cannot break a batch that is still around. `.incoming`
    directories — the debris of an interrupted upload — are always garbage.
    Returns (removable, freed_bytes).
    """
    entries, referenced = scan_shared_store(cfg)
    removable = [
        e for e in entries
        if e["key"] not in referenced or e["key"].endswith(".incoming")
    ]
    freed = sum(e["bytes"] for e in removable)

    if not entries:
        echo("  shared store is empty")
        return [], 0
    kept = len(entries) - len(removable)
    echo(f"  {len(entries)} store entr{'y' if len(entries) == 1 else 'ies'}, "
         f"{kept} still referenced")
    for e in removable:
        why = "interrupted upload" if e["key"].endswith(".incoming") else "unreferenced"
        echo(f"  - {e['key']}  ({_fmt_size(e['bytes'])})  {why}")
    if not removable:
        echo("  nothing to collect")
        return [], 0

    if not delete:
        echo(f"  {_fmt_size(freed)} reclaimable — rerun with --delete to remove")
        return removable, freed

    discard_remote(cfg, [e["path"] for e in removable])
    echo(f"  removed {len(removable)} entr{'y' if len(removable) == 1 else 'ies'}, "
         f"freed {_fmt_size(freed)}")
    return removable, freed


def batch_disk_usage(cfg):
    """Per-batch disk usage on the remote, newest last. Reported, never
    collected: a batch directory holds run output, which is evidence."""
    ws = cfg["workspace"].rstrip("/")
    res = remote_shell(
        cfg, f"du -sb {shlex.quote(ws)}/*/ 2>/dev/null | grep -v '/_shared/$'", check=False)
    out = []
    for line in res.stdout.splitlines():
        size, _, path = line.partition("\t")
        path = path.strip().rstrip("/")
        if path and size.strip().isdigit():
            out.append({"name": path.rsplit("/", 1)[-1], "path": path,
                        "bytes": int(size.strip())})
    return out


def discard_remote(cfg, paths):
    """Remove partial remote directories after an interrupted transfer."""
    for path in paths:
        if path:
            remote_shell(cfg, f"rm -rf {shlex.quote(path)}", check=False)


def _path_size(path):
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _fmt_size(n):
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024.0


def rewrite_escaping_paths(xml_text, xml_path, maps):
    """Rewrite escaping path references to remote-absolute paths.

    Returns (new_text, rewrites, unmapped, kept_absolute). Rewrites operate
    on the TEXT (not a re-serialized tree) so the pushed XML keeps its
    comments, formatting, and attribute order — a DSF config is
    hand-maintained source, and a silently reformatted copy is unreviewable.

    An unmapped RELATIVE escape is fatal (reported by the caller): the batch
    dir sits at a different depth on the remote, so `../../build/x.so`
    cannot resolve there no matter what. An unmapped ABSOLUTE path is only
    a warning — it has a fair chance of naming the same location on both
    machines (/usr/share/..., or an identically-laid-out /opt).
    """
    rewrites, unmapped, kept_absolute = [], [], []
    for elem, attr, value, logical, is_abs in _escaping_refs(xml_path):
        remote = map_to_remote(logical, maps)
        if remote is None:
            if is_abs:
                kept_absolute.append((elem.tag, attr, value))
            else:
                unmapped.append((elem.tag, attr, value, str(logical)))
            continue
        needle = f'{attr}="{value}"'
        if needle in xml_text:
            xml_text = xml_text.replace(needle, f'{attr}="{remote}"')
            rewrites.append((f"{elem.tag}.{attr}", value, remote))
    return xml_text, rewrites, unmapped, kept_absolute


def read_mc_block(xml_path):
    """(n_cases, output_dir_name) from the XML's <monte_carlo> block.

    Raises if there is no MC block: a single `dsf run` is not worth a round
    trip, and a batch is the only thing this command usefully ships.
    """
    tree = ET.parse(str(xml_path))
    root = tree.getroot()
    sim = root if root.tag == "sim" else root.find(".//sim")
    if sim is None:
        raise RuntimeError(f"No <sim> node in {xml_path}")
    mc = sim.find("monte_carlo")
    if mc is None:
        raise RuntimeError(
            f"No <monte_carlo> block in {xml_path} — `dsf remote run` submits "
            "MC batches; add one with `dsf mc template`, or run single sims "
            "locally with `dsf run`."
        )
    out_dir = mc.get("output_dir", "mc_results")
    if Path(out_dir).is_absolute():
        raise RuntimeError(
            f'<monte_carlo output_dir="{out_dir}"> is absolute — remote '
            "batches need a path relative to the XML so results land inside "
            "the pushed batch dir."
        )
    return int(mc.get("n", "100")), out_dir.rstrip("/")


def stage_batch(xml_path, staging_dir, maps, shared_root=None, echo=print):
    """Copy the deck's payload into staging_dir, rewriting paths it names.

    Escaping references are remapped onto the remote's roots; deck-local
    payload is copied in at its own depth, except for bulk datasets, which
    are routed to the remote's shared store (see plan_shared) and uploaded
    separately by push_shared.

    Returns {'xml', 'n_cases', 'output_dir', 'rewrites', 'shipped',
    'kept_absolute', 'payload_bytes', 'shared'}.
    """
    xml_path = Path(xml_path).resolve()
    case_dir = xml_path.parent
    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)

    n_cases, out_dir = read_mc_block(xml_path)

    text, rewrites, unmapped, kept_absolute = rewrite_escaping_paths(
        xml_path.read_text(), xml_path, maps
    )
    if unmapped:
        detail = "\n".join(
            f'    <{tag} {attr}="{val}">  ->  {res}' for tag, attr, val, res in unmapped
        )
        raise RuntimeError(
            "these references escape the case dir and match no --map root, so "
            "the remote could not resolve them:\n"
            + detail
            + "\n  Add a mapping, e.g.  dsf remote setup --map "
            "/local/sixdof=/remote/sixdof"
        )

    shipped = [xml_path.name]

    # Everything the deck NAMES that lives inside its own directory, at
    # whatever depth: a table under config/, a local data/bathymetry/ tree.
    # A sibling-only scan silently dropped these, and the batch died N times
    # on the remote with no warning here.
    local_refs = deck_local_refs(xml_path)
    local_refs, shared = plan_shared(local_refs, case_dir, shared_root)

    # Bulk datasets are not copied into the batch — the deck is pointed at
    # their place in the remote's shared store, so a later batch naming the
    # same tiles reuses that upload instead of repeating it.
    by_rel = {e["rel"]: e["remote"] for e in shared}
    for _elem, attr, value, logical, kind in _all_path_refs(xml_path):
        if kind != "local":
            continue
        target = by_rel.get(str(logical.relative_to(case_dir)))
        if target:
            text = text.replace(f'{attr}="{value}"', f'{attr}="{target}"')
    (staging / xml_path.name).write_text(text)

    for rel in local_refs:
        src = case_dir / rel
        dst = staging / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
        else:
            shutil.copy2(src, dst)
        shipped.append(str(rel))

    # Sibling data files the XML does not name — a table can pull in a
    # companion file by a path written inside the table, which no XML scan
    # can see. Prior run output (stray .h5/.csv, the batch's own out dir) is
    # deliberately left behind.
    for f in sorted(case_dir.iterdir()):
        if not f.is_file() or f.name == xml_path.name:
            continue
        if f.suffix not in PAYLOAD_SUFFIXES or f.name in shipped:
            continue
        shutil.copy2(f, staging / f.name)
        shipped.append(f.name)

    for label, old, new in rewrites:
        echo(f"  ~ remap {label}: {old} -> {new}")
    total = 0
    for name in shipped:
        size = _path_size(staging / name)
        total += size
        suffix = "/" if (staging / name).is_dir() else ""
        echo(f"  + ship  {name}{suffix}  ({_fmt_size(size)})")
    for tag, attr, val in kept_absolute:
        echo(
            f'  ! kept absolute <{tag} {attr}="{val}"> — assumed to exist '
            "on the remote (add a --map if it does not)"
        )
    if total >= BULK_PAYLOAD_BYTES:
        echo(
            f"  ! this batch carries {_fmt_size(total)} of its own — transfer "
            "starts now; Ctrl-C stops it"
        )

    return {
        "xml": xml_path.name,
        "n_cases": n_cases,
        "output_dir": out_dir,
        "rewrites": rewrites,
        "shipped": shipped,
        "kept_absolute": kept_absolute,
        "payload_bytes": total,
        "shared": shared,
    }


def verify_remote_refs(cfg, info):
    """Check that every remapped target actually exists on the remote.

    A --map root can be right while the thing under it is missing (terrain
    tiles never copied, a build never made). Without this the batch pushes,
    launches, and dies N times with the answer buried in case_0000/sim.log.
    One ssh round trip; returns the list of missing remote paths.
    """
    targets = [new for _label, _old, new in info.get("rewrites", [])]
    if not targets:
        return []
    probe = "; ".join(
        f"test -e {shlex.quote(tgt)} || echo MISSING:{shlex.quote(tgt)}" for tgt in targets
    )
    res = remote_shell(cfg, probe, check=False)
    return [
        line.split("MISSING:", 1)[1].strip()
        for line in res.stdout.splitlines()
        if line.startswith("MISSING:")
    ]


def push_batch(cfg, staging_dir, batch_name):
    remote_dir = f"{cfg['workspace'].rstrip('/')}/{batch_name}"
    remote_shell(cfg, f"mkdir -p {shlex.quote(remote_dir)}")
    _rsync(str(Path(staging_dir)) + "/", f"{cfg['host']}:{remote_dir}/")
    return remote_dir


def launch_batch(cfg, remote_dir, xml_name, workers=None):
    """Start `dsf mc run` detached on the remote and return its PID.

    setsid + nohup so the batch outlives the ssh session — `dsf mc run` is a
    blocking foreground command with no daemon behind it, so an attached run
    would die with the connection.
    """
    cmd = f"{cfg['dsf_cmd']} mc run {shlex.quote(xml_name)}"
    if workers:
        cmd += f" -j {int(workers)}"
    launch = (
        f"cd {shlex.quote(remote_dir)} && "
        f"setsid nohup {cmd} > mc_launch.log 2>&1 < /dev/null & echo $!"
    )
    res = remote_shell(cfg, launch)
    return res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "?"


# ─── batch records ───


def load_batches():
    if not BATCHES_PATH.exists():
        return []
    return json.loads(BATCHES_PATH.read_text()).get("batches", [])


def record_batch(cfg, batch_name, remote_dir, xml_path, info, pid=None):
    batches = load_batches()
    batches.append(
        {
            "name": batch_name,
            "host": cfg["host"],
            "remote_dir": remote_dir,
            "remote_output_dir": f"{remote_dir}/{info['output_dir']}",
            "local_dir": str(Path(xml_path).resolve().parent),
            "xml": info["xml"],
            "n_cases": info["n_cases"],
            "output_dir": info["output_dir"],
            "pid": pid,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    BATCHES_PATH.parent.mkdir(parents=True, exist_ok=True)
    BATCHES_PATH.write_text(json.dumps({"batches": batches}, indent=2) + "\n")
    return batches[-1]


def find_batch(name=None):
    batches = load_batches()
    if not batches:
        raise RuntimeError("no remote batches recorded — submit one with `dsf remote run`")
    if name is None:
        return batches[-1]
    for b in reversed(batches):
        if b["name"] == name:
            return b
    raise RuntimeError(f"unknown batch {name!r} — see `dsf remote batches`")


# ─── status / fetch ───


def batch_state(cfg, record):
    """The remote `.dsf_mc.json` as a dict (None if not written yet)."""
    state_path = f"{record['remote_output_dir']}/.dsf_mc.json"
    res = remote_shell(cfg, f"cat {shlex.quote(state_path)}", check=False)
    if res.returncode != 0 or not res.stdout.strip():
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        # a concurrent write by the running batch caught mid-file
        return None


def remote_size(cfg, record):
    res = remote_shell(
        cfg, f"du -sh {shlex.quote(record['remote_output_dir'])} 2>/dev/null | cut -f1", check=False
    )
    return res.stdout.strip() or "?"


def _shelve_existing(out_dir):
    """Never overwrite prior results in place — move them aside."""
    out_dir = Path(out_dir)
    if not out_dir.exists() or not any(out_dir.iterdir()):
        return None
    n = 0
    while (shelf := out_dir.with_name(f"{out_dir.name}.prefetch{n}")).exists():
        n += 1
    out_dir.rename(shelf)
    return shelf


def fetch_batch(cfg, record, full=False, cases=None, echo=print):
    """Pull results into <local_dir>/<output_dir>/.

    Default is summary-only (the aggregate JSONs `dsf mc results`/`extremes`
    read) — a 1000-case batch's per-case HDF5 is usually gigabytes and you
    rarely want all of it. `full=True` takes everything; `cases=[3, 7]`
    cherry-picks case dirs (the `mc extremes` workflow).
    """
    local_out = Path(record["local_dir"]) / record["output_dir"]
    shelf = _shelve_existing(local_out)
    if shelf is not None:
        echo(f"  (previous {local_out.name}/ moved to {shelf.name}/)")
    local_out.mkdir(parents=True, exist_ok=True)

    src = f"{cfg['host']}:{record['remote_output_dir']}/"
    dst = str(local_out) + "/"

    if full:
        _rsync(src, dst)
        echo(f"  ✓ full results -> {local_out}")
    elif cases:
        extra = ["--include=/*.json", "--include=/.dsf_mc.json"]
        for cid in cases:
            extra += [f"--include=/case_{int(cid):04d}/", f"--include=/case_{int(cid):04d}/**"]
        extra += ["--exclude=*"]
        _rsync(src, dst, extra=extra)
        echo(f"  ✓ aggregates + {len(cases)} case(s) -> {local_out}")
    else:
        extra = [f"--include=/{name}" for name in SUMMARY_FILES]
        extra += ["--include=/mc_launch.log", "--exclude=*"]
        _rsync(src, dst, extra=extra)
        echo(f"  ✓ aggregates -> {local_out}")

    return local_out
