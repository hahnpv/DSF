# DSF + sixdof Feature Gap Analysis

Comprehensive assessment of both codebases against the expectations of a production-grade 6DOF simulation framework.

## Current Inventory

### DSF Framework
| Module | Capabilities |
|--------|-------------|
| **sim** | Block lifecycle, `dt`/`tmax`, RK4/RK45/Verlet integrators, CSV + HDF5 output, real-time clock, EventBus, PhaseSequencer |
| **util** | Vec3/Mat3, Table/Table2d/TableND (N-D interp), XML parser (boost::property_tree), Gaussian RNG |
| **vis** | OpenSceneGraph 3D viewer, orbit/static cameras, network callbacks |
| **net** | TCP client/server for distributed sim (⚠️ stubbed — all methods are TODO) |
| **python** | pybind11 bindings, Qt5 GUI, MCP server, CLI (run/watch/plot/map/globe/terrain/cesium), JAX models, `.dsf` project format |

### sixdof Models
| Subsystem | Implementations |
|-----------|----------------|
| **EOM** | 6DOF, 3DOF, FlatEarth, Equinoctial, HydroEOM, PointMassEOM, KinematicTarget, ScriptedEOM |
| **Geodesy** | WGS84, Spherical, EquinoctialMultibody (stub), MarsGeodesyBlock |
| **Aero** | F16Aero, AirplaneAero, MissileAero, MissileFin, ReentryAero, SpaceplaneAero, SimpleAero, AeroDamping, ParachuteAero, ParafoilAero, HelicopterFuselage |
| **Control** | F16FCS, AirplaneAutopilot, RotorcraftFCS, HelicopterFCS, TandemRotorFCS, ShipFCS, SubmarineFCS, SailFCS, PerfectControl, Actuator |
| **Guidance** | ReferenceTrajectory, GravityTurn, LinearTangent, Linear, SimpleGuidance, WaypointGuidance, ProNavGuidance, JPADSGuidance, BankAngleGuidance, EntryGuidance, SpacecraftGuidance, BoosterLandingGuidance |
| **Propulsion** | RocketProp, TurbofanEngine, TurbopropEngine, TurboshaftEngine, PistonEngine, ScramjetEngine, ElectricPropulsion, Squib |
| **Navigation** | PerfectNav, IMUSensor, GPSSensor, NavFilter, NavEKF (15-state), Seeker, Datalink, WaypointNav |
| **Mass** | Tank, Mass, StageMass, VehicleConfig, MassBase, BallastTank |
| **Ground** | LandingGear (spring-damper) |
| **Marine** | BargeHydro, HydroBody, ShipMMG, SailboatForces, WaterMedium |
| **Rotor** | RotorDisk (BET + momentum theory) |
| **Terrain** | TerrainModel (DTED/HGT multi-tile) |
| **Other** | Cable, StageManager, GroundStation, GroundVehicle, SteadyFlightAirplane, Sphere, OrbitalTelemetry, ColdGasRCS |
| **Atmosphere** | US Standard 1976 (7-layer + upper), MarsAtmosphere |

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
**Resolved**: Full sensor suite with fusion.

- `IMUSensor` — ZOH specific force/angular rate, bias, cross-coupling, additive noise
- `GPSSensor` — Gaussian noise, Gauss-Markov random walk
- `NavFilter` — pass-through GPS blending
- `NavEKF` — 15-state EKF (pos/vel/att/accel-bias/gyro-bias), Eigen matrix math
- `Seeker` — RF/IR LOS angles/rates/range with Gaussian noise, FOV/gimbal limits
- `Datalink` — configurable ZOH uplink frequency

Validated via F16FCS 220s routing maneuver with noisy nav state exclusively.

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
**Resolved**: `Actuator` component — first-order lag (`tau`), position limits, rate limits, integrated via `TClassIntegrandDict`. XML: `<actuator id="..." />`.
Verified: F16FCS with delayed surfaces, F-9 TVC tracking lag (55km altitude deviation vs instantaneous).

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

#### ~~14. Visualization Modernization~~ ✅ DONE
**Resolved**: Full visualization suite:
- `dsf globe` — PyVista 3D orbit globe
- `dsf map` — 2D ground-track map
- `dsf terrain` — GPU-accelerated 3D terrain + trajectory (PyVista/VTK), SRTM/DTED/GEBCO tiles, `--cull` (bbox crop), `--z-scale` (vertical exaggeration)
- `dsf cesium` — CesiumJS 4D web visualizer with local server
- `dsf plot` — interactive strip-chart viewer
- Qt5 GUI with introspection-based variable tree

#### 15. Missing `NavigationBase` Accessors
**Impact**: As discovered during ref-traj work — no Earth-relative velocity, no geodetic altitude accessor, `position()` contract is violated by PerfectNav.

**What's needed**:
- `geodetic_altitude()` — WGS84 altitude
- `ground_speed()` — Earth-relative velocity magnitude
- `flight_path_angle()` — γ
- Fix `PerfectNav::position()` to return actual inertial position

#### 16. Hardcoded Earth Constants (Code Consolidation)
**Impact**: `mu = 3.986004418e14` is hardcoded in both `Equinoctial.cpp:80` and `LinearTangentGuidance.cpp:133`. `Re = 6378137.0` is hardcoded in `Equinoctial.cpp:318` and `BoosterLandingGuidance.cpp:516`. `9.81` appears in `WaypointGuidance.cpp:549` instead of querying the gravity model.

**What's needed**:
- Central `EarthConstants.h` header with `constexpr` values (mu, Re, J2, g0, omega_e)
- Subsystems should query the geodesy model or use the central constants

#### 17. DSF Net Module is Entirely Stubbed
**Impact**: `NetClient.cpp` and `NetServer.cpp` contain only TODO comments — zero networking is implemented. Module compiles and links but does nothing.

**Decision needed**:
- Delete the net module (dead code)
- Or implement TCP state streaming for distributed/HLA-style sim federation

#### 18. Duplicate Python Data Loaders
**Impact**: Two separate `data_loader.py` files exist:
- `dsf/utils/data_loader.py` — structured H5 loader with Vec3 reassembly, used by GUI
- `dsf/visualization/data_loader.py` — CSV/H5 trajectory loader with column guessing, used by globe

Overlapping H5 reading logic should be consolidated into one canonical loader.

---

## Comparison vs Industry Tools

| Feature | JSBSim | Trick | DSF/sixdof |
|---------|--------|-------|------------|
| Variable-step integrator | ✅ | ✅ | ✅ (RK4, RK45, Verlet) |
| Wind/turbulence | ✅ | ✅ | ✅ (WindProfile, Dryden, gust) |
| Sensor models | ✅ | ✅ | ✅ (IMU, GPS, EKF, Seeker, Datalink) |
| Multi-dim tables | ✅ | ✅ | ✅ (TableND, N-D) |
| Actuator dynamics | ✅ | ✅ | ✅ (first-order lag, rate/pos limits) |
| Monte Carlo | ✅ | ✅ | ✅ (JAX vmap batch, C++ pending) |
| Event detection | ✅ | ✅ | ✅ (EventBus + PhaseSequencer) |
| Flex-body | ❌ | ✅ | ❌ |
| Python scripting | ❌ | ✅ | ✅ (PythonBlock, PythonModel, JAX) |
| Web visualization | ❌ | ❌ | ✅ (CesiumJS 4D, terrain, globe) |
| MCP / AI integration | ❌ | ❌ | ✅ |
| JAX differentiable models | ❌ | ❌ | ✅ |
| Trajectory optimization link | ❌ | ❌ | ✅ (Dymos) |

> [!TIP]
> DSF/sixdof's **unique strengths** (MCP integration, JAX differentiable models, Dymos trajectory coupling, CesiumJS 4D visualization) are not found in any competitor. Remaining gaps are limited to C++ Monte Carlo (JAX covers GPU batching) and flex-body / structural dynamics.
