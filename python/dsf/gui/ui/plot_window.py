from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
import sys
import os

# Ensure we can import from python package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))) # Point to root

try:
    from pyvistaqt import QtInteractor
    from dsf.visualization.globe import GlobePlotter
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



    def update_deep_data(self, t, data):
        """
        Updates 3D globe using introspection data (xyz_e).
        t: float (simulation time)
        data: dict { block_id: { prop_name: value, ... } }
        """
        self.render_counter += 1
        if self.render_counter % 2 != 0: 
            return

        positions = {}
        
        for block_id, props in data.items():
            # Look for explicit Earth-Fixed coordinates first
            if "xyz_e" in props:
                try:
                    val = props["xyz_e"]
                    # Expecting list [x, y, z] from introspection
                    if isinstance(val, list) and len(val) == 3:
                        # Extract Vehicle block ID if possible (e.g. Vehicle_EOM -> Vehicle)
                        # Heuristic: split by underscore, take first part if it looks like an ID?
                        # Or better: The map widget used the block_id directly.
                        # The block_id here is likely the EOM name (e.g. "Vehicle_EOM" or similar).
                        # Let's try to infer a cleaner ID for display.
                        
                        vid = block_id
                        # Strip common suffixes/prefixes if we can guess hierarchy?
                        # For now, use full ID to be safe and distinct.
                        
                        positions[vid] = {"x": val[0], "y": val[1], "z": val[2]}
                except Exception:
                    pass
        
        if positions:
            try:
                import json
                msg = json.dumps(positions).encode('utf-8')
                self.udp_sock.sendto(msg, (self.udp_ip, self.udp_port))
            except Exception as e:
                pass

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
        event.accept()

    def set_plot_widget(self, widget):
        if self.plot_widget:
            self.plot_layout.removeWidget(self.plot_widget)
        self.plot_widget = widget
        if self.plot_widget:
            self.plot_layout.addWidget(self.plot_widget)
