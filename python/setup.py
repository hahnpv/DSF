from setuptools import setup, find_packages

setup(
    name="dsf",
    version="0.1.0",
    description="Interactive 6-DOF Model Configuration Interface and Simulation Bindings",
    author="DSF Team",
    packages=find_packages(),
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
    ],
    entry_points={
        "gui_scripts": [
            "dsf-gui=dsf.gui.main:main",
        ],
        "console_scripts": [
            "dsf=dsf.cli.main:cli",
        ]
    },
)
