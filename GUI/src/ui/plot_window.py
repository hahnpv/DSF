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

        self.viz_process = None
        self.traj_history = []
        self.headers = None
        self.header_map = {}
        self.render_counter = 0

        # UDP Sender for 3D Viz
        import socket
        self.udp_ip = "127.0.0.1"
        self.udp_port = 5556
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Non-blocking not strictly needed for sending, but good practice
        self.udp_sock.setblocking(False)

    def set_headers(self, headers):
        """Called by SimulationWorker to provide signal names matching the data list."""
        self.headers = headers
        self.header_map = {name: i for i, name in enumerate(headers)}
        print(f"DEBUG: PlotWindow received {len(headers)} headers: {headers}")

    def _launch_globe_window(self):
        """Launches the 3D globe in a separate Process."""
        import subprocess
        import time
        
        if hasattr(self, "viz_process") and self.viz_process and self.viz_process.poll() is None:
            print("DEBUG: 3D Viz process already running.")
            return

        try:
            # Cleanup any zombie instances from previous runs
            # We can't easily rely on PID tracking across restarts, so we use pkill
            # This is safe-ish because we are targeting our specific script
            try:
                subprocess.run(["pkill", "-f", "viz_receiver.py"], check=False)
                time.sleep(0.5) # Give it time to die and release port
            except Exception:
                pass

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
        # Only send if headers are known
        if not self.headers or not self.header_map:
            return

        # Throttle: Simulation might run at 100Hz+, we only need ~60Hz for Viz
        self.render_counter += 1
        if self.render_counter % 2 != 0: # Send every 2nd frame (50% subsampling)
            return

        try:
            # Extract XYZ
            # Only perform lookup if we haven't cached indices? 
            # Optimization: Cache indices in set_headers? For now map lookup is fast enough.
            
            def get_val(key_candidates):
                for key in key_candidates:
                    idx = self.header_map.get(key)
                    if idx is not None and idx < len(data):
                        return data[idx]
                return None

            # Try to calculate from LLA (Latitude, Longitude, Altitude) if available
            # This is more robust than relying on "Earth XYZ" which might be local/relative
            lat = get_val(["Latitude", "Lat"])
            lon = get_val(["Earth Longitude", "Longitude", "Lon"]) # Prefer Earth-Start (Fixed) Longitude
            alt = get_val(["Altitude", "Alt"])
            
            x, y, z = None, None, None
            
            if lat is not None and lon is not None and alt is not None:
                try:
                    import math
                    # WGS84 Ellipsoid Constants
                    a = 6378137.0
                    f = 1.0 / 298.257223563
                    e2 = f * (2 - f)
                    
                    phi = float(lat) # Radians
                    theta = float(lon) # Radians
                    h = float(alt)
                    
                    sin_phi = math.sin(phi)
                    cos_phi = math.cos(phi)
                    
                    # Prime Vertical Radius of Curvature
                    N = a / math.sqrt(1 - e2 * (sin_phi ** 2))
                    
                    # ECEF Conversion
                    x = (N + h) * cos_phi * math.cos(theta)
                    y = (N + h) * cos_phi * math.sin(theta)
                    z = (N * (1 - e2) + h) * sin_phi
                    
                except Exception as e:
                    print(f"LLA Extraction Error: {e}")

            # Fallback to direct XYZ if LLA failed
            if x is None:
                x = get_val(["Earth XYZ (x)", "Inertial Position (x)"])
                y = get_val(["Earth XYZ (y)", "Inertial Position (y)"])
                z = get_val(["Earth XYZ (z)", "Inertial Position (z)"])
            
            if x is not None and y is not None and z is not None:
                # Prepare JSON packet
                import json
                packet = {
                    "x": float(x),
                    "y": float(y),
                    "z": float(z)
                }
                msg = json.dumps(packet).encode('utf-8')
                self.udp_sock.sendto(msg, (self.udp_ip, self.udp_port))
                
        except Exception as e:
            # Don't spam print on every frame if error
            if self.render_counter % 100 == 0:
                print(f"UDP Send Error: {e}")

    def hideEvent(self, event):
        self.visibilityChanged.emit(False)
        super().hideEvent(event)

    def closeEvent(self, event):
        if self.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
            # Real Close (App Exit)
            if self.viz_process:
                print("DEBUG: Terminating 3D Receiver Process...")
                self.viz_process.terminate()
                self.viz_process = None
            event.accept()
            return
            
        # We just hide the window when the user clicks 'X'
        self.visibilityChanged.emit(False)
        self.hide()
        event.ignore()
