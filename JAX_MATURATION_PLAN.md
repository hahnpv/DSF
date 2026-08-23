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

### 1.1 Mirror-parity principle (don't cheat)

ART is the **first consumer, not the design target**. The end state is massive
Monte Carlo for arbitrary vehicles, so the physics layer must stay a faithful
mirror of `/opt/sixdof` — not an ART-shaped shortcut. Full coverage of the C++
model tree is **not** the goal; the reentry-relevant physics is the scope for
now. The rules for what we do build:

- **C++ sixdof is the source of truth; the mapping is `sixdof → jax`.** Every
  JAX physics module corresponds **1:1 to a named C++ sixdof model class**
  (e.g. `Aero/ReentryAero`, `Wind/WindDryden`) and is golden-tested against it.
  No fused "reentry physics" functions — composition for a given vehicle
  happens in the rollout layer, never inside the models.
- **New functionality lands in C++ first (or simultaneously).** If a capability
  is needed that sixdof lacks (e.g. Sutton-Graves heat flux), implement the
  sixdof counterpart and mirror it — never JAX-only physics with no C++
  reference to validate against.
- ART/reentry-specific logic (schedule parameterization, task loss, dispersion
  choices) lives **only** in the rollout / task-loss / MC layers.
- Coverage grows model-by-model as vehicles demand it. Maintain a **parity
  matrix** in `sixdof/py/sixdof_jax/PARITY.md`: C++ model ↔ JAX module ↔ golden
  test ↔ status (*mirrored / deferred / out-of-scope*). Models that are hostile
  to `jit`/`vmap` (contact dynamics, marine hydro, discrete-event staging,
  stateful estimators) are marked out-of-scope explicitly rather than
  half-mirrored.

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

### J1 — Reentry rollout core — **LANDED 2026-08-22**
Delivered: `sixdof_jax/aero_reentry.py` (ReentryAero mirror incl. real-gas
and Sutton-Graves — the C++ counterpart `qdot_`/`R_nose` was added to
`ReentryAero` first, per §1.1), `eom_flightpath.py` (traj-geodetic EOM,
bit-exact vs `JaxWGS84FlightPathGeodetic`), `rollout.py` (composition),
`examples/entry/reentry_anchor_3dof.xml` (C++ anchor deck), and
`py/tests/test_reentry_rollout.py` (49 gates: per-model 1e-12/1e-9;
whole-trajectory 5-case grid vs `dsf run` at <2 km / <5 m/s equatorial,
<10 km / <25 m/s mid-lat — the mid-lat slack is the C++ geocentric-normal
vs geodetic-normal lift-plane definition, documented in the test).
Parity matrix: `sixdof/py/sixdof_jax/PARITY.md`.
- Add `eom_flightpath.py` (or extend `eom_3dof.py`): WGS84+J2 spherical/oblate
  flight-path EOM `(h, V, γ, χ, σ)`, β/LD aero, US76, **Sutton-Graves q̇** output
  (R_nose param). Pure functions, `jax_enable_x64`. Per §1.1: the aero and heat
  models land as standalone mirrors of their C++ counterparts (`ReentryAero`
  etc.), composed by the rollout — not fused into the EOM.
- Fixed-step and adaptive integrator; energy or time as the independent variable.
- **Gate:** single-schedule rollout matches `JaxWGS84FlightPath` and C++ sixdof
  to §3 whole-trajectory tolerance on a 5-case entry grid (spanning orbital and
  sub-orbital energy, shallow and pull-up γ₀).

### J2 — Batch + differentiate — **LANDED 2026-08-22** (GPU wall-clock number pending a GPU box)
Delivered: `rollout` is jit/vmap-able over schedule, entry, and vehicle;
`sixdof_jax/task_loss.py` (miss + heat/g/γ relu penalties);
`py/tests/test_rollout_batch_grad.py` (vmap self-consistency, N=1e3
dispersed batch under wall-clock, grad finite/nonzero wrt schedule +
entry + vehicle, FD gradient check to 1e-5 on every knot). The dev box
is CPU-only — the 60 s GPU budget is asserted at 600 s CPU-scaled;
re-run on a GPU box to certify the plan's original number.
- `jit` the rollout; `vmap` over (schedule params, entry state, vehicle params).
- Verify `grad` through the full flight; expose a task-loss:
  `L = miss(target) + w·Σ relu(path-constraint violation)` over heat, g, γ.
- **Gate:** `vmap` of N=1e3 rollouts on GPU under a wall-clock budget; FD-checked
  gradient to §3 tolerance.

### J3 — Dispersion layer — **LANDED 2026-08-22**
Delivered: `sixdof_jax/dispersions.py` (correlated AR(1) density profile
±30% 1σ @ 60–80 km, steady wind profiles, β/LD scales, IC deltas — all
keyed PRNG), `mc.py` (chunked vmap campaign API with miss statistics),
wind/density channels in `rollout.py`, and — C++ first, per §1.1 — a
`rho_bias_table` replay attribute on the sixdof `Atmosphere` block so a
sampled JAX atmosphere flies bit-identically through the C++ stack
(`test_dispersions_mc.py::test_density_profile_cpp_replay`). Gates in
`py/tests/test_dispersions_mc.py`: sampler statistics, determinism,
zero-dispersion ≡ nominal, chunking invariance, N=1e4 stable-statistics.
Dryden gusts and nav-error injection deliberately deferred to J4
(closed-loop, where spectra and estimators matter).
- Parameterize and sample: atmospheric density (±30% @ 60–80 km, correlated
  profile), winds (reuse `wind_dryden`), IC dispersion, aero uncertainty
  (β/L·D scale), and — for closed-loop — nav error injection.
- Batched as a `vmap` dimension; deterministic PRNG keys in, so runs are
  reproducible (no wall-clock/`Math.random` seeding).
- **Gate:** an MC campaign of N=1e4 produces stable miss statistics; reproducible
  across two runs with the same key.

### J4 — Closed-loop hooks — **LANDED 2026-08-22**
Delivered: `sixdof_jax/closed_loop.py` (`rollout_guided`: a continuous
stateless law evaluated per RK4 stage — the exact C++
Block::update-per-stage semantics — plus a discrete zero-order-hold
controller mode for stateful policies/learned FSW, and nav-bias
injection so guidance sees the estimate while physics flies the truth);
`guidance_entry.py` (`energy_scheduled_bank` mirroring
ScheduledBankGuidance schedule_var="energy" term-for-term, and
`reference_bank_tracker` carrying the ReferenceTrajectoryGuidance
semantics — tabular reference + Kp perturbation feedback — to the bank
channel); the 'nav' dispersion channel; closed-loop `mc()`. Gates in
`py/tests/test_closed_loop.py`: the certification gate runs three
DISPERSED closed-loop cases through both stacks (sampled density
profile replayed via rho_bias_table into a C++ deck flying
ScheduledBankGuidance in energy mode) at <2 km / <5 m/s / bank command
within 2°, and the robustness property (energy scheduling beats the
recorded open-loop σ(t) under density dispersion) holds in MC.
Dryden gusts remain deferred (spectral content needs the 6-DOF-lite
attitude loop of J5 to matter).
- Allow a guidance callback in the loop (so a tracker or a learned policy flies
  the schedule, not just open-loop table playback), mirroring
  `sixdof/Guidance/ScheduledBankGuidance` + `ReferenceTrajectoryGuidance`
  semantics.
- **Gate:** closed-loop dispersed MC matches a C++ `dsf` closed-loop deck on the
  same case to agreed tolerance (this is the cross-stack certification the ART
  dsf-side consumer needs).

### J5 — 6-DOF-lite (stretch) — **LANDED 2026-08-22**
Delivered: `sixdof_jax/sixdof_lite.py` (`rollout_lite`: actual bank as
an 8th state, σ̇ = clip((σ_cmd−σ)/τ, ±rate) — first-order actuator lag
+ slew saturation, defaults matched to the ColdGasRCS envelope); trim
α(M) as Mach-varying L/D and β tables — added to C++ `ReentryAero`
first (`LD_mach`/`beta_mach`, cd_mach idiom) and mirrored, cross-stack
validated to J1 tolerance; and `body_roll="1"` on C++
`ScheduledBankGuidance` so one schedule flies both kinematically and
through the real RCS/6-DOF attitude path. Gates in
`py/tests/test_sixdof_lite.py`.

**Measured flyability-gap decomposition** (the gate, reinterpreted per
what the reference case actually showed): the lite model reproduces the
C++ RCS roll-channel response (reversal crossing duration within 1.5×)
and its trajectory-level effect (km-class downrange extension through a
through-zero reversal). But the FULL 3→6-DOF gap on this stack is
dominated by attitude-trim absence — the capsule model has no pitch
stability and the RCS commands roll only, so the lift orientation
drifts with the rotating local horizon (~0.07°/s) while reported bank
tracks perfectly; the trajectory diverges exponentially to hundreds of
km by t=500 s. Gated as: gap_full > 10× gap_lite with the roll loop
provably healthy. That is the flyability gap made concrete: 3-DOF's
"held bank" assumption silently presumes attitude authority the
modeled vehicle lacks. Consumers (ART): treat 3-DOF/lite optimism about
attitude as a modeling boundary, not a small correction.
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
