# Proposal: consolidate the C++ and Python sim loaders

*Status: PROPOSAL — not started, pending review. Written 2026-07-11.*

The two entry points that build a sim from a deck — the C++ `dynamic`
executable (`examples/dynamic/main.cpp`) and the Python `dsf run` path
(`python/dsf/cli/run.py` + `python/dsf/utils/sim_session.py`) — each
re-implement the load sequence. Commit 67301ee reconciled the biggest
divergences by sharing `apply_monte_carlo` / `register_events` through
`sim/xml_config.h` and funneling all Python paths (run/watch/GUI/MCP)
through `SimSession`, but the build sequence itself is still duplicated,
and it has drifted.

## Observed drift (live behavioral differences today)

1. **`<sim>` attribute parsing.** C++ uses `SimInput`; `run.py` re-implements
   it by hand (`run.py:138` — "SimInput class isn't bound"). The log-level
   conventions have diverged: C++ maps *ints* (`main.cpp` `mapLevel`, 0/2),
   Python maps *strings* ("verbose"/"critical"). Same deck attribute, two
   interpretations.
2. **Class-name fallback in tree construction.** When a block element has no
   `class=`, C++ (`main.cpp:81`) falls back to `model = child_id`; Python
   (`sim_session.py:133`) falls back to the capitalized *tag name*, and only
   Python honors a `name=` override. A deck relying on either fallback
   behaves differently under `dynamic` vs `dsf run`.
3. **dlopen.** Python's `_load_library` falls back to an XML-relative library
   path; the C++ loader does not.
4. **Strict mode / banner.** The strict-resolution logic (deck attr + CLI
   flag) and the refusal banner are maintained twice (`main.cpp:143-154` +
   `ValidationReport::print_strict_banner` vs `sim_session.py:198-242`).
5. **Output defaults application** duplicated (`main.cpp:93-99` vs
   `sim_session.py:106-109` plus run.py's parsing of `output=`).

## Direction

The shared core must be C++ (the `dynamic` executable cannot depend on
Python), so the approach is *push down and bind* — extend the
`sim/xml_config.h` pattern that already worked for Monte Carlo and events.
Python keeps only its genuine value-add: `.dsf`/JSON→XML conversion,
`RunConfig` metadata overrides, watch lists, the per-step loop, and
introspection (`collect_state`, header prefixing).

### Phase 1 — bind `SimInput`
`main.cpp:20` already carries `// FIXME relocate to DSF with SimInput`.
Move `SimInput` from the example into `DSF/sim/`, bind it, and use it from
`run.py`. Deletes the hand-rolled `<sim>` parsing (~40 lines) and forcibly
unifies the log-level and atol/rtol conventions.

### Phase 2 — one C++ build function
Add `dsf::sim::build_from_xml(doc, SimInput&, BuildOptions&) -> Block* root`
owning: dlopen (with the XML-relative fallback), the instantiate+configure
loop with **one** fallback rule, `warn_unknown_attributes`,
`apply_monte_carlo`, and output defaults. `main.cpp` shrinks to argument
parsing + build + exec (~40 lines). `SimSession.build_tree` becomes a thin
wrapper that calls it, then rebuilds its `(block, xmlnode, id)`
introspection list by walking the returned tree.

**Decision point:** the fallback-rule unification is a behavior change to
one loader or the other. Recommendation: standardize on the Python rule
(capitalized tag, `name=` honored) — `.dsf`-converted decks depend on it,
and the C++ `child_id` fallback looks vestigial. Flag in the commit message.

### Phase 3 — one strict-mode path
Bind `ValidationReport::print_strict_banner` and the strict-resolution
logic so the Python banner string is deleted and both loaders refuse to run
identically.

## Verification

- `python/tests/test_run_vs_watch.py` exists precisely to catch run/watch
  divergence; the sixdof canary in CI exercises real decks through both
  paths.
- Add a small parity test pinning the class-name fallback rule (the live
  difference in item 2), and one pinning log-level interpretation.

## Non-goals

- No change to the step-loop/introspection API (`SimSession.step/collect_state`).
- No change to deck syntax.
- `examples/dynamic` remains a working standalone loader (it just gets thin).
