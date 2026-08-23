# Remote Monte Carlo Runs

Submit MC batches from a small machine (laptop) to a big one over ssh. There
is no server and no daemon: `dsf remote` pushes a case directory, starts a
detached `dsf mc run` on the remote, polls its state file, and pulls results
back. The remote needs nothing but a working DSF install.

Single sims are not worth a round trip — `dsf remote run` requires a
`<monte_carlo>` block and refuses a plain config.

## Setup (once, on the client)

```bash
dsf remote setup --host solvebox \
                 --workspace /opt/DSF/tmp/remote \
                 --map ~/sixdof=/opt/sixdof \
                 --map ~/DSF=/opt/DSF
```

`--host` is any ssh destination (`~/.ssh/config` aliases work; set up
pubkey auth first). `--workspace` receives one directory per batch and is
created on demand. `--map` is the important one — see below. Setup verifies
the remote by running `dsf` through a login shell (`bash -lc`, so conda and
`LD_LIBRARY_PATH` from your profile apply) and probes each mapped root.
Config lands in `~/.dsf/remote.json`, batch records in
`~/.dsf/remote_batches.json`.

## Why `--map` exists

A DSF config references files two different ways, and only one of them can
travel with the batch:

```xml
<sim library="libsixdof.so">                             <!-- linker   -->
    <terrain data_dir="../../../data/terrain" />         <!-- ESCAPES  -->
    <aero filename="cruise_aero.dat" />                  <!-- payload  -->
```

The model library is not a path at all under the current convention: a bare
soname is resolved by the dynamic linker from the remote's own
`LD_LIBRARY_PATH`, which is exactly what you want — the remote runs its own
build. Staging leaves any slash-free value alone. (A legacy deck that still
names the library by relative path is remapped like any other escaping
reference, but fix the deck instead — see `docs/monte_carlo.md`.)

References resolving **inside** the deck dir are payload, at any depth. A
table beside the deck (`cruise_aero.dat`), one in a subdirectory
(`filename="config/6dofTables.dat"`), and a local data tree
(`data_dir="data/bathymetry/"`) all travel with the batch, keeping their
relative layout. Sibling data files the deck does not name are shipped too,
since a table can pull in a companion file by a path written inside itself,
which no XML scan can see.

Every shipped item is listed with its size:

```
  + ship  deck.xml  (233B)
  + ship  config/6dofTables.dat  (18.4KB)
```

Anything at or above 10 MB is routed to the remote's shared store instead of
being copied into the batch — see below.

References that **escape** the deck dir are the ones `--map` is for: shared
terrain and bathymetry tile sets that already exist on the remote. They
cannot be left as written, because the batch dir sits at a different depth
there, so `../../../data/terrain` resolves to nothing. Instead they are
**rewritten** to the remote's own paths using the `--map` roots:

```
~ remap terrain.data_dir: ../../../data/terrain -> /opt/sixdof/data/terrain
```

Only the pushed copy is rewritten — your local XML is never touched, and the
copy keeps its comments and formatting so it stays reviewable. Every
attribute of every element is scanned, so model-specific path attributes are
covered without an allowlist; values with incidental slashes (`units="m/s"`)
resolve inside the case dir and are left alone, as are bare sonames
(`library="libsixdof.so"`, resolved via `LD_LIBRARY_PATH` on the remote).

An escaping **relative** path with no matching map is a hard error — it
would fail on the remote every time, for all N cases. An unmapped
**absolute** path is only a warning: it may well name the same location on
both machines.

Before pushing, every remapped target is checked for existence on the
remote. A `--map` root can be correct while the thing under it is missing
(terrain never copied, a build never made), and that is worth one ssh round
trip to catch here rather than in N identical case logs:

```
Error: these remapped paths do not exist on the remote:
    /opt/sixdof/data/terrain
  Fix the --map roots, or put the data there first.
```

## Bulk data uploads once

Tables are kilobytes and ride along with every batch. Tile sets are not, and
copying them into each batch would re-send the same gigabytes forever. So
anything at or above 10 MB goes to a **content-addressed shared store** on
the remote (`<workspace>/_shared/<name>-<hash>/`) and the pushed deck is
pointed at it:

```
--- first batch ---
  ^ upload data/bathymetry  (12.0MB) -> shared store bathymetry-6c1270820ddc
--- later batch, same tiles (even a different deck) ---
  = reuse  data/bathymetry  (12.0MB) already on the remote as bathymetry-6c1270820ddc
```

The key is a hash of the dataset's file names and sizes, not its contents —
re-reading gigabytes on every submission to decide whether to skip an upload
would cost more than the upload saves. Change the data and it uploads under
a new key; the old one stays for batches that still reference it. Entries
land in a `.incoming` directory and are renamed into place only on success,
so a store entry is never half-populated (the next batch decides to skip an
upload purely by finding it there).

Nothing is deduplicated *within* a batch because there is nothing to
deduplicate: one deck's data is staged once and pushed once, however many
cases the batch runs.

## Interrupting a transfer

There is no confirmation prompt. The transfer starts immediately and rsync
reports progress, so if it is moving far more than you expected, Ctrl-C
stops it:

```
  ! this batch carries 12.0GB of its own — transfer starts now; Ctrl-C stops it
  Cancelled — discarding the partial transfer ...
  Nothing left on the remote; staging discarded.
```

The interrupt is caught, not fatal: the partial batch directory and any
half-finished store entry are removed from the remote, the local staging
copy is discarded, and the batch is never launched. Exit code is 130.

## Running a batch

```bash
dsf remote run cruise_missile_mc_test.xml            # submit and return
dsf remote run cruise_missile_mc_test.xml -j 32      # more remote workers
dsf remote run vehicle.xml --watch                   # poll to completion, then fetch
dsf remote run vehicle.xml --dry-run                 # show the plan, push nothing
```

In order: compare git HEADs of the mapped roots (mismatch refuses without
`--force`), stage the payload with paths rewritten, rsync it to
`<workspace>/<batch>/`, and start `dsf mc run` under `setsid nohup` with
stdout in `mc_launch.log`. The batch is **detached** — `dsf mc run` is a
blocking foreground command with no daemon behind it, so an attached run
would die with your ssh session. It survives disconnects and laptop sleep.

> The sync check compares *sources*. DSF physics runs from compiled libs, so
> matching SHAs do not prove the remote was rebuilt — that is on you.

## Monitoring

```bash
dsf remote status [BATCH]        # one-shot: done/failed/elapsed
dsf remote watch  [BATCH]        # poll until finished (Ctrl-C detaches)
dsf remote batches               # what you have submitted, newest last
dsf remote stop   [BATCH]        # graceful stop (in-flight cases finish)
```

All of these read the remote's `.dsf_mc.json`, the same state file
`dsf mc status` uses. Omit BATCH to act on the most recent one. `stop`
drives the `dsf mc stop` sentinel: queued cases are cancelled, running ones
are allowed to finish.

## Getting results back

```bash
dsf remote fetch                 # aggregates only (default)
dsf remote fetch --full          # every case dir
dsf remote fetch --case 7 --case 42
```

Results land in `<local case dir>/<output_dir>/` — the same place a local
run would write them, so `dsf mc results`, `dsf mc extremes`, and
`dsf mc plot` work on them unchanged.

The default is deliberately **aggregates only** (`.dsf_mc.json`,
`mc_draws.json`, `mc_index.json`): that is everything `dsf mc results` and
`dsf mc extremes` read, and it is kilobytes. Per-case HDF5/CSV for a
1000-case batch is often gigabytes, so ask for it explicitly. The natural
workflow is to fetch aggregates, find the interesting cases, then pull only
those:

```bash
dsf remote fetch                             # aggregates
dsf mc extremes mc_results/ -t 2.5           # which cases are extreme?
dsf remote fetch --case 391 --case 774       # pull just those
```

An existing local results dir is moved aside to `<output_dir>.prefetchN/`
before a fetch — prior results are never overwritten in place. Fetch is
re-runnable, so pulling early for finished cases and again later is fine.

## Gotchas

- Both machines need this feature installed; the client drives stock
  `dsf mc` verbs on the remote.
- Do not move or rename the local case directory between submit and fetch —
  results are delivered to the path recorded at submit time.
- Staging's remap and the dispatcher's path anchoring (`docs/monte_carlo.md`)
  do not fight: staging rewrites escaping references to remote-absolute
  paths, and the dispatcher leaves absolute values alone when it writes each
  `case.xml`. Anchoring alone cannot substitute for `--map` — it resolves
  against the *pushed* deck's directory, which sits at a different depth
  from the shared assets.
- `<monte_carlo output_dir="...">` must be relative, so results land inside
  the pushed batch dir where fetch can find them.
- Case dirs contain absolute symlinks to data files; fetch skips them
  (`rsync --safe-links`) rather than transferring dangling links or copying
  an aero table into every case dir. The originals are already beside your
  local XML.
- Batches accumulate under the remote workspace. Nothing cleans them up —
  they are your run evidence until you archive them.
