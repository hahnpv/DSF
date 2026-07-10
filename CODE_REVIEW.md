# DSF Deep-Dive Code Review

Scope: full C++ kernel (`DSF/sim`, `DSF/util`), pybind11 bindings, build/packaging, Python CLI + utils, PyQt6 GUI, JAX/MCP/Monte Carlo, and tests/hygiene. Findings marked **[verified]** were confirmed by reading the exact source this session or (for the C++ utility layer) reproduced under AddressSanitizer/UBSan by the reviewer. Severity is the reviewer's, normalized across subsystems.

---

## Top-priority fixes (start here)

These are the highest impact-per-effort items; each is either a security hole, a silent-wrong-physics bug, or a crash on a common path.

1. **MCP server is an unauthenticated RCE surface.** `--host` defaults to `0.0.0.0` with `enable_dns_rebinding_protection=False`, exposing `dsf_write_file` + `dsf_build` + a `library` param that feeds `LD_PRELOAD` — write a file, build it, load it into a sim = remote code execution with no auth. Path containment uses `str(p).startswith(str(FILE_ROOT))`, so `/opt/sixdof_secrets` counts as inside `/opt/sixdof`. **[verified]** `python/dsf/mcp/server.py:51,1989,1999`
2. **1D `Table` interpolation is wrong.** Early-`break` + post-loop special cases short-circuit before the bracketing indices are set: last panel of every table returns a frozen constant then jumps, and 2-point tables return the low value for all interior queries. ASan/empirically confirmed: `interp(2.5)` on {0,1,2,3}→{0,10,20,30} returns 20, not 25. Every aero/thrust/mass table is affected. **[verified]** `DSF/util/tbl/tbl.cpp:188-207`
3. **`Table2d` heap-overflow below range.** Query below the first breakpoint exits binary search with `right=-1` and reads `table[-1]`. ASan-confirmed. **[verified]** `DSF/util/tbl/tbl2d.cpp:101-128`
4. **`dsf run` crashes on tag-implied classes.** `run.py` calls `child.tag()`, which was never bound (`xmlnode` exposes only `name()`). Any `<sim>` child without a `class=` attribute → `AttributeError` mid-run. **[verified]** `python/dsf/cli/run.py:193`, `python/bindings/bindings_util.cpp:161`
5. **`Mat4::det/inv/transpose` have commented-out bodies** — non-void functions with no return, UB; exposed to Python. **[verified]** `DSF/util/math/mat4.cpp:32-71`
6. **Clock `safe_sample` uninitialized + float-equality report gate.** `Clock` never initializes `safe_sample`; the report trigger `time/(t*error) == (int)(time/(t*error))` silently emits *zero* telemetry for any rate not landing on an exact binary-representable integer. This gate governs all CSV/HDF5 output. **[verified]** `DSF/sim/clock.h:36-42,93`
7. **`Sim.load` / `Block` / `Sim` bindings have no lifetime tethering.** `Sim.load` lacks `keep_alive`, and `dsf.Sim()`/`dsf.Block()` expose uninitialized/null pointer members — trivial segfaults reachable from pure Python (`dsf.Block().t()`, `dsf.Sim().step()`). **[verified]** `python/bindings/bindings_sim.cpp:74-78,164-170`
8. **Monte Carlo statistics are fiction.** Python pre-draws dispersions with numpy PCG64 into `mc_draws.json`; the C++ engine draws independently with its own md5-seeded `rand()`. The two never exchange values, so every reported σ/extreme is unrelated to what the sim applied. **[verified]** `python/dsf/mc.py:111-143`, `DSF/sim/monte_carlo.h:214`
9. **`-fpermissive` on all six targets traces to one missing `const` overload** on `Mat3::operator[]` (used by `Quaternion::fromDCM`). Add `const Vec3& operator[](int) const` and delete `-fpermissive` everywhere; it currently masks all future ill-formed code. **[verified]** `DSF/util/math/mat3.h:68`, `DSF/util/math/quat.h:73`

---

## C++ simulation kernel (`DSF/sim`)

### Critical
- **Uninitialized `safe_sample`** read as UB; default `Clock()` initializes nothing. `clock.h:36-42`
- **Float-equality report gate** silently drops entire telemetry channels; `(int)` cast is UB past INT_MAX. `clock.h:93`
- **RK45 has no rejection cap and accepts NaN steps.** At `dt_min` with persistent error the sub-step loop hangs forever; `std::max(err_max, NaN)` returns the non-NaN value, so NaN derivatives are *accepted* and propagate silently. `integrator_rk45.cpp:199-213`
- **No integrand deregistration** (`TIntDict` has no remove/clear). A block deleted mid-run (staging/separation) leaves the integrator writing through freed memory; a second Sim run in a long-lived host (GUI/MCP/session) integrates run-1's freed blocks. Same for `EventBus` (`clear()` exists, never called). `TIntDict.h`, `event.cpp:117-124`

### High
- **RK45 freezes clock across all stages** — every k1..k7 sees start-of-step time; time-dependent dynamics degrade to 1st order silently (RK4 does advance). `integrator_rk45.cpp:96-218`
- **Recurring events impossible** — the permanent `fired` flag makes `one_shot=false` fire exactly once. `event.cpp:16-17,191-193`
- **Mat3 CSV output injects newlines mid-row** (operator<< prints 3 `endl`s), and header/column/name counts are mutually inconsistent (1 vs 1 vs 9). `output.h:104-105`, `mat3.cpp:244-249`
- **No `dt`/`tmax` validation** — missing `dt` → `error=inf`, `t()`≡0, infinite loop with zero advance; missing `tmax` → zero-length run. `sim.cpp:75`, `clock.h:39`
- **Monte Carlo writes 8 bytes with no type check** — `*reinterpret_cast<double*>(block+offset)` corrupts smaller `int`/`bool`/`float` members and breaks under multiple inheritance. `monte_carlo.h:235-254`
- **Null `clock`/`o` deref for late-added blocks** — refs are propagated once in `Sim::load`; any runtime-added block segfaults on `t()`/`sample()`. `block.h:75-78`, `sim.cpp:99-100`

### Medium (selected)
- Verlet: default `GENERIC` integrands destroy the symplectic property with no warning; clock at t+dt/2 for the final force eval. `integrator_verlet.cpp:40-65`
- `Sim` has no ctor/dtor: uninitialized members, leaks `Clock`/`Output`/integrator/tree, reload leaks the prior set. `sim.h:87-93`
- `_console` report-rate parameter is a no-op. `sim.cpp:72`
- Event callbacks can invalidate `events_` mid-iteration (use-after-free); `TIME_GE` threshold ≤ start never fires; first-step crossings undetected. `event.cpp:27,204-211`
- `hdf5output` swallows all dataset errors with `catch(...){}`; variables added after first `report()` never get a dataset. `hdf5output.h:378,400`
- Static-init/linkage hazards: integrand dict & `EventBus` singletons aren't anchored like `TClassDict`; an `RTLD_LOCAL` load silently gets its own registry (states never integrated). `TIntDict.h:164`, `TClassDict.h:142`
- `TClass` eagerly `new`s a live instance of every model class at dlopen static-init (order fiasco surface; prototypes leak/alias). `TClassDict.h:222`

### Low (themes)
- Block trees, factories, output streams, HDF5 objects all leak (no dtors / rule-of-three violations → double-free if ever copied). `block.h:55`, `TClassDict.h:153`, `output.h:122`, `hdf5output.h:44`
- Debug `cout` in `TClass::getnew` spams stdout on every block creation. `TClassDict.h:159,199`
- Documented registration idiom in `block.h:41-49` doesn't compile (assigns `TClass*` to `Block*`).
- `find_variable` uses substring match (`"x"` matches `"Max_Q"`). `output.h:265`
- Redundant 5th derivative eval per RK4 step; `TFunctor` passes child vectors by value on the hot path. `integratorRK4.cpp:14`, `TFunctor.h:33`
- Dead: `TSkedDict.h`, `RTclock.h` (all commented, nested `/* /*`), `Sim::sim()`.

---

## C++ utility layer (`DSF/util`) — several ASan-confirmed

### Critical
- **1D `Table` piecewise-constant bug** (see top-priority #2). `tbl.cpp:180-207` **[verified]**
- **`Table2d` `table[-1]` heap-overflow below range** (ASan). `tbl2d.cpp:101-128`

### High
- **`TableND` stack-overflow >8 dims** — fixed `int idx[8]/frac[8]`, loop to `D=axes_.size()` unchecked (ASan/UBSan). `tablend.cpp:223-235`
- **`TableND` single-point axis reads past end** (ASan). `tablend.cpp:183-188,232`
- **`Mat4::det/inv/transpose` empty bodies → UB**, exposed to Python. `mat4.cpp:32-71` **[verified]**
- **Missing/failed table load** leaves `max=-1`/empty and then OOB-reads `table[0][0]`; error path blocks on `cin >> xx` (headless `dsf run` hangs). `tbl.cpp:26-61,165`, `tbl2d.cpp:26`
- **Default/failed `Table2d` and `Table` crash on first interp** (`size()-2` size_t underflow; wild `table` pointer). `tbl2d.cpp:58-96`, `tbl.h:24,32`
- **`xml::parse()` failure leaves `xmlRoot==nullptr`** with only a stderr message; the documented `*doc.xmlRoot` usage then segfaults on any malformed XML. `xml.h:268-277`
- **`Vec3::operator==`/`!=`/`<`/`>` compare magnitudes, not components** — `(1,0,0)==(0,1,0)` is `true`. `vec3.cpp:149-184` **[verified]**

### Medium (selected)
- `Vec3::operator[]`/`Mat3::operator[]` fall off the end for out-of-range index (UB). `Mat3::inv()`/`Vec3::unit()` no zero/singularity guard → silent NaN. `Mat4()` leaves 16 elements uninitialized. `vec3.cpp`, `mat3.cpp:45`, `mat4.h:30`
- **`Quaternion::dcm()` doc says body-to-inertial but returns inertial-to-body** (verified with pure yaw); `fromDCM` is self-consistent but its docstring mislabels the input frame. `quat.cpp:28-45`
- **`parse.h::split` zero-fills unparseable tokens and truncates strings at internal whitespace** — this is the real mechanism behind the "whitespace bug." `attrAsVec3` splits on `","` only, so `position="1 2 3"` silently becomes `(0,0,0)`. `parse.h:50-57`, `xml.h:143`
- Table classes: no breakpoint sort/dup validation; three inconsistent out-of-range policies (clamp vs extrapolate vs crash); `TableND` never checks data length vs axis-size product. `tbl.cpp`, `tbl2d.cpp:58`, `tablend.cpp:24-57`
- `Table` leaks its `double**` (LeakSanitizer-confirmed), aliases on copy. `tbl.cpp:54`
- **`J2_EARTH = 0.001081874`** vs WGS84 `1.08262998e-3` (0.07% off); **`PI=3.14159`, `RAD=57.2958`** (~7 sig figs), all exported to Python. `earth_constants.h:23`, `constants.h:13-15` **[verified]**
- `xmlnode` accessors silently return zero/identity defaults for missing/malformed attrs; a failed `search()` leaves the cursor on the wrong node. `xml.h:119-208`
- `gauss.h` non-inline funcs in a header (latent ODR/multi-def link error); uses global non-thread-safe `rand()` and discards half the Box–Muller draws. `gauss.h:21-61`

### Note on the "hand-rolled XML parser"
CLAUDE.md/TODO.md describe a hand-rolled, tab-dependent parser. The current `DSF/util/xml/` is a **Boost Property Tree wrapper** (`xml.cpp` is empty); tag/attribute/comment/CDATA parsing is Boost's and structurally sound. The residual whitespace fragility is in **value** parsing (`parse.h`, `attrAsVec3` — see above). **CLAUDE.md's gotcha should be corrected.**

### Duplicated code
Three divergent binary-search+interp implementations (the divergence *is* the source of the table bugs); CSV column-extraction duplicated `tbl.cpp` vs `tablend.cpp`; Euler→quat body duplicated in `quat.cpp`; `clamp`/`clamp_val` identical; `fptr.h` (118 lines) a self-declared deprecated dup of `TFunctor.h`; `mat4.cpp` has ~120 lines of commented-out Mat3 code.

---

## pybind11 bindings & build

### Critical
- **`Sim.load` no `keep_alive`** → Python GCs the root block while `run()` (GIL released) dereferences it. `bindings_sim.cpp:165-170`
- **`dsf.Sim()` exposes uninitialized `clock`/`output`/`i`**; `.clock.t()`/`.step()` before `load()` deref wild pointers. `bindings_sim.cpp:164`
- **`dsf.Block()` time methods deref null `clock`** → segfault from pure Python. `bindings_sim.cpp:74-78`

### High
- **`run.py` calls unbound `xmlnode.tag()`** (top-priority #4); C++ loader falls back to *id*, not capitalized tag — semantics differ too. `run.py:193`
- **PyBlock trampoline has leftover `std::cout` debug prints** on `rptSim`/`update` etc. — one line per block per step (~60k lines for a 600s/0.01 run) plus a GIL acquire; present in the shipped `.so`. `bindings_sim.cpp:19-44`
- **Python run path silently drops `<events>` and Monte Carlo** that `examples/dynamic/main.cpp` applies — `EventBus`, `MonteCarloCase`, `PhaseSequencer` have no bindings; same deck diverges between `dsf run` and the C++ exe. `bindings_sim.cpp`, `examples/dynamic/main.cpp:110-199`
- **Non-editable install is broken** — `dsf/gui`, `dsf/utils`, `dsf/gui_tests` lack `__init__.py`, so `find_packages()` omits them; `pip install .` ships a package where gui/watch/run/MCP fail with `ModuleNotFoundError`. `setup.py:8`
- **`dsf_core` is never installed and is currently stale/divergent** — `build/…so` (md5 cf23) ≠ `python/dsf/…so` (md5 883b). `dsf run` loads the build copy; `import dsf`/watch/GUI/MCP load the stale package copy → two binding versions in one repo. No `install()` rule anywhere; a wheel would contain no extension. `CMakeLists.txt`, `setup.py`
- **`-fpermissive` everywhere from one missing `const` overload** (top-priority #9). `mat3.h:68`, `quat.h:73`
- **xmlnode graph returns raw refs with no keep_alive to the owning `xml`** — returning a node from a function that drops the doc = use-after-free; `child/parent/search` also mutate-and-return-self (surprising aliasing). `bindings_util.cpp:156-167`

### Medium (selected)
- `run.py` sets `RTLD_GLOBAL|RTLD_LAZY` and never restores it — every later C-extension (h5py/numpy/lxml) loads global, inviting symbol interposition. `run.py:27`
- `.so` discovery globs `dsf*.so` in arbitrary `os.listdir` order → wrong-ABI pick after a Python upgrade. `run.py:11-24`
- `util` static lib built without PIC but linked into `libDSF.so` (works only because the sole util-only TU, `xml.cpp`, is empty). `DSF/util/CMakeLists.txt`
- `DSF` recompiles the same sources as `libsim.a`/`libutil.a` and PUBLIC-links the archives → link-order-dependent singleton duplication (the exact failure `RTLD_GLOBAL` exists to prevent); the two source lists have already drifted (`mat4.cpp`/`quat.cpp`). `CMakeLists.txt:58-79`
- `setup.py` missing `jax`/`matplotlib`/`mcp`/`pydantic`; no `package_data` for the extension or gui textures; installs top-level `tests`/`tests.gui` into site-packages. `setup.py`
- Two 904 KB `libsixdof.so.1*` binaries git-tracked in the package, referenced by nothing. `python/dsf/`
- `Output::add` deliberately unbound → Python `Block` subclasses can never emit telemetry (feature unusable end-to-end). `bindings_sim.cpp:147`
- `Table2d` bilinear overload & `TableND` unbound; `t.interp(0.5, 2.7)` silently truncates col to 2. `bindings_util.cpp:136`
- `Mat3.__getitem__` returns `Vec3&` with bare `reference` (dangling row). `MANIFEST.in` entirely dead (`src/`, `LICENSE`, `README` don't exist under `python/`). `run_sixdof_example.sh`/README reference a `build/sixdof_build` the build no longer creates.

---

## Python CLI & utils (cross-verified against sixdof)

### Critical
- **`.dsf`-as-directory format is unimplemented** — DSF_FORMAT.md/CLAUDE.md say a `.dsf` is a directory with `project.xml`; all three loaders `json.load(open(path))`. `dsf run myproject.dsf/` → `IsADirectoryError`. `run.py:66`, `run_config.py:82`, `convert_dsf_to_xml.py:120`
- **`child.tag()` crash** (shared with bindings H1). `run.py:193`
- **Guidance/target/nav connections emitted with wrong names** — `known_pointers` appends `_id` (`guidance_id`), but C++ reads bare `guidance`/`target`/`nav` → connection silently unwired, sim runs unguided. `xml_generator.py` does the opposite, so the two generators contradict. `convert_dsf_to_xml.py:14-21`
- **Boolean round-trip corruption** — `True`→`"True"`, C++ `attrAsBool` accepts only `"true"`/`"1"` → reads `false`. `xml_parser.py:99`, `convert_dsf_to_xml.py:63`

### High
- **`dsf map` divides lat/lon by 57.3** — assumes degrees, HDF5 stores radians (verified against `6DOF.cpp`/`HydroEOM.cpp`/`3DOF.cpp`); `terrain_view`/`cesium_view` treat the same data as radians. `map_view.py:33-53`
- **Monte Carlo stats are fiction** (top-priority #8). `mc.py:111-143`, `mc_cli.py:75-123`
- **`dsf run` loads two copies of the extension** — module-level load of `build/…so` plus `dsf/__init__`'s `python/dsf/…so`; two static factory registries in one process. `run.py:11-38` vs `__init__.py:2`
- **`sys.exit(1)` at import time** in run.py kills any process that merely imports the module. `run.py:35`
- **Cesium GLTF serving broken + directory-traversal file server** bound to all interfaces, no whitelist. `cesium_view.py:487-744`
- **Monte Carlo breaks relative `library` paths** — runs each case with `cwd=case_dir` and raw `LD_PRELOAD`, symlinks only `.dat/.dt2/.tbl`; a deck that works with `dsf run` fails all N cases. `mc.py:244-252`

### Medium (selected)
- `--console-rate` click default `1.0` makes `.dsf` metadata `console_rate` dead; help says "sim time" but code uses wall-clock. `main.py:42`
- Numeric round-trip floats everything (`n="100"`→`"100.0"`, `"1,0,0"`→`"1.0,0.0,0.0"`); block IDs synthesized from `id(element)` are nondeterministic across imports. `xml_parser.py:68,91`
- No sanitization of IDs against the whitespace-sensitive parser (`id="missile eom"` passes through). `xml_generator.py:79`
- `data_loader` renames Vec3 components with axis integers (`Foo_x`→`Foo_0`); folds quaternions into a stray-`_w` (N,3). `data_loader.py:74`
- `sim_session` header prefixing assumes equal channel counts per vehicle → mislabels multi-vehicle telemetry; two `except: pass` hide block failures from watch/MCP. `sim_session.py:148-191`
- `run.py` block-construction duplicates `SimSession.build()` and has already diverged (`tag()` vs `name()`, name-override, report rates). HGT tile loading + lat/lon detection implemented 2–3× with different conventions (void handling differs → -32768 m into Cesium). `run.py:179` vs `sim_session.py:44`; `terrain_view.py`/`cesium_view.py`/`map_view.py`
- `mc.build_index` marks failed cases `done` (sim.log exists on failure too); `MCPlotter` indexes all cases with the first case's column map. `mc.py:342`, `mc_plot.py:76`
- Hardcoded `/home/philip/...` fallback exe path in `mc.py:104` (no env override).

### Low
Numerous: `sys.argv` mutation dispatch (works, fragile); temp-XML/`finalize()` not in try/finally; `load_h5_trajectory` IndexErrors on the 1-D `Time` dataset; dead `_resolve_connections`, debug prints, unreachable `terrain_view.main()` with a conflicting `--decimation` default; `--max-cases 0` treated as unlimited; scatter PNGs overwrite each other. See raw notes.

---

## PyQt6 GUI

### Critical
- **Undo stack holds destroyed items after New/Import/Open** — `scene.clear()` without clearing the undo stack; then Ctrl+Z calls `removeItem` on a freed `QGraphicsItem` → `RuntimeError`/crash. `main_window.py:516,631`, `serializer.py:74`
- **Cycle-detection never unwinds its DFS `path`** — stale entries poison later roots; valid configs get a false "circular dependency" error and are blocked from running. `validation_engine.py:60-76`
- **`scene.changed → _run_validation` feedback loop** — validation calls `item.set_error(None)` → `update()` → re-emits `changed`; perpetual validate/repaint loop pegs a CPU core at idle. `main_window.py:62,564-603`

### High (selected)
- Telemetry `deep_data_ready` **emitted twice per message** (copy-paste) → all plots/map trails 2× with duplicated x-values. `simulation_worker.py:66-69`
- Worker QThreads never stopped in `closeEvent` → "QThread destroyed while running" abort + orphaned subprocess. `main_window.py:18-26`
- `progress` branch unreachable (`if "data"… elif "progress"…` but both keys present) → progress bar stuck at 0; headers message silently discarded. `simulation_worker.py:63-71`
- `stderr=PIPE` never drained → child blocks on a full pipe; sim appears frozen. `simulation_worker.py:43-89`
- Race on `self.process` between GUI `stop()` and worker `run()` (`poll()` on `None`); `finished=pyqtSignal` shadows `QThread.finished` (native cleanup never fires). `simulation_worker.py:9,87-111`
- Instance IDs derived from block *count* → duplicate IDs after any delete, corrupting the cycle-check dict, undo labels, and exported XML. `canvas.py:400`, `main_window.py:980`
- `_probe_headers` overwrites a running `probe_worker` → GC'd live QThread → crash; probe t=0 sample pollutes plot history. `main_window.py:1023`

### Medium / Low (themes)
`RemoveBlockCommand` leaves stale `port.connections` (false-accept + dangling XML ref); `MapWindow.set_headers/update_data` call nonexistent methods; `reset_plots` clears curves but not the tree selection (nothing replots); `resizeEvent` force-fits scene on every resize; `pkill -f viz_receiver.py` + `time.sleep(0.5)` on the GUI thread (kills other instances); UDP `SO_REUSEADDR` defeats the port guard; lon-normalize `while` loops spin forever on `inf`; connections not undoable/deletable; mutable-default vec3 aliased across block instances; broken `gui_tests/` inside the package; committed `egg-info`; 2.5 MB unused duplicate texture; `gui_runtime_debug.xml` written to CWD on every Start; inspector `_show_block_properties` defined twice; unbounded plot/map history. See raw notes for the full 32.

---

## JAX / MCP / Monte Carlo

### Critical
- **MCP unauthenticated RCE + path escape** (top-priority #1). `server.py:51,1989,1999`
- **`dsf_build build_dir` bypasses confinement** — not in `path_params`, runs `cmake`/`make` in any directory with a hostile Makefile. `server.py:1450`

### High
- **JAX requests float64 but never enables x64** — no `jax.config.update("jax_enable_x64", True)` anywhere; all state/params silently downcast to float32 (~0.5 m epsilon at ECI magnitudes) → orbital propagation quietly wrong. `jax/config.py:20`
- `dsf_patch_run_xml` calls the decorated `run_sim` positionally → always `TypeError` (dead tool). `server.py:1436`
- `dsf_report` overwrites `output_file` with the XML path → parses XML as CSV → garbage report. `server.py:1714`
- Arbitrary write-within-FILE_ROOT + `LD_PRELOAD` `library` = local RCE chain (no loadable-lib allow-list). `server.py:1938`

### Medium (selected)
- `run_sim`/`dsf_run_sim` `tmax` param documented but never used. `server.py:334`
- `_running_jobs` mutated/read with no lock → dict-changed-size races; async job log FDs never closed, `Popen` no timeout, sessions/UUIDs never evicted. `server.py:449-462`
- **JAX RK4 is autonomous** (no time passed to `deriv_fn`) while C++ advances the clock at half/full step → non-autonomous dynamics diverge. `jax/integrator.py:11-27`
- `server_for_dumb_models_untested.py` is a ~95% stale copy with broken macro tools (`list_decks(directory=…)`, `_watched_sessions`, `list_components()`) and **no path confinement at all** — delete it. `mcp/`
- `normalize_args` wraps every tool as `def wrapper(**kwargs)`, which may collapse the FastMCP JSON schema to one opaque arg (needs runtime check). `server.py:97-158`

### Verified correct (not bugs)
Gaussian MC semantics agree between C++ (`gauss.h` `mean + y1*stdev`) and JAX (`nominal + sigma*noise`) — sigma is a standard deviation in both, no variance confusion. JAX seeding is reproducible with no key reuse. (C++ and JAX use different RNG engines, so identical seeds match in *distribution* only, not bit-for-bit.)

### Low
JAX `propagate_with_history` drops the remainder of `n_steps % save_every`; nothing is actually `jax.jit`'d despite docstrings; `safe_dumps` only strips the FILE_ROOT prefix and several returns bypass it (absolute-path leak); `finalize()` called under `_watch_lock`; numpy scalars not rounded/serialized in watch values.

---

## Tests & repo hygiene

### High
- **Suite can't run on a fresh clone**: fixtures `fixtures/gps_1.xml`/`.dsf` are git-tracked symlinks to absolute untracked repo-root paths; `pytest.ini` and `CLAUDE.md` are themselves untracked; every sim fixture hard-depends on the sibling `sixdof` repo with `RuntimeError`/`FileNotFoundError` instead of `pytest.skip`.
- **Zero C++ unit tests** — `test/test_tablend.cpp` (a real TableND test) has no `add_executable`; untested: all integrators beyond indirect RK4, the table classes (which the util review just showed are broken), the XML value parser, `monte_carlo.h`, `phase_sequencer.h`, `event.cpp`, CSV output, the factory.
- **MCP server (2002 lines) and the entire JAX subsystem have no tests.**
- Committed binaries: `python/dsf/libsixdof.so.1*` (dodge `*.so` gitignore), two `egg-info/PKG-INFO`.
- `python/dsf/gui_tests/` — broken pre-refactor tests (`../src` imports, `QApplication` at import) shipped inside the package, never collected.

### Medium / Low
- `slow` marker defined/documented but applied to nothing, so `-m "not slow"` skips the 36,000-step session fixtures; `watch_h5` doesn't check the subprocess return code; `test_plot_widget` converts failures to skips and drops `LD_LIBRARY_PATH`; `test_python_blocks` uses `os._exit(0)` to dodge a real HDF5 dtor crash; `test_run_vs_watch` comparisons degrade to skips.
- Dead: `tests_example.cmake` (never `include()`d), root `test/` (assertion-free "verify" scripts + committed CSVs), `examples/visualization/*` imports a moved module and crashes.
- `.gitignore` over-broad: `*.txt`/`*.csv` repo-wide would silently ignore new `CMakeLists.txt`/fixtures; missing `*.egg-info/`, `/output/`, scratch dirs — hence the ~40 untracked files at repo root. Stray `python/dsf.py` shim.

---

## Cross-cutting themes

- **Single-run/process-lifetime kernel meets long-lived Python hosts.** Three process-global singletons (`TClassDict`, integrand dict, `EventBus`) accumulate raw pointers with no teardown; the GUI, MCP session, and Monte Carlo all violate that assumption → dangling-pointer integration on the second run.
- **The Python `dsf run` path is a drifted re-implementation** of `examples/dynamic/main.cpp`: broken class fallback, no events, no Monte Carlo, no `.dsf`-directory support. It should call into a single shared builder (ideally the C++ loader via bindings) rather than duplicating it.
- **Two of everything.** Two extension copies loaded per run; two MCP servers; two MC stat implementations (`mc.py` vs `mc_cli.py`); three interp implementations; three lat/lon-unit conventions; two HGT readers; two generators that disagree on connection naming. The duplication is the direct cause of several of the bugs above.
- **Silent-default error handling** pervades both layers: C++ `attrAs*`/table lookups and Python `except: pass` turn malformed input into zeros/NaNs/empty telemetry that "runs but is wrong."
- **Doc/impl drift** worth fixing in CLAUDE.md: the XML parser is Boost-PT (not hand-rolled); the `.dsf`-directory format is documented but unimplemented; `build/sixdof_build` no longer exists.
