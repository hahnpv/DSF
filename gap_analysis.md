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

#### 1. No Wind / Turbulence Model
**Impact**: All aero simulations assume still air. No way to test vehicle robustness to gusts, wind shear, or jet stream profiles.

**What's needed**:
- Constant wind profile (configurable direction + speed)
- Altitude-dependent wind (e.g. power-law or table-driven profiles)
- Discrete gusts (1-cosine, step, ramp — per MIL-F-8785C)
- Dryden / von Kármán turbulence spectrum models
- Wind affects relative velocity computation in EOM → aero forces

#### 2. No Sensor Models (Navigation is PerfectNav-only)
**Impact**: No ability to simulate realistic GNC performance. Every guidance law sees perfect truth state.

**What's needed**:
- **IMU model**: accelerometer + gyro with bias, scale factor, noise, quantization
- **GPS model**: position/velocity with noise, outage simulation, multipath
- **INS/GPS filter**: Complementary or Kalman filter for blended nav solution
- **Air data**: pitot-static with lag, altitude encoder with quantization
- **Star tracker / horizon sensor**: for spacecraft attitude determination

#### 3. Only RK4 Integrator
**Impact**: RK4 is fixed-step only. No error control, no stiffness handling. Orbital propagation at dt=0.05s wastes compute; cable dynamics may need smaller steps.

**What's needed**:
- Variable-step RK45 (Dormand-Prince) with error tolerance
- Symplectic integrator option for long-duration orbital mechanics
- Per-block integration rate (fast inner loop for FCS, slow outer loop for environment)

#### 4. No Event Detection / Discrete Logic Framework
**Impact**: State machines, mode transitions, and event triggers are ad-hoc (hard-coded time checks in each model). No way to detect zero-crossings (e.g. "altitude == 0" for impact).

**What's needed**:
- Zero-crossing detector (for impact, apogee, phase transitions)
- Discrete-event scheduling (fire squib at event, not at fixed time)
- State machine framework or at least a standardized event bus

---

### 🟡 Medium Priority — Model Completeness

#### 5. No Multi-Dimensional Table Interpolation
**Impact**: Aero databases are typically 3D+ (α, β, Mach → Cx). The current `Table` class only supports 1D. F16Aero hard-codes its own table lookups.

**What's needed**:
- 2D bilinear interpolation (α, Mach)
- 3D trilinear interpolation (α, β, Mach)
- N-D scattered data interpolation (or regular grid)
- Table file format that supports multi-dimensional data

#### 6. No Actuator / Servo Dynamics
**Impact**: Control surfaces respond instantly. No way to evaluate actuator rate limits, saturation, hysteresis, or time delay effects on stability margins.

**What's needed**:
- First-order lag model with rate/position limits
- Optional backlash, hysteresis, quantization
- Configurable per control surface via XML

#### 7. Atmosphere Model Incomplete
**Impact**: US Standard 1976 is the only option. No off-standard day, no high-altitude (>86 km) model, no planetary atmospheres.

**What's needed**:
- Hot/cold day profiles (MIL-STD-210)
- GRAM (Global Reference Atmosphere Model) or equivalent for dispersions
- High-altitude extension (>86 km for reentry vehicles)
- Mars / Titan atmosphere models for interplanetary work

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

#### 10. No Datalink / Seeker Models
**Impact**: Missile and intercept scenarios can't be simulated. No target tracking, no guidance law feedback from a seeker.

**What's needed**:
- RF / IR seeker model (gimbal dynamics, FOV, tracking noise)
- Proportional navigation / augmented PN guidance laws
- Datalink (uplink commands, target state updates)
- Target motion models (maneuvering, countermeasures)

---

### 🟢 Lower Priority — Framework Polish

#### 11. XML Parser Fragility
**Impact**: Already documented in TODO.md — tab-dependent parsing, space-splitting bugs, model name truncation.

**What's needed**:
- Migrate to pugixml or RapidXML
- Or alternatively, support YAML/JSON as an option

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
| Variable-step integrator | ✅ | ✅ | ❌ (RK4 only) |
| Wind/turbulence | ✅ | ✅ | ❌ |
| Sensor models | ✅ | ✅ | ❌ (PerfectNav only) |
| Multi-dim tables | ✅ | ✅ | ❌ (1D only) |
| Actuator dynamics | ✅ | ✅ | ❌ |
| Monte Carlo | ✅ | ✅ | ❌ |
| Event detection | ✅ | ✅ | ❌ (ad-hoc) |
| Flex-body | ❌ | ✅ | ❌ |
| Python scripting | ❌ | ✅ | ✅ |
| MCP / AI integration | ❌ | ❌ | ✅ |
| JAX differentiable models | ❌ | ❌ | ✅ |
| Trajectory optimization link | ❌ | ❌ | ✅ (Dymos) |

> [!TIP]
> DSF/sixdof's **unique strengths** (MCP integration, JAX differentiable models, Dymos trajectory coupling) are not found in any competitor. The gaps are mostly in classical simulation infrastructure that's well-understood and straightforward to implement.
