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
        
        # Main Container for 2D PlotWidget
        # We removed the QSplitter since the Globe is now in a separate window
        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        
        self.setCentralWidget(self.plot_container)
        
        self.plot_widget = None
        self.init_btn = None
        
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
        
        # Disambiguate duplicate headers
        # e.g. ["Latitude", "Longitude", "Latitude", "Longitude"] -> ["Latitude_0", "Longitude_0", "Latitude_1", "Longitude_1"]
        # Or even better: "Vehicle_1_Latitude" if we could infer it?
        # But for now, simple counter suffix if collision found.
        
        self.headers = []
        counts = {}
        # First pass count
        for h in headers:
            counts[h] = counts.get(h, 0) + 1
            
        current_counts = {}
        for h in headers:
            if counts[h] > 1:
                idx = current_counts.get(h, 0)
                unique_name = f"{h}_{idx}"
                current_counts[h] = idx + 1
                self.headers.append(unique_name)
            else:
                self.headers.append(h)

        self.header_map = {name: i for i, name in enumerate(self.headers)}
        
        # Identity all unique vehicles by looking for "_Latitude" or just "Latitude"
        # If multiple vehicles exist, they usually prefix with the vehicle id (fixed in fix_ids.py)
        # With disambiguation, we might get "Latitude_0", "Latitude_1".
        # We need a robust way to identify vehicle groups.
        self.vehicle_ids = set()
        
        # Strategy: Look for "Latitude" substring.
        for h in self.headers:
            if "Latitude" in h:
                # Special handling for duplicate "Latitude" columns (e.g. Latitude_0, Latitude_1)
                # These usually come from the same vehicle reporting multiple times (flat hierarchy)
                # We only want to track the primary one (index 0 or no suffix)
                if h.startswith("Latitude_"):
                    try:
                        suffix = h.split("_")[-1]
                        if suffix.isdigit() and int(suffix) > 0:
                            # Skip Latitude_1, Latitude_2, etc. to avoid ghost vehicles
                            continue
                    except ValueError:
                        pass

                # e.g. "GPS_1_Latitude", "Latitude_0"
                vid = h.replace("Latitude", "").strip("_")
                self.vehicle_ids.add(vid)
        
        # If empty set (maybe "Lat"?), default to 0
        if not self.vehicle_ids:
             self.vehicle_ids.add("0")
        
        # print(f"DEBUG: PlotWindow Headers set. Found {len(self.vehicle_ids)} vehicles: {self.vehicle_ids}", file=sys.stderr)
        # print(f"DEBUG: Headers: {self.headers}", file=sys.stderr)

    def _launch_globe_window(self):
        """Launches the 3D globe in a separate Process."""
        import subprocess
        import time
        
        if hasattr(self, "viz_process") and self.viz_process and self.viz_process.poll() is None:
            # print("DEBUG: 3D Viz process already running.")
            return

        try:
            # Cleanup any zombie instances from previous runs
            try:
                subprocess.run(["pkill", "-f", "viz_receiver.py"], check=False)
                time.sleep(0.5) # Give it time to die and release port
            except Exception:
                pass

            # print("DEBUG: Launching viz_receiver.py subprocess...", file=sys.stderr)
            script_path = os.path.join(os.path.dirname(__file__), "../viz_receiver.py")
            # Use -u for unbuffered output to see logs immediately
            self.viz_process = subprocess.Popen([sys.executable, "-u", script_path])
            
        except Exception as e:
            print(f"Error launching 3D Globe Process: {e}")
            self.viz_process = None

    def showEvent(self, event):
        super().showEvent(event)

    def set_plot_widget(self, widget):
        if self.plot_widget:
            self.plot_layout.removeWidget(self.plot_widget)
        self.plot_widget = widget
        if self.plot_widget:
            self.plot_layout.addWidget(self.plot_widget)


    def reset_view(self):
        """Clears 3D visualization by sending reset command."""
        self.render_counter = 0
        try:
            import json
            msg = json.dumps({"command": "reset"}).encode('utf-8')
            self.udp_sock.sendto(msg, (self.udp_ip, self.udp_port))
            print("PlotWindow: Sent RESET command to 3D Viz.")
        except Exception as e:
            print(f"Error sending RESET: {e}")

    def update_3d_data(self, data):
        """Called to update the 3D globe with new simulation data."""
        # print(f"DEBUG: update_3d_data called with {len(data)} items", file=sys.stderr)
    def update_3d_data(self, data):
        """Called to update the 3D globe with new simulation data."""
        # print(f"DEBUG: update_3d_data called with {len(data)} items", file=sys.stderr)
        if not self.headers or not self.header_map:
            return

        self.render_counter += 1
        if self.render_counter % 2 != 0: 
            return

        # Prepare a dictionary of positions for all vehicles
        positions = {}
        
        # WGS84 Constants
        a = 6378137.0
        f = 1.0 / 298.257223563
        e2 = f * (2 - f)

        import math
        R_EARTH = 6378137.0
        
        for vid in self.vehicle_ids:
            prefix = f"{vid}_" if vid else ""
            
            # Key candidates for this specific vehicle
            # Try Prefix first (e.g. GPS_1_Latitude)
            lat_key = f"{prefix}Latitude"
            lon_key = f"{prefix}Earth Longitude" if f"{prefix}Earth Longitude" in self.header_map else f"{prefix}Longitude"
            alt_key = f"{prefix}Altitude"
            
            idx_lat = self.header_map.get(lat_key)
            idx_lon = self.header_map.get(lon_key)
            idx_alt = self.header_map.get(alt_key)

            # If not found, try Suffix (e.g. Latitude_0)
            if idx_lat is None:
                lat_key = f"Latitude_{vid}"
                lon_key = f"Earth Longitude_{vid}" if f"Earth Longitude_{vid}" in self.header_map else f"Longitude_{vid}"
                alt_key = f"Altitude_{vid}"
                if alt_key not in self.header_map and f"altitude_{vid}" in self.header_map:
                    alt_key = f"altitude_{vid}"
                
                idx_lat = self.header_map.get(lat_key)
                idx_lon = self.header_map.get(lon_key)
                idx_alt = self.header_map.get(alt_key)
            
            if idx_lat is not None and idx_lon is not None and idx_alt is not None:
                try:
                    phi = float(data[idx_lat])
                    theta = float(data[idx_lon]) 
                    h = float(data[idx_alt])

                    if math.isnan(phi) or math.isnan(theta) or math.isnan(h):
                        # print(f"DEBUG: NaNs found for {vid}", file=sys.stderr)
                        continue
                        
                    x_sph = (R_EARTH + h) * math.cos(math.radians(phi)) * math.cos(math.radians(theta))
                    y_sph = (R_EARTH + h) * math.cos(math.radians(phi)) * math.sin(math.radians(theta))
                    z_sph = (R_EARTH + h) * math.sin(math.radians(phi))

                    # Use simple mapping for now. 
                    # Note: Original code used (x,y,z) map directly if available? No, we need LLA to XYZ usually for Globe.
                    # Wait, the visualization expects XYZ or LLA?
                    # The `viz_receiver` expects "x", "y", "z".
                    # Let's use the computed spherical ones.
                    
                    positions[vid or "Vehicle"] = {"x": x_sph, "y": y_sph, "z": z_sph}
                    # print(f"DEBUG: {vid} LLA=({phi:.2f}, {theta:.2f}, {h:.2f}) -> XYZ", file=sys.stderr)

                except Exception as e:
                    # print(f"DEBUG: Error processing keys for {vid}: {e}", file=sys.stderr)
                    pass
            else:
                if self.render_counter % 100 == 0:
                     pass
                    # print(f"DEBUG: Keys missing for {vid}. lat_key={lat_key} found={idx_lat is not None}", file=sys.stderr)

        if positions:
            try:
                import json
                msg = json.dumps(positions).encode('utf-8')
                self.udp_sock.sendto(msg, (self.udp_ip, self.udp_port))
                # print(f"DEBUG: Sent {len(msg)} bytes to Viz", file=sys.stderr)
            except Exception as e:
                # Always print send errors
                if self.render_counter % 100 == 0:
                    print(f"UDP Send Error: {e}", file=sys.stderr)

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
