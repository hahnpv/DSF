"""
Remote-run CLI subcommands for DSF.

    dsf remote setup    — configure the solve box (one time)
    dsf remote run      — push a case dir, launch the MC batch detached
    dsf remote status   — one-shot progress of a batch
    dsf remote watch    — poll until the batch finishes
    dsf remote fetch    — pull results back
    dsf remote stop     — signal a running batch to stop
    dsf remote batches  — list submitted batches

Client-side verbs only: the remote runs stock `dsf mc`, so nothing beyond a
working DSF install is needed there. See docs/remote_runs.md.
"""

import sys
import time

import click


def _cfg():
    """Load the remote config, turning library errors into clean CLI errors."""
    from dsf.remote import load_config

    try:
        return load_config()
    except RuntimeError as e:
        raise click.ClickException(str(e))


def _batch(name):
    from dsf.remote import find_batch

    try:
        return find_batch(name)
    except RuntimeError as e:
        raise click.ClickException(str(e))


def _render_state(state, n_cases):
    if state is None:
        return (
            "no state file yet — the batch is starting (or failed to launch; check mc_launch.log)"
        )
    done, failed = state.get("done", 0), state.get("failed", 0)
    total = state.get("n_cases", n_cases)
    line = f"{state.get('status', '?')}: {done} done, {failed} failed / {total} cases"
    if state.get("elapsed"):
        line += f"  ({state['elapsed']})"
    return line


@click.group()
def remote():
    """Run Monte Carlo batches on a remote box over ssh."""
    pass


@remote.command()
@click.option(
    "--host", required=True, help="ssh destination (host or user@host; ~/.ssh/config aliases work)"
)
@click.option(
    "--workspace",
    required=True,
    help="Remote directory that receives batch dirs (created on demand)",
)
@click.option(
    "--map",
    "maps",
    multiple=True,
    metavar="LOCAL=REMOTE",
    help="Root mapping for paths that escape the case dir, e.g. "
    "LOCAL=REMOTE — your checkout on the left, the solve box's on the "
    "right, e.g. ~/sixdof=/opt/sixdof. Repeatable; needed for data "
    "references that escape the deck dir.",
)
@click.option("--dsf-cmd", default="dsf", show_default=True, help="Remote dsf invocation")
@click.option("--no-verify", is_flag=True, default=False, help="Skip the connectivity test")
def setup(host, workspace, maps, dsf_cmd, no_verify):
    """Configure (and test) the remote solve box.

    Written to ~/.dsf/remote.json. --map tells staging how to translate
    paths that point outside the case directory (the sixdof build, terrain
    data) into their locations on the remote:

      dsf remote setup --host solvebox --workspace /opt/DSF/tmp/remote \\
          --map ~/sixdof=/opt/sixdof --map ~/DSF=/opt/DSF
    """
    from dsf.remote import CONFIG_PATH, parse_map, remote_shell, save_config

    try:
        parsed = [parse_map(m) for m in maps]
    except ValueError as e:
        raise click.ClickException(str(e))

    cfg = {"host": host, "workspace": workspace, "maps": parsed, "dsf_cmd": dsf_cmd}

    if not no_verify:
        click.echo(f"Testing {host} ...")
        res = remote_shell(cfg, f"{dsf_cmd} --help > /dev/null && echo dsf-ok", check=False)
        if res.returncode != 0 or "dsf-ok" not in res.stdout:
            raise click.ClickException(
                f"remote test failed (rc {res.returncode}): {(res.stderr or res.stdout).strip()}"
            )
        click.echo("  dsf reachable through the remote login shell")
        for m in parsed:
            probe = remote_shell(cfg, f"test -d {m['remote']}", check=False)
            mark = "ok" if probe.returncode == 0 else "MISSING on remote"
            click.echo(f"  map {m['local']} -> {m['remote']}  [{mark}]")

    save_config(cfg)
    click.echo(f"Saved {CONFIG_PATH}")


@remote.command()
@click.argument("xml_file", type=click.Path(exists=True))
@click.option("--name", default=None, help="Batch name (default: <xml stem>_<UTC timestamp>)")
@click.option(
    "--workers",
    "-j",
    default=None,
    type=int,
    help="Parallel workers on the remote (default: the XML's own)",
)
@click.option(
    "--watch",
    "do_watch",
    is_flag=True,
    default=False,
    help="Poll until the batch finishes, then fetch aggregates",
)
@click.option(
    "--poll", default=15, show_default=True, help="Seconds between polls when --watch is used"
)
@click.option("--no-sync-check", is_flag=True, default=False, help="Skip the git HEAD comparison")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Submit despite a source mismatch between the machines",
)
@click.option(
    "--dry-run", is_flag=True, default=False, help="Stage and report the plan; push nothing"
)
def run(xml_file, name, workers, do_watch, poll, no_sync_check, force, dry_run):
    """Push a Monte Carlo case dir to the remote and launch the batch.

    Everything the deck names inside its own directory travels with it, at
    any depth — a table under config/, a local data/bathymetry/ tree — plus
    its sibling data files. References that ESCAPE the deck dir (shared
    terrain, a legacy library= path) are rewritten to the remote's own
    locations via the configured --map roots and never pushed; the remapped
    targets are checked for existence before launch. The batch is launched
    detached, so it survives your ssh session and laptop sleeping.

      dsf remote run cruise_missile_mc_test.xml -j 32
      dsf remote run vehicle.xml --watch
    """
    import shutil
    import tempfile
    from datetime import datetime, timezone

    from dsf import remote as rmod

    cfg = _cfg()

    if not no_sync_check:
        verdict, lines = rmod.sync_check(cfg)
        for ln in lines:
            click.echo(f"  {ln}")
        if verdict == "mismatch" and not force:
            raise click.ClickException(
                "source trees differ between the machines (--force to override)"
            )
        if verdict == "unknown":
            click.secho("  sync check inconclusive — proceeding", fg="yellow")
        click.secho(
            "  note: matching sources do not prove the remote was "
            "rebuilt — physics runs from its compiled libs",
            fg="yellow",
        )

    stem = __import__("pathlib").Path(xml_file).stem
    batch_name = name or f"{stem}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')}"

    staging = tempfile.mkdtemp(prefix="dsf_remote_")
    try:
        try:
            info = rmod.stage_batch(
                xml_file, staging, cfg["maps"],
                shared_root=f"{cfg['workspace'].rstrip('/')}/_shared",
            )
        except RuntimeError as e:
            raise click.ClickException(str(e))

        click.echo(
            f"\nBatch {batch_name}: {info['n_cases']} cases -> {cfg['host']}:{cfg['workspace']}"
        )
        if dry_run:
            click.echo("--dry-run: nothing pushed.")
            return

        # A remapped root can be right while the thing under it is missing.
        # Catch that here, not in 1000 identical case logs.
        missing = rmod.verify_remote_refs(cfg, info)
        if missing:
            detail = "\n".join(f"    {m}" for m in missing)
            raise click.ClickException(
                "these remapped paths do not exist on the remote:\n" + detail +
                "\n  Fix the --map roots, or put the data there first.")

        # The transfer starts immediately and reports progress; if it turns
        # out to be moving far more than you expected, Ctrl-C stops it and
        # nothing is left behind on either end.
        in_flight, remote_dir = [], None
        try:
            in_flight = rmod.push_shared(cfg, info)
            remote_dir = f"{cfg['workspace'].rstrip('/')}/{batch_name}"
            in_flight.append(remote_dir)
            rmod.push_batch(cfg, staging, batch_name)
            in_flight.remove(remote_dir)
        except KeyboardInterrupt:
            click.echo("\n  Cancelled — discarding the partial transfer ...")
            rmod.discard_remote(cfg, in_flight)
            click.echo("  Nothing left on the remote; staging discarded.")
            raise SystemExit(130)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    pid = rmod.launch_batch(cfg, remote_dir, info["xml"], workers=workers)
    record = rmod.record_batch(cfg, batch_name, remote_dir, xml_file, info, pid=pid)
    click.echo(f"Launched detached (pid {pid}).")

    if not do_watch:
        click.echo(
            f"\n  Progress:  dsf remote status {batch_name}\n"
            f"  Results:   dsf remote fetch {batch_name}"
        )
        return

    rc = _watch_loop(cfg, record, poll)
    click.echo("\nFetching aggregates ...")
    rmod.fetch_batch(cfg, record)
    _report_next_steps(record)
    raise SystemExit(rc)


def _watch_loop(cfg, record, poll):
    """Poll the remote state file until the batch reports finished."""
    from dsf.remote import batch_state

    click.echo(f"Watching {record['name']} (Ctrl-C detaches; the batch keeps running)\n")
    try:
        while True:
            state = batch_state(cfg, record)
            stamp = time.strftime("%H:%M:%S")
            click.echo(f"[{stamp}] {_render_state(state, record['n_cases'])}")
            if state and state.get("finished"):
                return 1 if state.get("failed") else 0
            time.sleep(max(2, poll))
    except KeyboardInterrupt:
        click.echo(f"\nDetached. Batch continues on {cfg['host']}.")
        raise SystemExit(0)


def _report_next_steps(record):
    out = f"{record['local_dir']}/{record['output_dir']}"
    click.echo(
        f"\n  dsf mc results {out}\n"
        f"  dsf mc extremes {out}\n"
        f"  dsf remote fetch {record['name']} --full   # per-case output"
    )


@remote.command()
@click.argument("batch", required=False, default=None)
def status(batch):
    """Progress of a batch (default: the most recent one)."""
    from dsf.remote import batch_state, remote_size

    cfg = _cfg()
    record = _batch(batch)
    state = batch_state(cfg, record)
    click.echo(f"{record['name']}  {record['host']}:{record['remote_dir']}")
    click.echo(f"  {_render_state(state, record['n_cases'])}")
    if state and state.get("finished"):
        click.echo(
            f"  remote size: {remote_size(cfg, record)}  "
            f"(fetch with `dsf remote fetch {record['name']}`)"
        )


@remote.command()
@click.argument("batch", required=False, default=None)
@click.option("--poll", default=15, show_default=True, help="Seconds between polls")
def watch(batch, poll):
    """Poll a batch until it finishes (Ctrl-C detaches; it keeps running)."""
    cfg = _cfg()
    record = _batch(batch)
    raise SystemExit(_watch_loop(cfg, record, poll))


@remote.command()
@click.argument("batch", required=False, default=None)
@click.option(
    "--full", is_flag=True, default=False, help="Pull every case directory, not just the aggregates"
)
@click.option(
    "--case",
    "cases",
    multiple=True,
    type=int,
    help="Pull specific case IDs (repeatable) — the `mc extremes` workflow",
)
def fetch(batch, full, cases):
    """Pull results back into the local case dir.

    Default pulls only the aggregates (.dsf_mc.json, mc_draws.json,
    mc_index.json) — enough for `dsf mc results` and `dsf mc extremes`, and
    small. Per-case HDF5/CSV for a big batch is often gigabytes, so ask for
    it explicitly with --full, or cherry-pick with --case.
    """
    from dsf.remote import fetch_batch

    cfg = _cfg()
    record = _batch(batch)
    fetch_batch(cfg, record, full=full, cases=list(cases) or None)
    _report_next_steps(record)


@remote.command()
@click.argument("batch", required=False, default=None)
def stop(batch):
    """Signal a running batch to stop after its in-flight cases."""
    from dsf.remote import remote_dsf

    cfg = _cfg()
    record = _batch(batch)
    raise SystemExit(remote_dsf(cfg, ["mc", "stop", record["remote_output_dir"]]))


@remote.command()
@click.option("--delete", is_flag=True, default=False,
              help="Actually remove the unreferenced entries (default: report only)")
def gc(delete):
    """Collect shared-store entries that no batch references.

    The store grows because every distinct dataset uploaded stays until
    nothing points at it. An entry is garbage once no pushed deck in the
    workspace names it — plus any `.incoming` left by an interrupted upload.

    Batch directories are reported but never collected: they hold run
    output. Remove those yourself once you have fetched what you need.
    """
    from dsf.remote import batch_disk_usage, gc_shared

    cfg = _cfg()
    click.echo(f"Shared store on {cfg['host']}:{cfg['workspace']}/_shared")
    gc_shared(cfg, delete=delete)

    batches_on_disk = batch_disk_usage(cfg)
    if batches_on_disk:
        total = sum(b["bytes"] for b in batches_on_disk)
        from dsf.remote import _fmt_size

        click.echo(f"\n{len(batches_on_disk)} batch dir(s) holding {_fmt_size(total)} "
                   "(run output — not collected):")
        for b in sorted(batches_on_disk, key=lambda b: b["bytes"], reverse=True)[:5]:
            click.echo(f"  {b['name']}  {_fmt_size(b['bytes'])}")


@remote.command()
def batches():
    """List submitted batches (newest last)."""
    from dsf.remote import load_batches

    for b in load_batches():
        click.echo(
            f"  {b['created']}  {b['name']}  {b['n_cases']} cases  {b['host']}:{b['remote_dir']}"
        )


if __name__ == "__main__":
    sys.exit(remote())
