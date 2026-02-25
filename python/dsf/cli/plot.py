"""
dsf.cli.plot
------------
Replay an HDF5 output file in the interactive strip-chart (PlotWidget).
"""

from __future__ import annotations
import sys
import os


def run_plot(h5_path: str):
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
    from PyQt6.QtCore import QTimer

    from dsf.gui.ui.plot_widget import PlotWidget
    from dsf.utils.data_loader import load_h5

    print(f"Loading {h5_path}...")
    times, data = load_h5(h5_path)
    print(f"  {len(times)} timesteps, {sum(len(v) for v in data.values())} signals "
          f"across {len(data)} block(s)")

    app = QApplication.instance() or QApplication(sys.argv)

    win = QMainWindow()
    win.setWindowTitle(f"dsf plot — {os.path.basename(h5_path)}")
    win.resize(1200, 700)

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    win.setCentralWidget(container)

    pw = PlotWidget()
    layout.addWidget(pw)

    # Feed all frames at once — PlotWidget accumulates in deques
    for i, t in enumerate(times):
        frame = {
            block_id: {
                prop: (vals[i].tolist() if hasattr(vals[i], "tolist") and vals[i].ndim > 0 else float(vals[i]))
                for prop, vals in props.items()
            }
            for block_id, props in data.items()
        }
        pw.update_deep_data(t, frame)

    win.show()
    sys.exit(app.exec())
