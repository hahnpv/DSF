from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
import sys
import os

# Ensure we can import from python package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))) # Point to root

try:
    from pyvistaqt import QtInteractor
    from python.visualization.globe import GlobePlotter
except ImportError as e:
    print(f"Warning: Could not import 3D viz dependencies: {e}")
    QtInteractor = None
    GlobePlotter = None


class PlotWindow(QMainWindow):
    visibilityChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Real-Time Plotting")
        self.resize(1200, 800)
        
        # Use standard Window type. Tool windows can have weird hide/show behavior on some Linux WMs.
        self.setWindowFlags(Qt.WindowType.Window)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)
        
        # Left Side: Container for 2D PlotWidget
        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.plot_container)
        
        self.plot_widget = None
        self.init_btn = None
        
        # Right Side: Controls for 3D Globe (Detached)
        self.globe_controls = QWidget()
        self.globe_layout = QVBoxLayout(self.globe_controls)
        
        from PyQt6.QtWidgets import QLabel
        self.globe_layout.addWidget(QLabel("3D Visualization"))
        self.globe_layout.addWidget(QLabel("Launch from Main Toolbar"))
        self.globe_layout.addStretch()
        
        self.splitter.addWidget(self.globe_controls)

        self.globe_plotter = None
        self.traj_history = []
        self.headers = None
        self.header_map = {}
        self.render_counter = 0

    def set_headers(self, headers):
        """Called by SimulationWorker to provide signal names matching the data list."""
        self.headers = headers
        self.header_map = {name: i for i, name in enumerate(headers)}
        print(f"DEBUG: PlotWindow received {len(headers)} headers.")

    def _launch_globe_window(self):
        """Launches the 3D globe in a separate Process."""
        import subprocess
        
        if hasattr(self, "viz_process") and self.viz_process and self.viz_process.poll() is None:
            print("DEBUG: 3D Viz process already running.")
            return

        try:
            print("DEBUG: Launching viz_receiver.py subprocess...")
            
            script_path = os.path.join(os.path.dirname(__file__), "../viz_receiver.py")
            
            # Launch detached process
            # sys.executable ensures we use the same python interpreter
            self.viz_process = subprocess.Popen([sys.executable, script_path])
            
        except Exception as e:
            print(f"Error launching 3D Globe Process: {e}")
            import traceback
            traceback.print_exc()
            self.viz_process = None

    def showEvent(self, event):
        super().showEvent(event)
        # Timer removed - manual init only for safety
        # Set initial split (50/50 or prefer 2D slightly)
        self.splitter.setSizes([600, 600])

    def set_plot_widget(self, widget):
        if self.plot_widget:
            self.plot_layout.removeWidget(self.plot_widget)
        self.plot_widget = widget
        if self.plot_widget:
            self.plot_layout.addWidget(self.plot_widget)
            
    def update_3d_data(self, data):
        """Called to update the 3D globe with new simulation data."""
        # Disconnected for performance testing as per user request
        return
        
        if not self.globe_plotter:
            return
            
        # If we haven't received headers yet, we can't map the list data
        if not self.headers or not self.header_map:
            return

        # Extract Earth XYZ positions using the header map
        try:
            def get_val(key_candidates):
                for key in key_candidates:
                    idx = self.header_map.get(key)
                    if idx is not None and idx < len(data):
                        return data[idx]
                return None

            x = get_val(["Earth XYZ (x)", "Earth XYZ (x) "])
            y = get_val(["Earth XYZ (y)", "Earth XYZ (y) "])
            z = get_val(["Earth XYZ (z)", "Earth XYZ (z) "])
            
            if x is not None and y is not None and z is not None:
                 self.traj_history.append([float(x), float(y), float(z)])
                 
                 # Optimization: Update every N points? Or limit history length.
                 if len(self.traj_history) > 2:
                     import numpy as np
                     pts = np.array(self.traj_history)
                     
                     # Limit memory usage (tail 5000 points)
                     if len(pts) > 5000:
                         pts = pts[-5000:]
                         self.traj_history = self.traj_history[-5000:]
                     
                     self.globe_plotter.add_trajectory(pts, name="LiveTraj", color="cyan", stop_marker=True)
                     # self.globe_plotter.add_ground_track(pts, name="LiveGround", color="magenta")
                     
                     # Force render update for detached window (Throttled)
                     self.render_counter += 1
                     if self.globe_plotter and hasattr(self.globe_plotter, "plotter"):
                         # Only render every 10th frame to keep UI responsive in software mode
                         if self.render_counter % 10 == 0:
                             self.globe_plotter.plotter.update()
    
                     # Check if we need to focus once?
                     if len(self.traj_history) == 5:
                         print("DEBUG: First trajectory segment added. Resetting camera.")
                         self.globe_plotter.plotter.reset_camera()
        except Exception as e:
            print(f"Error in update_3d_data: {e}")

    def hideEvent(self, event):
        self.visibilityChanged.emit(False)
        super().hideEvent(event)

    def closeEvent(self, event):
        if self.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
            event.accept()
            return
            
        # We just hide the window when the user clicks 'X'
        self.visibilityChanged.emit(False)
        self.hide()
        event.ignore()
