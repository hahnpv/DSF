
# Compatibility shim: the loaders live in dsf.utils.data_loader.
# (load_csv_trajectory was removed 2026-07-11 — it had no consumers.)
from dsf.utils.data_loader import load_h5_trajectory
from .globe import GlobePlotter
