# DSF
Digital Simulation Framework

## Prerequisites & Dependencies

### C++ Core Dependencies
To build the DSF C++ core, the following tools and libraries are required:
- **Build Tools**: `cmake`, `g++` (or equivalent compiler supporting C++17)
- **Boost** (>= 1.56): `libboost-program-options-dev`, `libboost-system-dev`, `libboost-serialization-dev`
- **OpenSceneGraph** (>= 2.0.0): `libopenscenegraph-dev`
- **HDF5**: `libhdf5-dev`
- **Doxygen** (Optional, for building docs): `doxygen`

**Ubuntu/Debian Installation:**
```bash
sudo apt-get update
sudo apt-get install -y cmake g++ libboost-program-options-dev libboost-system-dev libboost-serialization-dev libopenscenegraph-dev libhdf5-dev doxygen
```

> **Note**: If building in a Conda environment, ensure you install these dependencies via `conda-forge`:
> ```bash
> conda install -c conda-forge boost openscenegraph hdf5
> ```

### Python Package Dependencies
To use the Python bindings and GUI (`dsf-gui`), you need Python >= 3.8 and the following modules (automatically installed via `pip`):
- `PyQt6`, `pyqtgraph`, `numpy`, `pandas`, `lxml`, `pyqtdarktheme`, `click`, `pyvista`, `h5py`


## Installation

### 1. Build the C++ Core and Python Bindings

First, clone the repository and build the C++ core:
```bash
git clone https://github.com/hahnpv/DSF
cd DSF
mkdir build
cd build
cmake ..
make -j$(nproc)
```

The build process will produce the `dsf_core.<target>.so` shared object library representing the Python bindings. 

### 2. External Simulation Libraries
DSF dynamically loads external models at runtime (e.g., `libsixdof.so`). Ensure that your linked simulation libraries are compiled and the `.so` files are placed inside `./build/` alongside the DSF libraries, or on your system's `LD_LIBRARY_PATH`.

For example, to configure the path so everything runs properly:
```bash
export LD_LIBRARY_PATH="$(pwd)/build:$(pwd)/build/sixdof_build:$LD_LIBRARY_PATH"
```

### 3. Install the Python Package
We recommend installing the python package in **editable mode** so changes to the code immediately take effect.

From the root project directory:
```bash
# Copy the compiled C++ extension into the python module path
cp build/dsf_core.*.so python/dsf/

# Install the Python package and dependencies
cd python
pip install -e .
```

You can verify the installation by checking if the package and GUI CLI are accessible:
```bash
dsf --help
dsf-gui --help
python -c "import dsf"
```

## Running Examples

### Static Vehicles
```bash
cd examples/static
./staticsixdof satellite.xml
./staticsixdof vehicle.xml
```

### Dynamic Vehicles
```bash
cd examples/dynamic
./staticsixdof satellite.xml
./staticsixdof vehicle.xml
```

**Note on Windows Subsystem for Linux (WSL) Visualization**:
To get visualization to work under WSL:
[WSL Issues #2855](https://github.com/microsoft/WSL/issues/2855)

---

## Development

**Include-What-You-Use (IWYU) Analysis:**
IWYU is active when configured. To use it:
```bash
cd build
cmake -DCMAKE_CXX_INCLUDE_WHAT_YOU_USE="include-what-you-use" ..
make clean && make 2>&1 | grep "should remove"
```
