# DSF Roadmap

Forward-looking work on the DSF **framework** (executive, util, bindings,
Python tooling). Model/vehicle work lives in the sibling sixdof repo — see
`../sixdof/ROADMAP.md` (capabilities) and `../sixdof/AUDIT_ACTIONS.md` (bugs).

This consolidates the former `high_priority.md` and `gap_analysis*.md` notes
(2026-07); completed-work history is in `CODE_REVIEW_ACTIONS.md` and git.
The informal ideas list in `TODO.md` predates this file — its XML-parser
section is resolved; the visualization/GRAM ideas below absorb the rest.

---

## 1. Architecture

### R1. Retire the process-global singletons  *(Phases 1+2 DONE 2026-07-11)*
Each `Sim` now OWNS its integrand registry and event bus; `Instance()`
resolves through a thread_local "active registry" context the Sim scopes
around load/init/step/exec/finalize (RAII), with a process fallback for
standalone harnesses — no model source changes, no Block ABI break.
Retired bugs, pinned by `cpp_multisim_tests` (17 checks, ASan/UBSan
clean) + `python/tests/test_multisim.py` (two interleaved SimSessions):
load-B-wipes-live-A, cross-sim event evaluation/dangling pointers,
destroy-one-continue-other, and cross-thread interference. The factory
(`TClassDict`) and `PropertyNameRegistry` stay global **by design**
(dlopen-time metadata). Remaining: Phase 3 (`config_errors()` →
thread_local) and optional Phase 4 (`Block::addIntegrand` sugar) — see
`R1_SINGLETONS.md`. sixdof rebuilt + pin bumped same day (NOT fail-soft:
a stale model lib registers into the dead global). *(was H4)*

### R2. ~~RK45 per-stage clock time~~  *(DONE 2026-07-11)*
The tick-based clock (2 ticks/dt, purpose-built for RK4's c = 0,½,½,1)
can't represent Dormand-Prince stage times, so RK45 held `t()` frozen at
start-of-step for every stage of every adaptive sub-step — silently ~1st
order for time-forced models. Fix: a continuous `stage_offset` appended to
`Clock` (`t()` = tick time + offset; `Sample()`/report gating stay pure-tick;
offset forced to 0 whenever not mid-integration). Integrators set the offset
per stage; RK4/Verlet migrate to the same mechanism for uniform `t()`
semantics (this also fixes Verlet's step-3 force eval, which ran at t+dt/2
instead of t+dt). Not actually blocked by R1 — the offset is additive on the
existing per-Sim Clock. **Field appended at end of Clock so a stale
`libsixdof.so` fails soft** (sees macro time — the pre-fix behavior).
sixdof rebuilt against the new headers and the RK45 decks
(`f16_*_rk45`) re-verified 2026-07-11. *(was A11)*

### R2b. Adaptive macro stepping  *(future — the "longer steps" payoff)*
Today RK45 adapts **downward only**: sub-steps refine within the deck's
fixed macro `dt` (`h` is clipped to the remaining macro interval), so RK45
can never take a longer step than RK4 — its value is error control and
robustness, at ~2× the per-step cost. Letting the integrator *stretch* the
macro step during smooth flight (orbit coast at seconds-long steps) needs:
(a) an integrator policy driving `Clock::set_dt()` between steps — the
clock already supports rescaled dynamic dt and the `Sample()` report gate
is already robust to arbitrary dt/rate ratios (A6 fix); (b) an audit of
blocks whose discrete logic latches `dt()` at init (filter gains, FCS
integrators, Dryden shaping) to read it per-step instead. Payoff is
long-coast orbit decks (GPS fixtures); aircraft/missile decks are FCS-rate
-bound and gain little. Do after R2.

### R3. ~~Make C++ Monte Carlo dispersions fully honest~~  *(DONE 2026-07-11)*
The numpy pre-draws are now transmitted into each case's XML
(`n_sigma_draw`/`drawn` attributes on `<dispersion>`) and the C++ engine
applies them verbatim (`[pre-drawn]` in the case log), so `mc_draws.json`
records exactly what each sim ran; standalone runs still fall back to the
case-seeded C++ RNG. The stats code is de-duplicated (`load_draws` /
`draw_stats` / `extreme_draws` in `dsf/mc.py`, used by `mc_cli`). Related
`dsf run` fixes (sixdof TRIAGE #23): it now reads `case_id`/`seed` from
`<sim>` so dispatcher case decks run identically through Python, and an MC
deck run without a case prints a nominal-run notice instead of silently
ignoring `<monte_carlo>` (whose dispatcher-only `workers`/`output_dir`
attrs are now consumed, so MC decks pass strict). Pinned by `cpp_mc_tests`
and `python/tests/test_mc_dispatch.py`. *(was A8/A42)*

### R4. Retire the legacy tables  *(blocked on sixdof)*
`Table`/`Table2d` are deprecated in favor of `TableND`, but sixdof's
`TurbofanEngine` (Table2d) and `squib` (Table) still use them. Once those
migrate, delete `Table`/`Table2d`, their pybind bindings, and the duplicated
interpolation code. *(was H13/A40)*

### R5. ~~Decide the `net/` module~~  *(DONE — deleted in b73a8a4)*
`DSF/net/` (stubbed `NetClient`/`NetServer`) was removed per `TODO.md`'s
standing recommendation: couple to external visualizers over a defined
protocol instead of writing our own distribution layer.

### R8. ~~Consolidate the C++ and Python sim loaders~~  *(DONE 2026-07-11)*
All sim-construction logic now lives in C++ once — `sim/SimInput.h` +
`sim/sim_loader.h` (dlopen, output defaults, tree build with ONE
class-name fallback rule, MC application, strict resolution + banner) —
and both loaders are thin callers: `main.cpp` directly, `dsf run` /
`SimSession` via bindings. Python keeps only non-loading work
(`.dsf`→XML conversion, RunConfig→options, watch/introspection loops).
Behavior note: the `dynamic` loader adopted the former Python fallback
(capitalized tag, `name=` honored); its old class=id fallback was
vestigial. Pinned by `cpp_loader_tests`; loaders verified byte-identical
on a live deck. Details: `LOADER_CONSOLIDATION.md`.

## 2. Config & data plumbing

### R6. Unit system / conversion layer
Units are implicit and conventions mixed (some radians, some degrees) —
a recurring bug source. Minimum: a conventions document; better: unit
annotations on block properties (the `PropertyMetadata` direction field
shows the pattern) with conversion at parse time.

### R7. ~~Finish the Python data-loader cleanup~~  *(DONE 2026-07-11)*
`load_h5` is now the only code that opens an output H5 (shared
`_regroup_vec3` for both formats; `load_h5_trajectory` is an adapter;
consumer-less `load_csv_trajectory` deleted). The three per-view
position-channel tables collapsed into `find_geodetic`/`find_ecef` next to
`load_h5`; map/globe/terrain views are load→resolve→render. **Real bug
found and fixed in the process:** angle units vary by model (Equinoctial
logs Latitude/Longitude in *degrees*, 6DOF/Hydro in radians) and the HDF5
`units` attribute says which — `load_h5` now preserves it
(`BlockData.units`) and `find_geodetic` normalizes to radians, fixing
`map_view`'s blanket radians assumption, which was silently wrong for
orbit decks (54 "rad" ≈ 3100°). Pinned by `test_data_loader.py` (units,
aliases, ECEF/ECI preference, flat-format regroup) and verified against a
live Equinoctial deck. The per-model units mess itself is R6's problem —
this at least makes the readers honest about it.

## 3. JAX GPU Monte Carlo track

**Philosophy (settled):** two-track architecture. C++ is the interactive
development workshop and the source of truth; JAX is a derived,
numerically-equivalent pure-function mirror for GPU Monte Carlo. C++
architecture stays as-is. **Unit tests are the transfer standard** — every
ported vehicle gets a C++↔JAX cross-validation suite (identical ICs/params,
state-history agreement to ε). Foundations already in place: JAX RK4 +
vmap MC (`dsf/jax/`), WGS84 gravity / US76 atmosphere / quaternion
kinematics mirrors (sixdof `traj/`), 23/23 cross-validation tests passing.

Remaining port work (priority order):
- **J1. N-D table interpolation** — `jnp.searchsorted` + linear blend;
  `TableND`'s flat row-major layout maps directly.
- **J2. Conditional control flow → `jnp.where` masks** — ground contact,
  rolling airframe. (Consider whether MC even needs ground contact.)
- **J3. Staging via active masks** — pre-allocate all stages,
  `active_mask` gates their force contributions; events flip the mask.
- **J4. Termination masks** — all cases run `n_steps`; a `terminated` flag
  zeroes derivatives; post-process for event times.
- **J5. Dryden turbulence via JAX PRNG** — shaped-noise filter as a
  discrete state-space model alongside the EOM.

C++-side conventions that make porting cheap (do opportunistically):
canonical state-naming table in Doxygen (`///< JAX name: xyz_dot`),
physics-vs-framework section comments in `update()` methods, and
subsystem-level cross-validation tests (gravity, atmosphere, table interp,
DCM↔Euler) so full-EOM tests only verify composition.

**First full vehicle:** the missile intercept demo — simplest complete
stack (6DOF + MissileAero tables + RocketProp + ProNav) without staging or
ground contact.

## 4. Visualization & analysis polish  *(from TODO.md, still wanted)*
- Presentation-quality plots: cartopy + shaded-relief/ArcGIS basemaps,
  animated ground tracks, zoomed launch/entry insets.
- Exports for external players (Google Earth KML, X-Plane).
- GRAM atmosphere integration (NASA SUA required) as an `AtmosBase`
  subclass — needed for dispersion-grade Monte Carlo.
- Flex-body / slosh and aeroheating are **model** gaps → sixdof roadmap.
