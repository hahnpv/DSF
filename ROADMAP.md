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

### R1. Retire the process-global singletons  *(highest leverage remaining)*
`TClassDict`, the integrand dictionary (`TIntDict`), `EventBus`, and the
newer `PropertyNameRegistry` / `config_errors()` are process-global with no
ownership. Clear-on-load patches the symptom; the design is why GUI /
MCP-session / Monte-Carlo hosts are fragile — a second sim in one process
walks on the first's state. Real fix: each `Sim` **owns** its integrand
registry and event bus (dependency-injected). Meaningful refactor; retires a
whole class of latent bugs. *(was H4)*

### R2. RK45 per-stage clock time  *(blocked by R1's clock work)*
The tick-based clock (2 ticks/dt) can't represent Dormand-Prince stage
times; documented as a known limitation in `integrator_rk45.cpp`. Use RK4
for strongly time-dependent dynamics until the clock gains a continuous
stage time. *(was A11)*

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

### R8. Consolidate the C++ and Python sim loaders  *(proposal, pending review)*
`examples/dynamic/main.cpp` and `dsf run` (`run.py` + `SimSession`) each
re-implement the build sequence and have drifted (class-name fallback,
log-level conventions, dlopen fallback, strict banner). Plan: push the
build sequence down into shared C++ (bind `SimInput`, one
`build_from_xml`, one strict path) — full write-up in
`LOADER_CONSOLIDATION.md`.

## 2. Config & data plumbing

### R6. Unit system / conversion layer
Units are implicit and conventions mixed (some radians, some degrees) —
a recurring bug source. Minimum: a conventions document; better: unit
annotations on block properties (the `PropertyMetadata` direction field
shows the pattern) with conversion at parse time.

### R7. Finish the Python data-loader cleanup
The file-level merge already happened — `dsf/visualization/data_loader.py`
was migrated into `dsf/utils/data_loader.py` (shim re-export remains in
`dsf/visualization/__init__.py`). Residual duplication: the Vec3-regrouping
logic is copy-pasted between `load_h5`'s hierarchical/flat branches;
`load_h5_trajectory` re-implements H5 reading instead of adapting
`load_h5`; `load_csv_trajectory` appears to have no consumers; and three
CLI views each carry their own position-channel guessing
(`map_view` LAT/LON aliases, `globe_view` ECEF keys,
`terrain_view.load_trajectory` — a whole third H5 reader). Fix: one
channel-resolver next to `load_h5`; views become load→resolve→render.

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
