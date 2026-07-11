# DSF Code Review — Action Checklist

## Implementation status (this pass)

**Done & verified by tests** — all P0 items plus most P1/P2:
- P0: A1 (MCP loopback default + `--allow-remote` gate, path-semantics containment, `build_dir` confinement), A2/A3/A5/A21/A22 (table interp + Mat4 + bounds/load), A4 (`tag()`→`name()`), A6 (clock init + report gate), A7 (pybind `keep_alive` + null guards), A9 (map units), A16/A17 (connection naming + bool round-trip).
- P1: A10 (RK45 NaN/cap), A12 (integrand/event clear on load), A13 (dt/tmax validation), A14 (recurring events), A18 (Vec3 ==), A19 (Mat3 CSV), A20 (constants), A23 (JAX x64), A25/A26/A27/A28/A29 (GUI undo/cycle-detect/validation-loop/worker/threads+ids), A30 (debug prints), A31 (MCP tool bugs), A34/A35/A36 (single `.so` load, dlopen restore, no import-exit).
- P2/P3: A32 (`-fpermissive` removed), A33 (packaging `__init__`/deps/data), A38 (util PIC), A39 (de-symlinked fixtures), A41 (deleted stale MCP server), A43 (.gitignore), A45 (CLAUDE.md), A46 (C++ ctest: `cpp_util_tests`, `cpp_kernel_tests`, `cpp_tablend_tests`; + `test_validation_engine.py`).
- Bonus (found while fixing): `data_loader.load_h5` fabricated `times=arange(N)` because it ignored the root-level `Time` dataset → fixed (this had broken run-vs-watch alignment); `test_dsf_bindings` quaternion identity test used scalar-last convention → fixed; `dsf.visualization` imported a non-existent `GlobeViewer` → fixed.

**Done in the 2026-07-11 pass (MC honesty + P2 closeout):**
- **A8/A42** — pre-draws are now transmitted into each case's XML
  (`n_sigma_draw`/`drawn` on `<dispersion>`) and applied verbatim by C++
  (`[pre-drawn]` in case logs); `dsf run` reads `case_id`/`seed`; MC decks
  pass strict; stats de-duplicated into `dsf/mc.py` helpers. Pinned by
  `cpp_mc_tests` + `python/tests/test_mc_dispatch.py`; verified end-to-end
  (batch draws == applied values). See ROADMAP R3.
- **A37** — events + Monte Carlo are bound and shared with the C++ loader
  via `sim/xml_config.h` (both loaders run the same code). The
  phase-sequencer half is moot: `phase_sequencer.h` is a header-only *model*
  utility (consumed by sixdof FCS code), not an executive feature — there is
  nothing loader-visible to bind.
- **A38 residuals** — `sim`/`util` are now OBJECT libraries aggregated into
  `libDSF.so` (every source compiled exactly once; the old root list had
  drifted — `mat4.cpp`/`quat.cpp` were only compiled there and are now in
  `util`'s list). pybind11: `find_package` first, FetchContent fallback
  (offline builds work with pip/system pybind11 installed).
- **A34/A35 residuals** — `run.py` selects the extension by this
  interpreter's exact ABI tag (`EXT_SUFFIX`) before falling back to a glob,
  and warns on stderr when the loaded copy is older than another discovered
  copy (the build/-vs-pip stale-shadow gotcha is now self-diagnosing).
- **A33 acceptance verified** — clean-venv **non-editable** `pip install .`
  yields a working `dsf` CLI: extension + `libDSF.so` bundled in the wheel
  ($ORIGIN rpath, no LD_LIBRARY_PATH needed for the core), and a real deck
  runs end-to-end against `libsixdof.so`.

**P3 closeout (2026-07-11):** A41/A43-artifacts/A44 were already clean (verified: no tracked binaries/egg-info/dead test dirs; `.gitignore`'s repo-wide `*.txt`/`*.csv` kept deliberately with `!CMakeLists.txt`-style negations). A46 gaps filled: XML value parsing (`attrAsVec3/Mat3/Bool` comma/whitespace/malformed forms) and factory-by-name tests added to `cpp_util_tests` (74 checks). A40 superseded by ROADMAP R4 (legacy tables are deletion-bound, not consolidation-bound).

**Deferred (documented, not code-changed)** — reason noted inline:
- **A11** (RK45 per-stage clock time) — architecture-blocked: the tick-based clock (2 ticks/dt) can't represent Dormand-Prince stage times; documented as a known limitation in `integrator_rk45.cpp`. Use RK4 for strongly time-dependent dynamics.
- **A15** (`.dsf`-as-directory) — the format is a JSON file in practice; CLAUDE.md now says so rather than implementing the unused directory layout.
- **A40** (fully merge the 3 interp implementations) — the correctness bugs are fixed and covered by tests; the DRY consolidation is cosmetic and deferred.

---


Actions distilled from `CODE_REVIEW.md`, ordered highest → lowest priority. Each item is scoped to a fix, with the file(s) to touch and a one-line acceptance check. Tick the box when done.

Priority tiers:
- **P0** — security holes, silent-wrong-physics, crashes on common paths. Fix before any real use.
- **P1** — correctness bugs that produce wrong results or crashes on specific (non-rare) inputs.
- **P2** — build/packaging/robustness that blocks distribution or hides future errors.
- **P3** — duplication, dead code, docs, hygiene.

---

## P0 — Security / silent-wrong-physics / crashes

- [ ] **A1. Lock down the MCP server.** Default `--host` to `127.0.0.1`; gate `0.0.0.0` behind an explicit `--allow-remote` + auth token. Replace `startswith(str(FILE_ROOT))` containment with `Path.is_relative_to` (or compare against `FILE_ROOT + os.sep`). Add `build_dir` to `path_params` so `dsf_build` can't run in an arbitrary dir; add a loadable-`library` allow-list. `python/dsf/mcp/server.py:51,60-62,1450,1938,1989,1999` — *Accept:* remote request to `dsf_write_file` refused without token; `../sixdof_secrets` rejected.
- [ ] **A2. Fix 1D `Table` interpolation.** Rewrite the bracket search in `interp()` so the last panel and 2/3-point tables interpolate correctly. `DSF/util/tbl/tbl.cpp:180-207` — *Accept:* `interp(2.5)` on {0,1,2,3}→{0,10,20,30} returns 25; 2-point table {0→0,1→10}, `interp(0.5)`=5.
- [ ] **A3. Fix `Table2d` below-range read.** Clamp/guard when `val < table[0][0]` (binary search returning `right=-1`). `DSF/util/tbl/tbl2d.cpp:101-128` — *Accept:* ASan clean on a below-first-breakpoint query.
- [ ] **A4. Bind `xmlnode.tag()` or fix the caller.** Either add a `tag()` binding or change `run.py` to use `name()`, and match the C++ loader's *id* fallback (not capitalized tag). `python/dsf/cli/run.py:193`, `python/bindings/bindings_util.cpp:161` — *Accept:* `dsf run` on a deck with a `class`-less `<sim>` child runs without `AttributeError`.
- [ ] **A5. Implement `Mat4::det/inv/transpose`** (correct 4×4 math) or remove the bindings until implemented. `DSF/util/math/mat4.cpp:32-71`, `python/bindings/bindings_util.cpp:121-123` — *Accept:* `Mat4(identity).det()==1`, `inv(A)*A≈I`.
- [ ] **A6. Initialize `Clock::safe_sample` and fix the report gate.** Init all members in both constructors; replace the exact float-equality sample test with a tolerance/tick-count comparison; guard the `(int)` cast. `DSF/sim/clock.h:29-42,62-72,93` — *Accept:* a sim with `rpt=0.1, dt=1/30` writes the expected number of telemetry rows.
- [ ] **A7. Add pybind lifetime tethering.** `keep_alive<1,2>` on both `Sim::load` overloads; guard `Block` time methods and `Sim` accessors against null/unloaded state (or don't expose the default ctors). `python/bindings/bindings_sim.cpp:74-78,164-170` — *Accept:* `dsf.Block().t()` and `dsf.Sim().step()` raise a Python exception, not segfault; `sim.load(dsf.Block(),…); sim.run()` doesn't UAF.
- [x] **A8. Make Monte Carlo dispersions real.** Either transmit the numpy pre-draws into each C++ case (so reported σ matches applied values) or drop the numpy pre-draw and read back what C++ actually drew. `python/dsf/mc.py:111-143`, `python/dsf/cli/mc_cli.py:75-123`, `DSF/sim/monte_carlo.h:214` — *Accept:* reported per-case draw equals the value the sim applied (spot-check one case).
- [ ] **A9. Fix `dsf map` lat/lon units.** Stop converting radians→radians; honor the dataset `units` attr (HDF5 stores radians). Unify the lat/lon-unit convention across `map_view`/`terrain_view`/`cesium_view`. `python/dsf/cli/map_view.py:33-53` — *Accept:* a 34°N trajectory plots at 34°N.

---

## P1 — Correctness bugs

- [ ] **A10. RK45: cap rejections and reject NaN.** Add a max-iteration/failure escape; treat NaN error as a rejected step (don't let `std::max(x,NaN)` accept it). `DSF/sim/integrator_rk45.cpp:199-213` — *Accept:* a NaN-producing model terminates with an error instead of hanging/propagating NaN.
- [ ] **A11. RK45: advance clock per stage.** Evaluate stage times at `t + a_i*h`. `DSF/sim/integrator_rk45.cpp:96-218` — *Accept:* a time-explicit forcing term integrates to the analytic result to method order.
- [ ] **A12. Integrand/event deregistration.** Add `remove`/`clear` to `TIntDict` and call it on block teardown and Sim reload; call `EventBus::clear()` on teardown. `DSF/sim/TIntDict.h`, `DSF/sim/sim.cpp`, `DSF/sim/event.cpp:117-124` — *Accept:* two consecutive `Sim::load`/`run` cycles in one process don't integrate stale pointers (ASan clean).
- [ ] **A13. Validate `dt`/`tmax` from XML.** Reject missing/zero/negative `dt` and `tmax` with a clear error. `DSF/sim/sim.cpp:75`, `DSF/util/xml/xml.h` — *Accept:* a deck missing `dt` errors out instead of looping forever.
- [ ] **A14. Recurring events.** Only latch `armed=false` when `one_shot`; don't let `fired` permanently block re-fire. `DSF/sim/event.cpp:16-17,191-193` — *Accept:* a `one_shot=false` event fires on every threshold crossing.
- [ ] **A15. `.dsf`-as-directory support.** Implement the documented directory format (`project.xml` inside) in the three loaders, or update the docs to match reality. `python/dsf/cli/run.py:66`, `python/dsf/utils/run_config.py:82`, `python/dsf/utils/convert_dsf_to_xml.py:120` — *Accept:* `dsf run myproject.dsf/` works.
- [ ] **A16. Connection naming: pick one generator.** Reconcile `convert_dsf_to_xml.py` (`guidance_id`) with `xml_generator.py` (bare `guidance`) so emitted names match what C++ reads. `python/dsf/utils/convert_dsf_to_xml.py:14-21`, `python/dsf/utils/xml_generator.py:107` — *Accept:* a GUI-drawn guidance/target/nav connection resolves in the sim.
- [ ] **A17. Boolean round-trip.** Emit `"true"/"false"` (lowercase) so C++ `attrAsBool` reads them; stop floating `"1"`→`"1.0"` for bool-typed attrs. `python/dsf/utils/convert_dsf_to_xml.py:63`, `python/dsf/utils/xml_parser.py:99` — *Accept:* import `enabled="true"` → save → C++ reads `true`.
- [ ] **A18. `Vec3` comparison operators** compare components, not magnitude. `DSF/util/math/vec3.cpp:149-184` — *Accept:* `Vec3(1,0,0)==Vec3(0,1,0)` is false.
- [ ] **A19. Mat3 CSV output** — fix row-breaking `endl`s and reconcile header/column/value counts. `DSF/sim/output.h:104-105`, `DSF/util/math/mat3.cpp:244-249` — *Accept:* a sim logging a Mat3 produces a parseable single-row-per-step CSV.
- [ ] **A20. Correct constants.** `J2_EARTH=1.08262998e-3`, `PI`/`RAD`/`C_DEG` to full double precision (use `M_PI`). `DSF/util/math/earth_constants.h:23`, `DSF/util/math/constants.h:13-15` — *Accept:* values match WGS84/`M_PI` to machine precision.
- [ ] **A21. `TableND` bounds.** Guard fixed `int[8]`/`double[8]` against `D>8`; handle single-point axes; validate data length vs axis-size product. `DSF/util/tbl/tablend.cpp:24-57,183-235` — *Accept:* ASan clean on a 9-D table and a 1-point-axis table.
- [ ] **A22. Table load/error paths.** Remove blocking `cin >> xx`; on missing file/table return a clean error instead of leaving `max=-1` and OOB-reading. `DSF/util/tbl/tbl.cpp:26-61,165`, `DSF/util/tbl/tbl2d.cpp:26` — *Accept:* headless `dsf run` on a missing table errors, doesn't hang.
- [ ] **A23. JAX float64.** Call `jax.config.update("jax_enable_x64", True)` at package import. `python/dsf/jax/config.py` — *Accept:* `make_state0(...).dtype == float64`.
- [ ] **A24. `parse.h`/`attrAsVec3` whitespace + zero-fill.** Don't silently push 0 on extraction failure; support space-separated vectors (or reject them loudly). `DSF/util/parse.h:50-57`, `DSF/util/xml/xml.h:143`, `xml.h:268-277` (null-root guard) — *Accept:* `position="1 2 3"` yields `(1,2,3)` or a clear error, never `(0,0,0)`.
- [ ] **A25. GUI: undo stack vs `scene.clear()`.** Clear the undo stack on New/Import/Open. `python/dsf/gui/ui/main_window.py:516,631`, `python/dsf/utils/serializer.py:74` — *Accept:* add block → New → Ctrl+Z doesn't crash.
- [ ] **A26. GUI: cycle-detection DFS.** Unwind `path` on return; only flag actual cycle members. `python/dsf/gui/core/validation_engine.py:60-76` — *Accept:* `A→B→C→B` plus `D→A` doesn't flag `D`; a valid graph runs.
- [ ] **A27. GUI: validation feedback loop.** Break the `scene.changed → set_error → update → changed` cycle (debounce, or don't mutate items during validation). `python/dsf/gui/ui/main_window.py:62,564-603` — *Accept:* idle GUI with a block on canvas doesn't peg a CPU core.
- [ ] **A28. GUI sim-worker fixes (batch).** Remove the double `deep_data_ready.emit`; fix `if data … elif progress` (both keys present); drain stderr concurrently; fix the `self.process` GUI/worker race; rename the `finished` signal so it doesn't shadow `QThread.finished`. `python/dsf/gui/execution/simulation_worker.py:9,43-111` — *Accept:* plots receive each sample once; progress bar advances; Stop doesn't raise; large-stderr sims don't freeze.
- [ ] **A29. GUI: stop worker threads on close + unique instance IDs.** Stop `sim_worker`/`probe_worker` in `closeEvent`; derive instance IDs from a monotonic counter, not block count. `python/dsf/gui/ui/main_window.py:18-26,980,1023`, `canvas.py:400` — *Accept:* closing mid-run doesn't abort; delete-then-add doesn't reuse an ID.
- [ ] **A30. Remove PyBlock debug prints.** Strip `std::cout` from the trampoline. `python/bindings/bindings_sim.cpp:19-44` — *Accept:* `dsf run` prints no `[PyBlock::…]` lines; rebuild + re-copy `.so`.
- [ ] **A31. MCP broken tools.** Fix `dsf_patch_run_xml` (call `run_sim` by keyword), `dsf_report` (don't overwrite `output_file` with the XML path), and the unused `tmax` param. `python/dsf/mcp/server.py:334,1436,1714` — *Accept:* each tool returns a real result on a smoke test.

---

## P2 — Build / packaging / robustness

- [x] **A32. Remove `-fpermissive` via one `const` overload.** Add `const Vec3& operator[](int) const` to `Mat3`; delete `-fpermissive` from all six targets. `DSF/util/math/mat3.h:68`, all `CMakeLists.txt` — *Accept:* full build succeeds with no `-fpermissive`.
- [x] **A33. Fix Python packaging.** Add `__init__.py` to `dsf/gui`, `dsf/utils`, (drop or fix `dsf/gui_tests`); add `install()`/`package_data` for the extension; add missing deps (`jax`, `matplotlib`, `mcp`, `pydantic`); stop shipping top-level `tests`. `python/setup.py`, `CMakeLists.txt` — *Accept:* `pip install .` (non-editable) yields a working `dsf gui`/`dsf watch`.
- [x] **A34. Single extension copy.** Make `dsf run` and `import dsf` load the same `.so` (install it, or load from one canonical location). `python/dsf/cli/run.py:11-38`, `python/dsf/__init__.py` — *Accept:* one `dsf_core` module object per process.
- [x] **A35. dlopen-flag and .so-glob robustness.** Save/restore `sys.setdlopenflags`; select the `.so` by exact ABI tag, not first-glob. `python/dsf/cli/run.py:11-27` — *Accept:* importing h5py after `dsf.cli.run` doesn't change its flags; correct `.so` picked when two ABIs coexist.
- [x] **A36. Move import-time `sys.exit`/side-effects out of module scope** in run.py into `main()`. `python/dsf/cli/run.py:35-38` — *Accept:* `import dsf.cli.run` doesn't kill the process.
- [x] **A37. Bind `<events>` / Monte Carlo / phase sequencer** (or route `dsf run` through the C++ loader) so the Python path matches `examples/dynamic/main.cpp`. `python/bindings/bindings_sim.cpp`, `python/dsf/cli/run.py` — *Accept:* an event-terminated deck ends at the event via `dsf run`.
- [x] **A38. CMake cleanup.** Give `util` PIC; stop double-compiling sim/util sources into `libDSF.so`; reconcile the drifted source lists; make pybind11 discoverable offline. `CMakeLists.txt:58-79`, `DSF/util/CMakeLists.txt` — *Accept:* clean build, no duplicate-symbol / relocation warnings.
- [x] **A39. Test suite runs on a fresh clone.** De-symlink fixtures (commit real files under `fixtures/`); track `pytest.ini`; `pytest.skip` when sixdof is absent. `python/tests/fixtures/`, `pytest.ini`, `python/tests/conftest.py` — *Accept:* `git clone` + `pytest -m "not slow"` collects and runs (skipping sixdof tests) without errors.

---

## P3 — Duplication / dead code / docs / hygiene

- [x] **A40. Consolidate the three interpolation implementations.** SUPERSEDED by ROADMAP R4: `Table`/`Table2d` are deprecated and slated for deletion once sixdof migrates `TurbofanEngine`/`squib` to `TableND` — consolidating their internals first would be wasted motion. Correctness is already pinned by `cpp_util_tests`/`cpp_tablend_tests`.
- [x] **A41. Delete `server_for_dumb_models_untested.py`** (stale, broken, no path confinement). `python/dsf/mcp/`
- [x] **A42. De-duplicate MC stats** (`mc_cli.py` should call `MonteCarlo` methods, not reimplement). `python/dsf/cli/mc_cli.py` vs `python/dsf/mc.py`
- [x] **A43. Remove committed binaries/artifacts.** `python/dsf/libsixdof.so.1*`, `*.egg-info/`, stray `python/dsf.py`, root `test/` outputs. Update `.gitignore` (drop repo-wide `*.txt`/`*.csv`; add `*.egg-info/`, `/output/`, scratch dirs).
- [x] **A44. Delete/port dead tests & examples.** `python/dsf/gui_tests/` (broken), root `test/` verify-scripts, `tests_example.cmake` (unwired), `examples/visualization/*` (moved-module import). Wire `test/test_tablend.cpp` into CTest (it now guards A2/A21).
- [x] **A45. Correct CLAUDE.md gotchas.** XML parser is Boost Property Tree, not hand-rolled (residual whitespace bug is in *value* parsing); note `.dsf`-directory status; `build/sixdof_build` no longer created. `CLAUDE.md`
- [x] **A46. Add C++ unit tests** for integrators (RK4/RK45/Verlet), tables, XML value parsing, events, and the factory. All covered: `cpp_util_tests` (tables, math, config validation, XML value parsing, factory-by-name), `cpp_tablend_tests`, `cpp_kernel_tests` (clock, events), `cpp_integrator_tests`, `cpp_mc_tests`.

---

### Suggested working order
A1 (security) → A2/A3/A21/A22 (tables, with A46's `test_tablend` as the harness) → A6/A10–A14 (kernel correctness) → A32 (unblocks clean builds) → A4/A7/A30 (bindings) → A25–A29 (GUI) → A8/A9/A15–A17/A23 (Python correctness) → A33–A39 (packaging/tests) → P3 cleanup.
