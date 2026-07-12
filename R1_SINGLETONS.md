# Plan: R1 — retire the process-global singletons

*Status: Phases 1+2 IMPLEMENTED 2026-07-11 (this document was the plan;
deviations noted inline). Phase 3 (config_errors → thread_local) and the
optional Phase 4 remain. ROADMAP R1.*

One process, one simulation: that assumption is baked in as four
process-global registries. It is why a second `Sim` in the same process
walks on the first's state, why the GUI / MCP-session / future in-process
Monte-Carlo hosts are fragile, and why `Sim::load` has to defensively
clear global state (the A12 patch — which *protects sequential* reuse by
*breaking interleaved* reuse: loading sim B wipes a still-live sim A).

## Inventory — what is actually global, and what should be

| Registry | Mutable per-run? | Who writes it | Verdict |
|---|---|---|---|
| `TClassIntegrandDict<Block>` (TIntDict.h) | **yes** — raw state/derivative pointers into live block instances | models' `init()` (**13 sixdof files** + DSF test models), integrators read | **move to Sim** — the core of R1 |
| `EventBus` (event.h) | **yes** — conditions hold raw `double*` into a sim's Output | `xml_config::register_events`, `Sim::step` evaluates | **move to Sim** — DSF-internal only (sixdof never touches it) |
| `dsf::util::config_errors()` | **yes** — per-load error list | table loaders deep in util (constructed during `configure()`, **no Sim context available**) | **thread_local** — see Phase 3 |
| `TClassDict<Block>` (factory) | no — populated at static-init/dlopen | class registration macros | **stays global, deliberately** — dlopen-time metadata has no Sim to belong to |
| `PropertyNameRegistry` | no — same | `DSF_PROPERTY*` macros | **stays global, deliberately** |

Live bugs this retires (worth pinning in tests before/with the fix):
1. **Interleaved sims**: `Sim::load` for B clears A's integrand registry —
   stepping A afterwards integrates nothing (or worse, B's states).
2. **Event cross-talk**: both sims' events sit on the one `EventBus`;
   whichever sim steps evaluates (and can fire/terminate on) the other
   sim's events, through dangling `double*` if that sim's Output is gone.
3. **Validation cross-talk**: `config_errors()` drained by whichever
   validate runs first; concurrent GUI + MCP loads misattribute table
   errors.

## Design

**Ownership**: `Sim` owns its integrand registry and event bus as plain
members. Integrators receive the registry the same way they already
receive the clock (`IntegratorBase::clock` set by `Sim::load` — add
`integrands` beside it). `register_events` already takes `Sim&`; it adds
to `sim.events()` instead of the singleton.

**The model-API problem**: models call
`TClassIntegrandDict<Block>::Instance()->add(...)` inside `init()`. We
cannot dependency-inject through that call site without touching every
model. Two constraints shape the solution:

- Adding members to `Block` is a **hard ABI break** for every model
  library (derived-class member offsets shift — not fail-soft like R2's
  Clock append). Avoid until/unless a coordinated break is scheduled.
- `Instance()` must keep working through the transition (13 sixdof call
  sites + DSF's own test models).

So: an **active-registry context**, not constructor injection.
`Instance()` becomes "return the currently-active registry":

```cpp
static TClassIntegrandDict<TClass>* Instance() {
    if (current_) return current_;          // set by the owning Sim
    static TClassIntegrandDict<TClass> fallback;  // standalone/test use
    return &fallback;
}
static void make_current(TClassIntegrandDict<TClass>* r) { current_ = r; }
static thread_local TClassIntegrandDict<TClass>* current_;
```

`Sim` sets `make_current(&integrands_)` for the duration of `load()`,
`init()`, `step()`/`exec()`, and `finalize()` (RAII guard so exceptions
restore it). `thread_local` means a GUI worker thread's sim and a
main-thread probe sim are isolated *for free*; two sims on one thread are
isolated because each swaps the context in around its own calls. The
fallback registry keeps `test_integrators.cpp`-style standalone harnesses
(no Sim at all) working unchanged.

This is still ambient state — but confined to one documented mechanism
with a Sim-scoped lifetime, instead of four independent forever-globals.
True constructor injection (`Block::addIntegrand` backed by a Sim ref)
remains available as a later cleanup once a Block ABI break is scheduled
for other reasons; it is NOT required to fix the bugs.

## Phases

### Phase 1 — Sim owns TIntDict + EventBus  *(the meat; DSF-internal)*
- `Sim` gains `TClassIntegrandDict<Block> integrands_;` and
  `EventBus events_;` members + accessors.
- `TClassIntegrandDict`: add the thread_local `current_` + `make_current`
  + RAII `ScopedRegistry` guard; `Sim::load/init/step/exec/finalize` wrap
  themselves in it. Delete the clear-on-load *for the registry members*
  (a fresh Sim starts empty by construction); keep `clear()` for the
  fallback registry path.
- `EventBus`: same treatment (`Instance()` → thread_local current with
  fallback), `Sim::step` uses `events_` directly, `xml_config.h` uses
  `sim.events()`. sixdof has zero references — no model impact.
- Integrators: UNCHANGED (deviation from the original plan, simpler):
  they keep calling `Instance()`, which resolves to the owning Sim's
  registry because `Sim::step/exec` hold the scoped context around
  `propagate()` — and to the fallback in standalone harnesses. Zero
  integrator churn, and every step exercises the same context path the
  models use.
- Bindings: nothing user-visible changes (`apply_monte_carlo` walks the
  *factory* metadata, which stays global; `register_events` already takes
  the Sim).
- **Models rebuild but do not change**: their `Instance()->add(...)`
  calls land in the owning Sim's registry via the context. Requires the
  sixdof rebuild + pin bump (inline `Instance()` changed), but no source
  edits.

### Phase 2 — pin the wins with tests
- C++ `cpp_multisim_tests`: (a) two Sims loaded in one process, stepped
  interleaved → both trajectories match their solo runs; (b) an event
  registered on sim A never fires from sim B's step; (c) destroy A,
  continue B (dangling-pointer regression, run under the ASan job);
  (d) two Sims on two threads stepping concurrently (thread_local
  isolation).
- Python: a `SimSession` × 2 interleaved test (the GUI/MCP host shape) —
  build both, step alternately, assert telemetry independence.

### Phase 3 — `config_errors()` → thread_local  *(small)*
Writers (table loaders) have no Sim context and shouldn't grow one;
`inline std::vector<std::string>& config_errors() { static thread_local ... }`
plus a note that attribution is per-thread (matches how the GUI/MCP
actually run concurrent loads). `validate_config` behavior unchanged.

### Phase 4 — optional end-state  *(defer until a Block ABI break is scheduled)*
`Block::addIntegrand(x, dx, type)` sugar routed through the context (no
layout change — non-virtual inline), mechanical migration of the 13
sixdof call sites, then deprecate direct `Instance()` use. Pure hygiene;
schedule opportunistically with the next coordinated break.

## Coordination / ABI

- Phase 1 changes header-inline code that models compile against
  (`TIntDict.h`) → **sixdof rebuild + `DSF_VERSION` pin bump required**,
  same dance as R2. No sixdof source changes. Unlike R2's Clock append,
  a stale `libsixdof.so` here is NOT fail-soft (its inline `Instance()`
  would use the old global singleton while DSF's integrators read the
  Sim-owned registry → models' states silently not integrated). Land
  DSF + sixdof pin bump together; expect a red canary in between.
- R2's revalidation already landed (2026-07-11), so this is its own
  pin bump — coordinate a window with any active sixdof work.

## Risks

- **Any DSF-internal caller of `Instance()` outside a Sim context** ends
  up on the fallback registry. Audit is short (7 files found); the
  integrators move to the member pointer, `sim.cpp` to members, leaving
  only the test harness — which *wants* the fallback.
- **Sub-block registration timing**: models register in `init()`, which
  `Sim::init()` drives inside the scoped context — safe. Anything
  registering integrands in `configure()` (none known) would land in the
  fallback under `dsf run`'s current build order; the Phase-2 tests plus
  a one-line warning when the fallback registry is non-empty at
  `Sim::init` catch this class.
- **GUI/MCP threads**: thread_local context assumes one sim per thread at
  a time — true for SimSession usage today; the RAII guard makes nesting
  safe (restores previous).

## Non-goals

- No change to the factory (`TClassDict`) / property-metadata registries —
  global by design; document that in their headers.
- No `Block` layout change, no model source changes (until Phase 4).
- No parallel *in-process* Monte Carlo implementation — this plan removes
  the architectural blocker; the MC host itself is separate work.

## Effort

Phase 1+2 ≈ one focused session plus regression (all C++ suites, targeted
Python, smoke decks, ASan job). Phase 3 minutes. Cross-repo pin bump
shared with R2's pending revalidation.
