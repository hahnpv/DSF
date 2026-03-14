# DSF C++/PyBind ABI Pitfalls & Telemetry Output

## Block Constructor Zero-Initialization (CRITICAL)

The `dsf::sim::Block` default constructor **must** explicitly zero-initialize all pointer members:

```cpp
Block() { parent = nullptr; clock = nullptr; o = nullptr; rptRate = 0.0; };
```

Without this, C++ `new` allocates from a dirty heap. Uninitialized `clock` and `o` contain garbage that passes `if (ptr == nullptr)` guards, causing segfaults when dereferenced during `Sim::exec()`.

**File**: `DSF/sim/block.h` line 54.

## OutputRef / ClockRef Overwrite Protection

`Block::OutputRef(Output* _o)` and `Block::ClockRef(Clock* _clock)` use a null-guard:

```cpp
void OutputRef(Output *_o) { if (o == nullptr) o = _o; };
void ClockRef(Clock *_clock) { if (clock == nullptr) clock = _clock; };
```

This prevents `Sim::load()` — which calls `TFunctor` to sweep the entire block tree — from overwriting vehicle-specific Output loggers with the global fallback logger. Without the guard, only the last vehicle's telemetry would be recorded.

## Header-Only Classes Require Full Rebuilds

`block.h`, `output.h`, and `hdf5output.h` define **inline methods** compiled into every `.so` that includes them. CMake's incremental `make` often **does not detect** changes to these headers.

**After modifying any of these headers, you MUST:**
```bash
# Touch all source files that include the header, or:
cd DSF/build && make clean && make -j16
cd sixdof/build && make clean && make -j16
```

Failure to do this results in `libsixdof.so` using stale object code with the old struct layout, causing silent ABI misalignment and segfaults.

## HDF5 Version Compatibility

- System `h5py` (used by MCP tools, `dsf cesium`) links HDF5 **1.10.10**
- Conda `h5py` links HDF5 **1.14.6**
- `libDSF.so` links system HDF5 via CMake `find_package(HDF5)`

**Do NOT call `H5Pset_libver_bounds(EARLIEST, EARLIEST)`** — HDF5 1.10 rejects this as invalid. The plain `H5::H5File(filename, H5F_ACC_TRUNC)` constructor uses the runtime library's native format, which is already 1.10-compatible when linked against the system library.

## Conda Environment (`DSF`)

Always use `conda activate DSF` or `conda run -n DSF` when running DSF simulations from the CLI. Building `dsf_core.so` with `/usr/bin/python3` instead of Conda Python creates ABI mismatches because:
- System Python and Conda Python may link different `libstdc++` versions
- `pybind11` header resolution differs between system and Conda installs

## TFunctor Argument Passing

`TFunctor<TClass, RClass>(fpt, objvec, c)` takes `RClass &c` by reference and internally calls `(*objvec[i].*fpt)(&c)`. This is safe — the reference preserves the original heap-allocated object's address. The pointer passed to `OutputRef`/`ClockRef` is the address of the original `Output`/`Clock` object, not a stack copy.

## Per-Vehicle Telemetry Output

When `rpt="1"` is set on a `<vehicle>` XML element:
1. `Vehicle::configure()` creates a new `Output` block and calls `this->OutputRef(out_block)`
2. The `Output` block is added as the **last child** (after physics components register their variables)
3. `Vehicle::configure()` uses `TFunctor` to propagate the vehicle's Output to all children
4. `Sim::load()`'s global `TFunctor` sweep is blocked by the null-guard, preserving vehicle-specific loggers

Each vehicle generates independent files: `output_<EOM_name>.h5` and `output_<EOM_name>.csv`.
