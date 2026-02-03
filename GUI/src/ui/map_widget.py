from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QImage, QPen, QColor, QFont, QBrush
import math
import os

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
        
        # Plotting colors
        self.colors = [Qt.GlobalColor.red, Qt.GlobalColor.green, Qt.GlobalColor.cyan, 
                       Qt.GlobalColor.magenta, Qt.GlobalColor.yellow, Qt.GlobalColor.white]

    def set_headers(self, headers):
        self.headers = headers
        self.header_map = {name: i for i, name in enumerate(headers)}
        
        self.vehicle_ids.clear()
        
        # Identify vehicles (Reuse logic from PlotWindow)
        for h in self.headers:
            if "Latitude" in h:
                vid = h.replace("Latitude", "").strip("_")
                self.vehicle_ids.add(vid)
                
        if not self.vehicle_ids:
            # Fallback for simple cases where maybe headers are just "Lat", "Lon" or similar?
            # Or if "Latitude" is present but no suffix/prefix (meaning "" ID)
            pass
            
        # Assign colors
        self.vehicle_colors.clear()
        for i, vid in enumerate(sorted(list(self.vehicle_ids))):
            self.vehicle_colors[vid] = self.colors[i % len(self.colors)]

    def reset(self):
        """Clears all vehicle data and repaints."""
        self.vehicle_positions.clear()
        self.vehicle_history.clear()
        self.update()

    def update_data(self, values):
        if not self.headers or not self.header_map:
            return
            
        updated = False
        
        for vid in self.vehicle_ids:
            prefix = f"{vid}_" if vid else ""
            
            # Try Prefix
            lat_key = f"{prefix}Latitude"
            lon_key = f"{prefix}Earth Longitude" 
            if lon_key not in self.header_map:
                 lon_key = f"{prefix}Longitude"
            
            idx_lat = self.header_map.get(lat_key)
            idx_lon = self.header_map.get(lon_key)
            
            # Try Suffix if prefix failed
            if idx_lat is None:
                lat_key = f"Latitude_{vid}"
                lon_key = f"Earth Longitude_{vid}"
                if lon_key not in self.header_map:
                    lon_key = f"Longitude_{vid}"
                
                idx_lat = self.header_map.get(lat_key)
                idx_lon = self.header_map.get(lon_key)
            
            if idx_lat is not None and idx_lon is not None:
                try:
                    lat = values[idx_lat]
                    lon = values[idx_lon]
                    
                    if not (math.isnan(lat) or math.isnan(lon)):
                        self.vehicle_positions[vid] = (lat, lon)
                        
                        # Add to history
                        if vid not in self.vehicle_history:
                            self.vehicle_history[vid] = []
                        self.vehicle_history[vid].append((lat, lon))
                        
                        # Limit history size for performance? Maybe 5000 points?
                        if len(self.vehicle_history[vid]) > 5000:
                            self.vehicle_history[vid].pop(0)
                        
                        updated = True
                except IndexError:
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
