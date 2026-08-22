# JAX Simulation Framework — Maturation Plan (work order)

**Status:** proposed · **Owner:** (remote agent) · **Consumers:** the ART
reentry program (`/opt/hahn-aero/art_reentry/`) — but the capability is
general-purpose and stands on its own.

This is a self-contained work order. It assumes only this repo (`/opt/DSF`), the
sibling `/opt/sixdof`, and `/opt/hahn-aero/traj` as the fidelity reference. It
does **not** assume the ART code is present on this box.

---

## 1. What we are building and why

A **differentiable, `jit`+`vmap`, dispersion-batched trajectory rollout in JAX**,
matured from the existing proof-of-concept mirror in
`/opt/sixdof/py/sixdof_jax/`.

It has to be good enough to serve **two masters at once**:

1. **Gradient-based training** — a differentiable rollout of a guidance schedule
   so a learned model can be fine-tuned on *task loss* (target miss + path
   constraints), not just imitation. Needs `grad` through the whole flight wrt
   the schedule parameters.
2. **Monte Carlo verification** — thousands of dispersed closed-loop rollouts per
   call (`vmap` over density, wind, nav-error, IC, aero dispersions) to certify
   guidance robustness where a point-optimal solve cannot.

Same rollout, both jobs. Maturing it pays twice. Today it is a POC: the model
mirrors exist and a cross-validation test exists, but it is not validated across
the reentry envelope, not packaged as a batched dispersed rollout, and has no
gradient/task-loss harness.

## 2. Current state (audited 2026-08-22)

Present in `/opt/sixdof/py/sixdof_jax/`:

| module | role |
|---|---|
| `atmos1976.py` | US76 atmosphere |
| `gravity.py` | gravity (J2; golden-tested) |
| `aero.py` | aero model |
| `propulsion.py` | engine models |
| `eom_3dof.py`, `eom_3dof_staged.py` | 3-DOF point-mass EOM (+ staged) |
| `guidance.py` | guidance laws |

Tests in `/opt/sixdof/py/tests/`: `test_jax_cross_validation.py` (vs C++ sixdof,
+ vmap consistency + MC *smoke*), `test_gravity_golden.py`, `test_wind_dryden.py`,
`test_staged_trajectory.py`, `test_deck_jax_comparison.py`. Run with
`conda activate DSF && python -m pytest py/tests/ -v` (float64 enabled in-test).

**Gaps to close** (this plan):
- No **reentry-specific** rollout: need WGS84 flight-path glide state
  `(h, V, γ, χ, σ)` matched to `traj.EOM.JaxWGS84FlightPath`, and
  **Sutton-Graves stagnation heat flux** as a path-constraint output.
- Cross-validation is pointwise/smoke, not **envelope-wide to tolerance** and not
  **whole-trajectory** against traj + C++ sixdof.
- No **dispersion layer** (density ±30% @ 60–80 km, winds, nav error, aero, IC)
  as a `vmap` batch.
- No **differentiable task-loss** head (miss + heat/g/γ penalties) with verified
  gradients.
- No **6-DOF-lite** option (trim α(M), bank-rate / actuator limit) to expose the
  3→6-DOF flyability gap.

## 3. Reference & tolerance policy

Truth models, in order: **C++ `sixdof`** (production truth) and
**`traj.EOM.JaxWGS84FlightPath`** (the optimizer's model). The BO study holds
traj↔sixdof agreement to **1e-9** on the real-gas law and reproduces crossrange
to the km / tof to the second — hold this rollout to the same bar:

- **Per-model** (atmos, gravity, aero, heat): relative error ≤ **1e-9** vs C++ at
  matched inputs across the envelope grid.
- **Whole-trajectory** (a fixed schedule flown end-to-end): final state match ≤
  **km / m/s / second** class vs both sixdof and traj `simulate`.
- **Gradient**: finite-difference check of `∂(miss)/∂knots` to ≤ **1e-5** rel.

Every claim is a pytest gate, extending the existing cross-validation suite. A
dead library path must fail loudly, not silently (BO lost a campaign to a silent
`.so` path — resolve/raise, never return garbage).

## 4. Work breakdown (phased, each phase gated by a test)

### J1 — Reentry rollout core
- Add `eom_flightpath.py` (or extend `eom_3dof.py`): WGS84+J2 spherical/oblate
  flight-path EOM `(h, V, γ, χ, σ)`, β/LD aero, US76, **Sutton-Graves q̇** output
  (R_nose param). Pure functions, `jax_enable_x64`.
- Fixed-step and adaptive integrator; energy or time as the independent variable.
- **Gate:** single-schedule rollout matches `JaxWGS84FlightPath` and C++ sixdof
  to §3 whole-trajectory tolerance on a 5-case entry grid (spanning orbital and
  sub-orbital energy, shallow and pull-up γ₀).

### J2 — Batch + differentiate
- `jit` the rollout; `vmap` over (schedule params, entry state, vehicle params).
- Verify `grad` through the full flight; expose a task-loss:
  `L = miss(target) + w·Σ relu(path-constraint violation)` over heat, g, γ.
- **Gate:** `vmap` of N=1e3 rollouts on GPU under a wall-clock budget; FD-checked
  gradient to §3 tolerance.

### J3 — Dispersion layer
- Parameterize and sample: atmospheric density (±30% @ 60–80 km, correlated
  profile), winds (reuse `wind_dryden`), IC dispersion, aero uncertainty
  (β/L·D scale), and — for closed-loop — nav error injection.
- Batched as a `vmap` dimension; deterministic PRNG keys in, so runs are
  reproducible (no wall-clock/`Math.random` seeding).
- **Gate:** an MC campaign of N=1e4 produces stable miss statistics; reproducible
  across two runs with the same key.

### J4 — Closed-loop hooks
- Allow a guidance callback in the loop (so a tracker or a learned policy flies
  the schedule, not just open-loop table playback), mirroring
  `sixdof/Guidance/ScheduledBankGuidance` + `ReferenceTrajectoryGuidance`
  semantics.
- **Gate:** closed-loop dispersed MC matches a C++ `dsf` closed-loop deck on the
  same case to agreed tolerance (this is the cross-stack certification the ART
  dsf-side consumer needs).

### J5 — 6-DOF-lite (stretch)
- Add trim α(M), bank-rate limit, first-order actuator lag so the differentiable
  model *exposes* the 3→6-DOF flyability gap (BO measured this as the real
  residual: control authority, ~0.89 s divergence, real-gas crossrange delta).
- **Gate:** the gap between 3-DOF and 6-DOF-lite reproduces the sign and rough
  magnitude of the sixdof full-6-DOF gap on a reference case.

## 5. Packaging & handoff

- Land as a clean importable API in `sixdof/py/sixdof_jax` (keep the C++-mirror
  home; this plan lives in `/opt/DSF` because the *capability* is framework-level
  and the DSF↔sixdof↔traj cross-validation is the crux).
- Public surface (proposed): `rollout(schedule, entry, vehicle) -> traj`,
  `task_loss(schedule, entry, vehicle, target) -> scalar` (differentiable),
  `mc(schedule_or_policy, entry, vehicle, dispersions, key, N) -> stats`.
- Every phase adds pytest gates to `py/tests/`. CI target: the full suite green
  on GPU and CPU (x64).
- Coordinate via git: commit this plan, work on a branch, keep the
  cross-validation suite as the contract. The ART program consumes the API at its
  epochs E2 (task-loss) and E6 (onboard-grade closed-loop) — see
  `/opt/hahn-aero/art_reentry/FUTURE.md`.

## 6. Order & parallelism

J1 → J2 → J3 is the critical path (rollout → differentiable batch → dispersions).
J4 depends on J1. J5 is a stretch after J2. J1 can start immediately; nothing here
blocks on the ART model work, and the ART model work (imitation pretrain) does not
block on this — they rendezvous at task-loss fine-tune.
</content>
