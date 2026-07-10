# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

DSF (Digital Simulation Framework) is a time-domain 6-DOF simulation framework: a C++ simulation kernel with pybind11 Python bindings, plus a Python package providing a CLI, PyQt6 GUI, JAX-accelerated Monte Carlo, and an MCP server. Physics models (e.g. sixdof) live in **external shared libraries** loaded at runtime — the sixdof repo is expected as a sibling at `../sixdof` and its `libsixdof.so` is dlopen'd by simulations.

## Build

```bash
# Python package + C++ extension in one step (scikit-build-core compiles the
# extension during pip install and bundles dsf_core + libDSF.so into the
# package — no manual .so copying). Re-run after C++ changes; the build dir
# (build/skbuild-*) is persistent, so rebuilds are incremental.
pip install scikit-build-core          # once (needed for --no-build-isolation)
pip install -e . --no-build-isolation  # from the repo root

# Plain C++ build — for ctest, the examples, and the 'dynamic' loader
# (out-of-source build is enforced):
mkdir -p build && cd build
cmake ..                # picks up ../sixdof automatically if present
make -j$(nproc)

# Runtime library path for the model libs that simulations dlopen (from repo root)
export LD_LIBRARY_PATH="$(pwd)/build:$(pwd)/../sixdof/build:$LD_LIBRARY_PATH"
```

Dependencies: C++17, Boost (program_options, system, serialization), HDF5, OpenSceneGraph; pybind11 is fetched by CMake.

## Tests

`pytest.ini` at the repo root points at `python/tests`:

```bash
pytest                                        # full suite
pytest python/tests/test_dsf_bindings.py      # one file
pytest python/tests/test_run_vs_watch.py::test_name   # one test
pytest -m "not slow"                          # skip full C++ sim-loop tests
pytest -m qt                                  # GUI tests (pytest-qt)
ctest                                         # from build/: runs pytest with PYTHONPATH/LD_LIBRARY_PATH set
```

Test design constraint (see `python/tests/conftest.py`): simulations are run in **subprocesses** via `dsf run --h5`, keeping the C extension out of the pytest process (which has Qt loaded from pytest-qt); the parent process only reads `.h5` output with h5py. Follow this pattern for new sim tests. Fixtures live in `python/tests/fixtures/`.

## Running simulations

```bash
dsf run config.xml [--h5]        # run a sim (C++ exec loop)
dsf watch project.dsf            # Python-driven step loop with live telemetry (slower)
dsf gui / dsf-gui                # PyQt6 GUI
./run_sixdof_example.sh <example.xml>          # C++ 'dynamic' executable against sixdof examples
python -m dsf.mcp.server         # MCP server (workspace root via DSF_WORKSPACE env var)
```

A `.dsf` project is a **directory** containing `project.xml`, `vehicles/`, `tables/`, etc. — see `DSF_FORMAT.md`. If a path argument is a directory, DSF looks for `project.xml` inside it; relative paths in XML resolve relative to the XML file's location.

## Architecture

Two layers, C++ and Python, joined by the `dsf_core` pybind11 module:

**C++ kernel (`DSF/`)**
- `DSF/sim/` — the executive. `Sim` owns the run loop (clock → integrator → reports → termination). `Block` is the base class of every model component: lifecycle is `configure(xmlnode)` → `init()` → `update()` (per integration step) → `rpt()` → `finalize()`, with blocks forming a parent/child tree. Integrators: RK4 (default), RK45, Verlet.
- Factory registration (`TClassDict.h`): model classes self-register at static-init time via `Block* MyModel::block = TClass<MyModel, Block>::Instance();` and are instantiated by class-name string from XML (`TRefUnique<Block>("MyModel")`). This is why model libraries only need to be `dlopen`'d with `RTLD_GLOBAL` — see `examples/dynamic/main.cpp` for the canonical loader.
- `DSF/util/` — math (vec3/quat/mat), N-D lookup tables (`tbl/`), and a hand-rolled XML parser (`util/xml/`).
- Outputs: HDF5 (`hdf5output.h`) and CSV; `monte_carlo.h` and `phase_sequencer.h` extend the executive.

**Python bindings (`python/bindings/`)** — pybind11 wrappers over Sim/Block/util, built by the top-level CMakeLists into `dsf_core.*.so`. `python/dsf/__init__.py` does `from .dsf_core import *` but tolerates a missing extension so pure-Python submodules (MCP server) still work. `dsf/cli/run.py` locates the `.so` in `build/` and loads it with `RTLD_GLOBAL` so model libraries can resolve DSF symbols.

**Python package (`python/dsf/`)**
- `cli/` — click-based `dsf` entry point (`run`, `watch`, `gui`, plot/map/globe views, Monte Carlo).
- `utils/` — the glue used everywhere: `.dsf` ↔ XML conversion (`convert_dsf_to_xml.py`, `run_config.py`), XML parse/generate, `sim_session.py` (per-step introspection driving `watch` and the MCP server).
- `gui/` — PyQt6 app split into `core/` (model registry, commands, validation), `execution/` (headless runner, sim worker thread), `ui/` (canvas, inspector, plot/map windows).
- `jax/` — JAX integration loop and Monte Carlo dispatcher; physics models come from `sixdof.py.jax` in the sibling repo.
- `mcp/` — FastMCP server exposing run/output-reading/introspection tools (`server.py` is the real one).

## Gotchas

- The C++ XML layer (`DSF/util/xml/`) is a **Boost Property Tree** wrapper — tag/attribute/comment parsing is Boost's and is sound (the "hand-rolled tab-sensitive parser" note in TODO.md is stale). The residual whitespace sensitivity is in *value* parsing: `attrAsVec3`/`attrAsMat3` now accept comma- **or** whitespace-separated components, and `parse.h` warns rather than silently zero-filling. Still, prefer the Python `dsf.utils` generators over hand-editing sim XML.
- A `.dsf` project is currently a **single JSON file** (block graph + `metadata`), not the directory-with-`project.xml` layout described in `DSF_FORMAT.md` (that format is documented but unimplemented). `dsf run`/`watch` load the JSON and convert it to XML for the C++ core.
- `dsf/cli/run.py` looks for the extension in `build/` first, then `python/dsf/`, then site-packages (where `pip install -e .` puts the compiled copy) — a fresh `cmake` build in `build/` therefore shadows the pip-installed extension. After C++ changes, either rebuild in `build/` or re-run `pip install -e . --no-build-isolation`; don't let the two go stale relative to each other. The loader registers the module as `sys.modules['dsf.dsf_core']` so the package reuses the same copy — loading a second copy makes pybind11 abort with "type 'Vec3' is already registered".
- `LD_LIBRARY_PATH` should include `build/` and wherever `libsixdof.so` was built (`../sixdof/build`); the `build/sixdof_build` path in older docs is not created by this build.
- C++ unit tests live in `test/` (`cpp_util_tests`, `cpp_kernel_tests`, `cpp_tablend_tests`) and run via `ctest`. Python tests live in `python/tests/` only — `pytest.ini` deliberately scopes collection there. The repo root also holds many untracked one-off analysis/debug scripts (`plot_*.py`, `check_*.py`, `test_*.py`).
