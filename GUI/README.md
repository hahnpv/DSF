# DSF GUI

Interactive 6-DOF Model Configuration Interface for the DSF project.

## Overview
This GUI allows users to:
- Drag and drop 6-DOF models to compose simulations.
- Visualize connections and hierarchy.
- Configure parameters and initial conditions.
- Run simulations (via C++ bindings) and view real-time plots.

## Installation

Ensure you have the DSF miniconda environment active:
```bash
conda activate DSF
```

Install the package in editable mode:
```bash
pip install -e .
```

## Usage

To run the GUI:
```bash
python src/main.py
```
Or if installed:
```bash
dsf-gui
```

## Structure
- `src/core`: Core logic and model registry.
- `src/ui`: PyQt6 widgets and windows.
- `src/execution`: Simulation execution handling.
- `src/utils`: XML processing and serialization.

## License
MIT
