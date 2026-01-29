from setuptools import setup, find_packages

setup(
    name="dsf-gui",
    version="0.1.0",
    description="Interactive 6-DOF Model Configuration Interface",
    author="DSF Team",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    py_modules=["main"],
    python_requires=">=3.8",
    install_requires=[
        "PyQt6",
        "pyqtgraph",
        "numpy",
        "pandas",
        "lxml",
        "pyqtdarktheme",
    ],
    entry_points={
        "gui_scripts": [
            "dsf-gui=main:main",  # Assuming main.py has a main function, I'll check/fix main.py next
        ],
    },
)
