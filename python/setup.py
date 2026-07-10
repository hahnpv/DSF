from setuptools import setup, find_packages

setup(
    name="dsf",
    version="0.1.0",
    description="Interactive 6-DOF Model Configuration Interface and Simulation Bindings",
    author="DSF Team",
    # Exclude the test package so it isn't installed into site-packages (and
    # doesn't collide with any other project's top-level `tests`).
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.8",
    install_requires=[
        "PyQt6",
        "pyqtgraph",
        "numpy",
        "pandas",
        "lxml",
        "pyqtdarktheme",
        "click",
        "pyvista",
        "h5py",
        "matplotlib",   # used by dsf.mc_plot
    ],
    extras_require={
        # Heavier/optional stacks kept out of the base install.
        "jax": ["jax"],                 # dsf.jax accelerated Monte Carlo
        "mcp": ["mcp", "pydantic"],     # dsf.mcp.server (FastMCP)
    },
    # Ship the GUI textures with the package. NOTE: the compiled dsf_core
    # extension is built by CMake and copied into python/dsf/ separately (see
    # CLAUDE.md); a wheel that bundles it needs a CMake build backend.
    package_data={"dsf.gui": ["resources/*.jpg", "resources/*.png"]},
    entry_points={
        "gui_scripts": [
            "dsf-gui=dsf.gui.main:main",
        ],
        "console_scripts": [
            "dsf=dsf.cli.main:cli",
        ]
    },
)
