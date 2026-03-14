# DSF + sixdof Feature Gap Analysis

Comprehensive assessment of both codebases against the expectations of a production-grade 6DOF simulation framework.

## Current Inventory

### DSF Framework
| Module | Capabilities |
|--------|-------------|
| **sim** | Block lifecycle, `dt`/`tmax`, RK4 integrator, CSV + HDF5 output, real-time clock |
| **util** | Vec3/Mat3, Table (1D interp), XML parser (TinyXML), Gaussian RNG |
| **vis** | OpenSceneGraph 3D viewer, orbit/static cameras, network callbacks |
| **net** | TCP client/server for distributed sim |
| **python** | pybind11 bindings, Qt5 GUI, MCP server, CLI (run/plot/watch/globe), JAX models |

### sixdof Models
| Subsystem | Implementations |
|-----------|----------------|
| **EOM** | 6DOF, 3DOF, FlatEarth, Equinoctial, ScriptedEOM |
| **Geodesy** | WGS84, Spherical, EquinoctialMultibody (stub) |
| **Aero** | F16Aero, AirplaneAero, MissileAero, MissileFin, ReentryAero, SimpleAero, AeroDamping |
| **Control** | F16FCS (TECS), AirplaneAutopilot, PerfectControl |
| **Guidance** | ReferenceTrajectory, GravityTurn, LinearTangent, Linear, SimpleGuidance |
| **Propulsion** | RocketProp, TurbofanEngine, PistonEngine, Squib |
| **Navigation** | PerfectNav (only) |
| **Mass** | Tank, Mass, StageMass, VehicleConfig, MassBase |
| **Ground** | LandingGear (spring-damper) |
| **Other** | Cable, StageManager, GroundStation, GroundVehicle, SteadyFlightAirplane, Sphere |
| **Atmosphere** | US Standard 1976 |

---

## Gap Analysis

### 🔴 High Priority — Foundational Gaps

#### 1. ~~No Wind / Turbulence Model~~ ✅ DONE
**Resolved**: Implemented base abstraction and concrete MIL-F-8785C models. Wind affects relative velocity computation in EOM auto-correcting aero forces/Mach/Alpha.

- `WindModel` base class with `wind_NED(alt)` + forward-compatible `wind_NED(alt, lat, lon, t)`
- `WindProfile`: XML-configurable altitude layers
- Discrete gusts (1-cosine — per MIL-F-8785C)
- `WindDryden`: Dryden continuous turbulence (MIL-F-8785C / MIL-HDBK-1797) — light/moderate/severe presets
- Falcon 9 Cape Canaveral wind variant verified
- F16 Dryden test: survived 60s moderate turbulence, correct ±3σ statistics

#### 2. ~~No Sensor Models (Navigation is PerfectNav-only)~~ ✅ DONE
**Resolved**: Implemented discrete-sampled dynamic sensor models and sensor fusion to provide realistic, noisy navigation states.

- **IMU model (`IMUSensor`)**: Implemented with Zero-Order Hold specific force and angular rate discretization to satisfy DAG requirements. Supports bias, cross-coupling, and continuous additive noise.
- **GPS model (`GPSSensor`)**: Implemented with Gaussian noise and Gauss-Markov random walk processes.
- **INS/GPS Filter**: 
  - `NavFilter`: Pass-through direct GPS replacement blending.
  - `NavEKF`: 15-state Extended Kalman Filter (Position, Velocity, Attitude, Accel Biases, Gyro Biases). Integrates using `Eigen` matrix math and continuous/discrete time updates separated from physical simulation timestep.

All validated via `F16FCS` running a 220-second dynamic routing maneuver using noisy navigation state estimates exclusively.

#### ~~3. Only RK4 Integrator~~ ✅ DONE
**Resolved**: Integrator strategy pattern with XML selection.

- `IntegratorBase` abstract class + factory in `Sim::load()`
- **RK45 (Dormand-Prince)**: adaptive sub-stepping within Clock dt, `atol`/`rtol` configurable
- **Störmer-Verlet**: symplectic integrator with `IntegrandType` position/momentum tags
- XML: `<sim integrator="RK45" atol="1e-8" rtol="1e-6" />`
- Regression verified: RK4 vs RK45 on F16 steady — ΔAlt=1m (0.02%), ΔMach≈0

#### ~~4. No Event Detection / Discrete Logic Framework~~ ✅ DONE
**Resolved**: EventBus + PhaseSequencer framework.

- **EventBus**: singleton with 7 condition types (time_ge, crosses, rising, falling, ge, le, crosses_zero), zero-crossing interpolation, sorted callback execution, event history
- **XML events**: `<events><event name="impact" type="falling" variable="Altitude" value="0" action="sim.terminate" /></events>`
- **PhaseSequencer**: named phases with `map<string,double>` params, time/guard triggers, transition callbacks
- F16FCS migrated from ad-hoc `Phase` struct to PhaseSequencer
- Variable resolution via `Output::find_variable()` substring matching

---

### 🟡 Medium Priority — Model Completeness

#### ~~5. No 3D+ Table Interpolation~~ ✅ DONE
**Resolved**: N-dimensional table interpolation via `TableND`.

- `TableND` class with N-D regular grid multilinear interpolation
- Supports arbitrary dimensionality (1D through N-D)
- Deprecates legacy `Table` (1D) and `Table2d` (2D) without removing them
- Used by `ReferenceTrajectoryGuidance` for trajectory table lookups

#### 6. ~~No Actuator / Servo Dynamics~~ ✅ DONE
**Resolved**: Implemented a continuous `Actuator` component evaluated natively within the RK4 ODE solver.

- **Kinetics**: First-order lag model parameterized by time constant `tau` (e.g. `tau="0.05"` for ~3Hz bandwidth)
- **Constraints**: Enforces physical boundaries (`pos_min`/`pos_max`) and mechanical rate limits (`rate_limit`)
- **Integration**: `pos_dot` derivative is injected into the global simulation integration system (`TClassIntegrandDict`) for flawless calculation alongside 6DOF kinematics
- **Wiring (XML)**: Standalone generic blocks instantiated via `<actuator id="..." />` that can be mapped directly to aero surfaces (`F16Aero`) or TVC gimbals (`RocketProp`)
- Verified via `F16FCS` stabilization with delayed surfaces, and F-9 `RocketProp` TVC tracking lag producing 55km altitude deviation against instantaneous optimal guidance.

#### 7. ~~Atmosphere Model Incomplete~~ ✅ DONE
**Resolved**: Full 7-layer US Standard Atmosphere 1976 (0–86 km) with tabulated upper atmosphere (86–1000 km, cubic interpolation). Hot/cold day perturbation (MIL-STD-210C).

- 7-layer analytical model replacing broken 3-layer (was missing mesosphere, had dead code above 25 km)
- Upper atmosphere with pressure/density ratio tables + kinetic temperature model
- `day="hot|cold|standard"` XML attribute for temperature perturbation

**Deferred**:
- GRAM (NASA proprietary, requires SUA — added to TODO.md)

#### 8. No Flex-Body / Structural Dynamics
**Impact**: Large rockets experience significant bending modes that couple with the flight control system. Slosh dynamics affect guidance stability.

**What's needed**:
- First-mode bending (simplified beam model)
- Propellant slosh (pendulum or spring-mass analogies)
- Structural load monitoring (axial load, bending moment at stations)

#### 9. Aerodynamic Heating / Thermal
**Impact**: No thermal state tracking for reentry vehicles. ReentryAero exists but has no heating model.

**What's needed**:
- Stagnation-point heating (Sutton-Graves, Fay-Riddell)
- Surface temperature integration (heat soak)
- Material ablation tracking (TPS thickness)
- Tie-in with the existing `streamtrace` package

#### ~~10. No Datalink / Seeker Models~~ ✅ DONE
**Resolved**: Implemented full RF/IR Seeker with FOV/gimbal limits, tracking noise, discrete Datalink, and True Proportional Navigation (TPN).

- `Seeker` provides LOS angles, rates, and range with Gaussian noise corruption.
- `Datalink` provides configurable ZOH uplink frequency target states.
- `ProNavGuidance` calculates lateral acceleration commands (A_cmd).
- `KinematicTarget` acts as a simplified evasive target drone.
- **Note**: These targeting models can be co-opted and used in non-seeker modes as general sensors. For example, a ground RADAR that computes Line-of-Sight and range (with noise/corruption), or a tracking sensor on a satellite.

---

### 🟢 Lower Priority — Framework Polish

#### ~~11. XML Parser Fragility~~ ✅ DONE
**Resolved**: Custom parser replaced with `boost::property_tree`.

- `xmlnode` wrapper provides stateful navigation with parent stack
- Proper error handling, attribute lookup, Vec3/Mat3 parsing
- No more tab-dependent or space-splitting bugs

#### 12. No Monte Carlo / Dispersion Framework
**Impact**: Can only run single deterministic cases. No way to evaluate system robustness.

**What's needed**:
- Parameter dispersions (Gaussian, uniform, tabular) via XML
- Batch runner with seed management
- Statistical post-processing (percentiles, CDF plots, scatter matrices)

#### 13. No Unit System / Conversion Layer
**Impact**: Units are implicit. Mixed conventions (some radians, some degrees) cause repeated bugs.

**What's needed**:
- Explicit unit annotations on Block inputs/outputs
- Automatic conversion at XML parse time
- At minimum, a convention document

#### 14. Visualization Modernization
**Impact**: OSG viewer is functional but aging. No web-based or lightweight option.

**What's needed**:
- Cesium / web-based 3D globe visualization
- Or lightweight VTK/matplotlib-based replay
- Integration with the existing `dsf globe-view` CLI command

#### 15. Missing `NavigationBase` Accessors
**Impact**: As discovered during ref-traj work — no Earth-relative velocity, no geodetic altitude accessor, `position()` contract is violated by PerfectNav.

**What's needed**:
- `geodetic_altitude()` — WGS84 altitude
- `ground_speed()` — Earth-relative velocity magnitude
- `flight_path_angle()` — γ
- Fix `PerfectNav::position()` to return actual inertial position

---

## Comparison vs Industry Tools

| Feature | JSBSim | Trick | DSF/sixdof |
|---------|--------|-------|------------|
| Variable-step integrator | ✅ | ✅ | ✅ (RK4, RK45, Verlet) |
| Wind/turbulence | ✅ | ✅ | ✅ (WindProfile, Dryden, gust) |
| Sensor models | ✅ | ✅ | ❌ (PerfectNav only) |
| Multi-dim tables | ✅ | ✅ | ✅ (TableND, N-D) |
| Actuator dynamics | ✅ | ✅ | ❌ |
| Monte Carlo | ✅ | ✅ | ❌ |
| Event detection | ✅ | ✅ | ✅ (EventBus + PhaseSequencer) |
| Flex-body | ❌ | ✅ | ❌ |
| Python scripting | ❌ | ✅ | ✅ |
| MCP / AI integration | ❌ | ❌ | ✅ |
| JAX differentiable models | ❌ | ❌ | ✅ |
| Trajectory optimization link | ❌ | ❌ | ✅ (Dymos) |

> [!TIP]
> DSF/sixdof's **unique strengths** (MCP integration, JAX differentiable models, Dymos trajectory coupling) are not found in any competitor. The gaps are mostly in classical simulation infrastructure that's well-understood and straightforward to implement.
