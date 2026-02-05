from PyQt6.QtWidgets import QWidget, QCheckBox
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QImage, QPen, QColor, QFont, QBrush
import math
import os
import sys

class MapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 200)
        self.setStyleSheet("background-color: black;")
        
        # Load Earth Texture
        # Assuming run from root or GUI/src, but we need to find the file relative to this file
        # This file is in GUI/src/ui/map_widget.py
        # Root is ../../../
        
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        self.image_path = os.path.join(base_path, "earth_texture.jpg")
        
        self.map_image = QImage()
        if os.path.exists(self.image_path):
            if not self.map_image.load(self.image_path):
                print(f"Error: Failed to load map image from {self.image_path}")
        else:
            print(f"Error: Map image not found at {self.image_path}")
            
        self.vehicle_positions = {} # id -> (lat_deg, lon_deg)
        self.vehicle_history = {} # id -> list of (lat_deg, lon_deg)
        self.vehicle_colors = {}
        self.headers = []
        self.header_map = {}
        self.vehicle_ids = set()
        
        # Trail settings
        self.max_history = 500 # Default to short for performance
        
        # Checkbox for full trails
        self.full_trails_cb = QCheckBox("Full Trails", self)
        self.full_trails_cb.setStyleSheet("QCheckBox { color: white; font-weight: bold; background: rgba(0,0,0,100); padding: 2px; }")
        self.full_trails_cb.setChecked(False)
        self.full_trails_cb.stateChanged.connect(self._toggle_trails)
        
        # Plotting colors
        self.colors = [Qt.GlobalColor.red, Qt.GlobalColor.green, Qt.GlobalColor.cyan, 
                       Qt.GlobalColor.magenta, Qt.GlobalColor.yellow, Qt.GlobalColor.white]

    def _toggle_trails(self, state):
        if self.full_trails_cb.isChecked():
            self.max_history = 100000 # Effectively unlimited for this sim
            print("MapWidget: Full trails enabled", file=sys.stderr)
        else:
            self.max_history = 500
            print("MapWidget: Short trails enabled (Performance mode)", file=sys.stderr)
            # Truncate existing
            for vid in self.vehicle_history:
                if len(self.vehicle_history[vid]) > self.max_history:
                    # Keep latest
                    self.vehicle_history[vid] = self.vehicle_history[vid][-self.max_history:]
        self.update()

    def reset(self):
        """Clears all vehicle data and repaints."""
        self.vehicle_positions.clear()
        self.vehicle_history.clear()
        self.update()

    def resizeEvent(self, event):
        # Anchor checkbox to bottom right
        padding = 10
        cb_size = self.full_trails_cb.sizeHint()
        x = self.width() - cb_size.width() - padding
        y = self.height() - cb_size.height() - padding
        self.full_trails_cb.move(x, y)
        super().resizeEvent(event)

    def update_deep_data(self, t, data):
        """
        Updates vehicle positions from introspection data.
        t: float (simulation time)
        data: dict { block_id: { prop_name: value, ... } }
        """
        updated = False
        
        for block_id, props in data.items():
            # Check if this block looks like a vehicle with position
            # We look for lambda_d (Geodetic Lat) and l_i_earth (Geographic Lon)
            # Both are in radians.
            if "lambda_d" in props and "l_i_earth" in props:
                try:
                    lat_rad = float(props["lambda_d"])
                    lon_rad = float(props["l_i_earth"])
                    
                    lat_deg = math.degrees(lat_rad)
                    lon_deg = math.degrees(lon_rad)
                    
                    self.vehicle_positions[block_id] = (lat_deg, lon_deg)
                    
                    # Ensure color exists
                    if block_id not in self.vehicle_colors:
                         idx = len(self.vehicle_colors)
                         self.vehicle_colors[block_id] = self.colors[idx % len(self.colors)]
                    
                    # History
                    if block_id not in self.vehicle_history:
                        self.vehicle_history[block_id] = []
                    self.vehicle_history[block_id].append((lat_deg, lon_deg))
                    
                    if len(self.vehicle_history[block_id]) > self.max_history:
                        self.vehicle_history[block_id].pop(0)
                        
                    updated = True
                    self.vehicle_ids.add(block_id) # Track ID
                except (ValueError, TypeError):
                    pass
        
        if updated:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw Map
        # Scale image to cover the widget while maintaining aspect ratio? 
        # Equirectangular projection maps directly to X/Y.
        # X = (Lon + 180) / 360 * Width
        # Y = (90 - Lat) / 180 * Height
        
        # We stretch the map to fill the widget completely, assuming the user might resize it to be roughly 2:1
        # If we keep aspect ratio, we might have black bars, which is fine.
        
        w = self.width()
        h = self.height()
        
        # Draw black background
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        
        if not self.map_image.isNull():
            # Draw image stretched for full coverage (Equirectangular assumes full sphere mapping)
            painter.drawImage(self.rect(), self.map_image)
            
        # Draw Trails
        if not self.vehicle_history:
            pass
        else:
            for vid, points in self.vehicle_history.items():
                if len(points) < 2: continue
                
                base_color = self.vehicle_colors.get(vid, Qt.GlobalColor.red)
                # Create semi-transparent color
                c = QColor(base_color)
                c.setAlpha(128) # 50% opacity ? "little opacity"
                
                pen = QPen(c)
                pen.setWidth(2)
                painter.setPen(pen)
                
                # We need to draw segments, handling wrapping
                # Simple approach: Iterate points
                prev_x, prev_y = None, None
                
                # To avoid massive loops in python for thousands of points, 
                # we could optimize, but for <5000 it should be okay-ish.
                # Optimization: QPolygon? But wrapping makes it a set of polylines.
                
                # Let's do simple segment loop for now.
                
                for lat, lon in points:
                    # Normalize Lon
                    while lon > 180: lon -= 360
                    while lon < -180: lon += 360
                    
                    x = (lon + 180) / 360.0 * w
                    y = (90 - lat) / 180.0 * h
                    
                    if prev_x is not None:
                        # Check for huge jump (wrapping)
                        dist = abs(x - prev_x)
                        if dist < w / 2: # No wrap
                            painter.drawLine(QPointF(prev_x, prev_y), QPointF(x, y))
                            
                    prev_x, prev_y = x, y

        # Draw Vehicles
        for vid, (lat, lon) in self.vehicle_positions.items():
            # Convert Lat/Lon to Screen Coordinates
            # Lon: [-180, 180] -> [0, w]
            # Lat: [-90, 90] -> [h, 0] (Top is +90)
            
            # Normalize Lon to [-180, 180)
            while lon > 180: lon -= 360
            while lon < -180: lon += 360
            
            x = (lon + 180) / 360.0 * w
            y = (90 - lat) / 180.0 * h
            
            color = self.vehicle_colors.get(vid, Qt.GlobalColor.red)
            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)
            
            # Draw Crosshair
            size = 10
            painter.drawLine(int(x - size), int(y), int(x + size), int(y))
            painter.drawLine(int(x), int(y - size), int(x), int(y + size))
            
            # Draw Circle
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(x, y), size/2, size/2)
            
            # Label
            painter.setPen(Qt.GlobalColor.white)
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            label = vid if vid else "Veh"
            painter.drawText(int(x + size + 5), int(y + 5), label)
