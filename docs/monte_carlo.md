# Monte Carlo Dispersion Framework

DSF includes a native Monte Carlo framework for statistical analysis of simulation models. It uses the `DSF_PROPERTY_BIND` introspection system to inject dispersed parameter values at runtime, with a Python dispatcher managing parallel batch execution.

## Quick Start

### 1. Add a `<monte_carlo>` block to your XML

```xml
<sim dt="0.01" tmax="600.0" library="libsixdof.so" output="csv">
    <!-- ... your vehicle definition ... -->

    <monte_carlo n="100" seed="42" workers="8" output_dir="mc_results/">
        <dispersion block="MissileMass" property="mass"
                    distribution="gaussian" sigma="50.0" />
        <dispersion block="FuelTank" property="mass"
                    distribution="gaussian" sigma="25.0" />
        <dispersion block="Engine" property="dry_mass"
                    distribution="uniform" min="180" max="220" />
    </monte_carlo>
</sim>
```

### 2. Run the batch

```bash
dsf mc run vehicle.xml              # 8 workers (default)
dsf mc run vehicle.xml --workers 16 # override parallelism
```

### 3. Monitor and analyze

```bash
dsf mc status mc_results/           # live progress
dsf mc results mc_results/          # per-parameter statistics
dsf mc extremes mc_results/         # cases with draws > 2σ
```

---

## XML Reference

### `<monte_carlo>` Element

Placed as a direct child of `<sim>`. Defines the MC batch configuration.

| Attribute    | Type   | Default      | Description                              |
|-------------|--------|--------------|------------------------------------------|
| `n`         | int    | `100`        | Number of Monte Carlo cases              |
| `seed`      | int    | `42`         | Master RNG seed for reproducibility      |
| `workers`   | int    | `8`          | Max parallel subprocesses                |
| `output_dir`| string | `mc_results/`| Directory for case outputs and metadata  |

### `<dispersion>` Element

Each `<dispersion>` is a child of `<monte_carlo>` and defines one parameter to vary.

| Attribute      | Type   | Required | Description                               |
|---------------|--------|----------|-------------------------------------------|
| `block`       | string | ✓        | XML `id` of the target block              |
| `property`    | string | ✓        | `DSF_PROPERTY_BIND` name                  |
| `distribution`| string | ✓        | `gaussian` or `uniform`                   |
| `sigma`       | double | Gaussian | Standard deviation (applied ±around nominal)|
| `min`         | double | Uniform  | Lower bound                               |
| `max`         | double | Uniform  | Upper bound                               |

**Gaussian**: draws from N(nominal, σ²) where nominal is the value set by `configure()`.

**Uniform**: draws from U(min, max), replacing the nominal value entirely.

---

## CLI Commands

All commands are accessed via `dsf mc <subcommand>`.

### `dsf mc run <xml_file>`

Launches the MC batch. Creates per-case XML files in `output_dir/case_NNNN/`, each with a unique `seed` and `case_id` attribute. Cases execute in parallel via `ProcessPoolExecutor`.

```
Options:
  -j, --workers INTEGER  Parallel workers [default: 8]
```

### `dsf mc status <output_dir>`

Reads the `.dsf_mc.json` state file and reports progress: cases done, failed, and running.

### `dsf mc results <output_dir>`

Aggregates pre-drawn dispersion values and reports per-parameter statistics (mean, std, min, max of n-sigma draws for Gaussian; direct values for Uniform).

### `dsf mc extremes <output_dir>`

Lists cases where any parameter draw exceeded a sigma threshold.

```
Options:
  -t, --threshold FLOAT  Sigma threshold [default: 2.0]
```

### `dsf mc template <xml_file>`

Auto-generates a `<monte_carlo>` XML block by inspecting the blocks defined in the XML. Produces a ready-to-edit template with all dispersible properties defaulted to `sigma="0.0"`.

---

## Architecture

```
Python Dispatcher                    C++ Simulation (per case)
┌──────────────────┐                ┌─────────────────────────┐
│  dsf mc run      │                │   main.cpp              │
│                  │   fork N       │                         │
│  Parse XML       ├───────────────►│   parse XML             │
│  Pre-draw values │   per case     │   configure()           │
│  Patch XML with  │                │   ┌─────────────────┐   │
│    seed/case_id  │                │   │ apply_dispersions│   │
│                  │                │   │  find block by id│   │
│  ProcessPool     │                │   │  demangle typeid │   │
│    Executor      │                │   │  TClassDict      │   │
│                  │                │   │  offsetof → write│   │
│  JSON state file │                │   └─────────────────┘   │
│  (.dsf_mc.json)  │   collect      │   init()                │
│                  │◄───────────────┤   exec()                │
│  Aggregate       │   CSV/H5       │   → output1.csv         │
└──────────────────┘                └─────────────────────────┘
```

### Dispersion Injection

Dispersions are applied **after `configure()` and before `init()`**. The engine:

1. Finds the target block in the simulation tree by its XML `id`
2. Calls `demangle(typeid(*block))` to get the C++ class name
3. Looks up the class in `TClassDict<Block>` and finds the property's `offsetof`
4. Reads the nominal value (set during `configure()`)
5. Draws from the specified distribution  
6. Writes the dispersed value via pointer arithmetic (`reinterpret_cast`)

Only properties registered with `DSF_PROPERTY_BIND` (which stores the member offset) are dispersible. Properties registered with plain `DSF_PROPERTY` are not.

### Reproducibility

Each case receives a deterministic seed derived from the master seed and case index via MD5 hash. Re-running the same batch with the same master seed produces identical results.

---

## Making a Property Dispersible

To expose a block member for Monte Carlo, use `DSF_PROPERTY_BIND` instead of `DSF_PROPERTY` in the class implementation:

```cpp
// Before (not dispersible):
DSF_PROPERTY(mass, "double", "0.0", "Mass (kg)")

// After (dispersible):
DSF_PROPERTY_BIND(mass, M, "double", "0.0", "Mass (kg)")
//                       ^
//                 C++ member name
```

The member must be `public` (required by `offsetof()`). If it's currently `private`, move it to the public section of the header:

```cpp
class Mass : public MassBase
{
public:
    // ... methods ...

    double M;      // MC-dispersible (must be public for offsetof)

private:
    // ... other private members ...
};
```

> **Design Intent**: Not all properties should be dispersible. `DSF_PROPERTY_BIND` is an explicit opt-in that forces model authors to declare which parameters are meaningful to vary in a Monte Carlo context.

---

## Output Structure

```
mc_results/
├── .dsf_mc.json       # Batch state (status, done/failed counts)
├── mc_draws.json      # Pre-drawn values, seeds, and distributions
├── case_0000/
│   ├── case.xml       # Patched XML with seed/case_id
│   ├── sim.log        # stdout/stderr from the simulation
│   └── output1.csv    # Simulation output (or .h5)
├── case_0001/
│   └── ...
└── case_NNNN/
    └── ...
```

### mc_draws.json

Contains full provenance for every draw:
- Master seed and per-case seeds
- Distribution type and parameters for each dispersion
- Drawn n-sigma values (Gaussian) or absolute values (Uniform)

---

## Example: Cruise Missile Mass Dispersion

```xml
<sim dt="0.01" tmax="600.0"
     library="/path/to/libsixdof.so" output="csv">

    <earth id="WGS84" class="WGS84" />
    <vehicle id="Vehicle" class="Vehicle" name="CruiseMissile">
        <mass id="MissileMass" class="Mass" mass="1500"
              MOI="50,0,0, 0,500,0, 0,0,500" />
        <tank id="FuelTank" class="Tank" mass="500" />
        <!-- ... other blocks ... -->
    </vehicle>

    <monte_carlo n="500" seed="12345" workers="8"
                 output_dir="cruise_mc/">
        <dispersion block="MissileMass" property="mass"
                    distribution="gaussian" sigma="50.0" />
        <dispersion block="FuelTank" property="mass"
                    distribution="gaussian" sigma="25.0" />
    </monte_carlo>
</sim>
```

```bash
$ dsf mc run cruise_missile_mc.xml
  ✓ Case    0 done
  ✓ Case    1 done
  ...
MC complete: 500 succeeded, 0 failed out of 500 (2m34s)

$ dsf mc extremes cruise_mc/ --threshold 2.5
Cases with draws > 2.5σ:
  Case   42: MissileMass.mass = +2.81σ
  Case  187: FuelTank.mass = -2.63σ
  Case  391: MissileMass.mass = +2.92σ
```
