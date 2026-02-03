from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QTreeWidget, QTreeWidgetItem, QSplitter, QHeaderView
from PyQt6.QtCore import Qt, pyqtSlot
import sys
import pyqtgraph as pg
# pg.setConfigOption('useOpenGL', False) # Moved to main.py
import numpy as np
from collections import deque

class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(False) # Prevent interference with dock dragging
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter for list and plot
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)
        
        # Left Panel: Variable Selection
        self.selection_panel = QWidget()
        self.selection_layout = QVBoxLayout(self.selection_panel)
        self.selection_layout.addWidget(QLabel("Select Signals:"))
        
        self.var_tree = QTreeWidget()
        self.var_tree.setHeaderHidden(True)
        self.var_tree.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        self.var_tree.itemSelectionChanged.connect(self.on_selection_changed)
        self.selection_layout.addWidget(self.var_tree)
        
        self.splitter.addWidget(self.selection_panel)
        
        # Right Panel: Plot
        self.plot_panel = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_panel)
        self.graph = pg.PlotWidget(title="Real-Time Data")
        self.graph.showGrid(x=True, y=True)
        self.graph.addLegend()
        self.plot_layout.addWidget(self.graph)
        
        self.splitter.addWidget(self.plot_panel)
        self.splitter.setStretchFactor(1, 4) # Plot gets more space
        
        # Data
        self.headers = []
        self.data_history = {} # Key: header_index, Value: deque
        self.time_history = deque(maxlen=1000)
        # Increase points slightly since user might want to see more history now
        self.max_points = 2000
        
        self.curves = {} # Key: header_index, Value: PlotDataItem
        
        # Palette for multiple lines
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w']
        
        self.persisted_selection = set() # Stores variable names

    @pyqtSlot(list)
    def set_headers(self, headers):
        print(f"PlotWidget: Received {len(headers)} headers.", file=sys.stderr)
        if headers:
            print(f"PlotWidget: Sample headers: {headers[:10]}", file=sys.stderr)
        self.headers = headers
        
        self.var_tree.blockSignals(True)
        self.var_tree.clear()
        
        # Group headers
        groups = {} # name -> list of (header_idx, header_name)
        globals_list = []
        
        # Robust Vehicle Detection Strategy
        # 1. Identify potential Vehicle IDs using "Anchor" variables (common simulation outputs)
        #    This allows us to find "GPS_1" from "GPS_1_Latitude" or "GPS_1_a".
        anchors = [
            "Latitude", "Longitude", "altitude", "Altitude",
            "x", "y", "z", "pos_x", "pos_y", "pos_z",
            "a", "e", "i", "inc", "eccentricity", "tanom", "omega", "Omega", "RAAN", "ap",
            "tanomd"
        ]
        
        vehicle_ids = set()
        for h in headers:
            # Check if header ends with _{Anchor}
            for anchor in anchors:
                suffix = "_" + anchor
                if h.endswith(suffix):
                    # Found a candidate prefix
                    vid = h[:-len(suffix)] # Strip suffix
                    if vid:
                        vehicle_ids.add(vid)
                    break # Only match one anchor per header to avoid double counting
        
        # 2. Sort Vehicle IDs by length (descending) to match longest specific prefix first
        #    e.g. if we have "GPS_1" and "GPS_1_Module", we might want to prioritize specific?
        #    Actually, we want "GPS_1" to catch "GPS_1_Module_x".
        #    So we match standard prefixes.
        sorted_vids = sorted(list(vehicle_ids), key=len, reverse=True)
        
        # print(f"DEBUG: Discovered Vehicles: {sorted_vids}", file=sys.stderr)

        # 3. Assign Headers to Groups
        for i, h in enumerate(headers):
            matched = False
            for vid in sorted_vids:
                # Check for "Vehicle_Variable" pattern
                prefix = vid + "_"
                if h.startswith(prefix):
                    if vid not in groups:
                        groups[vid] = []
                    groups[vid].append((i, h))
                    matched = True
                    break # Assigned to longest matching vehicle
                elif h == vid: # Exact match (rare for value, but possible)
                    if vid not in groups:
                        groups[vid] = []
                    groups[vid].append((i, h))
                    matched = True
                    break
            
            if not matched:
                globals_list.append((i, h))

        # print(f"PlotWidget: Groups found: {list(groups.keys())[:10]}", file=sys.stderr)
                
        # Create Tree Items
        
        # Add Groups
        for vid in sorted(groups.keys()):
            # Vehicle Parent
            group_item = QTreeWidgetItem(self.var_tree)
            group_item.setText(0, vid if vid else "Main Vehicle")
            # Make parent selectable? Usually selecting group selects all children.
            # But specific logic might be needed. Default QTreeWidget behavior allows selection.
            # We'll mark UserRole as -1 to indicate group.
            group_item.setData(0, Qt.ItemDataRole.UserRole, -1)
            
            for idx, h_name in groups[vid]:
                child = QTreeWidgetItem(group_item)
                # Strip prefix for cleaner display?
                # e.g. "GPS_1_Latitude" -> "Latitude" under "GPS_1"
                display_name = h_name
                if vid:
                    display_name = h_name.replace(vid, "").strip("_")
                
                child.setText(0, display_name if display_name else h_name)
                # Store full index
                child.setData(0, Qt.ItemDataRole.UserRole, idx)
                # Store full name for tooltip/debug
                child.setToolTip(0, h_name)
                
                if h_name in self.persisted_selection:
                    child.setSelected(True)
                    group_item.setExpanded(True) # Expand if containing selection

        # Add Globals
        if globals_list:
            other_parent = None
            if len(groups) > 0:
                other_parent = QTreeWidgetItem(self.var_tree)
                other_parent.setText(0, "Global / Other")
                other_parent.setData(0, Qt.ItemDataRole.UserRole, -1)
                parent_node = other_parent
            else:
                # If no groups, just add to root
                parent_node = self.var_tree.invisibleRootItem()
                
            for idx, h_name in globals_list:
                child = QTreeWidgetItem()
                child.setText(0, h_name)
                child.setData(0, Qt.ItemDataRole.UserRole, idx)
                
                if parent_node == self.var_tree.invisibleRootItem():
                     self.var_tree.addTopLevelItem(child)
                else:
                     parent_node.addChild(child)
                     
                if h_name in self.persisted_selection:
                    child.setSelected(True)
                    if other_parent: other_parent.setExpanded(True)

        self.var_tree.blockSignals(False)
        
        # Clear data logic same as before
        self.curves.clear()
        self.data_history.clear()
        self.time_history.clear()
        self.graph.clear()
        
        for i in range(len(headers)):
            self.data_history[i] = deque(maxlen=self.max_points)
            
        self.refresh_curves()

    def refresh_curves(self):
        # Update plotted curves based on current selection
        selected_items = self.var_tree.selectedItems()
        selected_idxs = set()
        
        # 1. Add new curves
        for item in selected_items:
            idx = item.data(0, Qt.ItemDataRole.UserRole)
            if idx is None or idx == -1:
                continue # Skip groups
                
            selected_idxs.add(idx)
            
            if idx not in self.curves:
                color = self.colors[len(self.curves) % len(self.colors)]
                name = self.headers[idx]
                self.curves[idx] = self.graph.plot(pen=color, name=name)
        
        # 2. Remove unselected traces
        current_idxs = list(self.curves.keys())
        for idx in current_idxs:
            if idx not in selected_idxs:
                self.graph.removeItem(self.curves[idx])
                del self.curves[idx]

    def reset_plots(self):
        """Clears all plot data and history."""
        self.data_history.clear()
        self.time_history.clear()
        self.graph.clear()
        self.curves.clear()
        
        # Re-initialize empty buffers for current headers
        for i in range(len(self.headers)):
            self.data_history[i] = deque(maxlen=self.max_points)
            
        # Re-plot empty curves? Or wait for update?
        # Ideally wait for update.
        print("PlotWidget: Reset complete.")

    @pyqtSlot(list)
    def update_data(self, values):
        if not self.headers:
            return
            
        # Assume first value is Time? No, sim.output headers usually start with "Time" if using default report?
        # Actually `sim.output.get_current_values()` follows `output.h` structure:
        # doubles, vectors, matrices.
        # "Time" is output by `writeHeader` but `get_current_values` DOES NOT INCLUDE TIME by default unless explicit?
        # Checking output.h: `get_current_values` strictly loops doubles/vectors/matrices.
        # `report()` writes `t()` first.
        # So I probably DON'T get time in `values`.
        # I rely on `sim.clock.t()`? But synchronization?
        # Actually, simpler: Use sample count as X, or just append distinct time?
        # Sim sends values.
        # I should probably emit time with data?
        # SimulationWorker emits `vals = sim.output.get_current_values()`.
        # I should assume time is NOT in there (unless I added it as a variable?).
        # I'll enable X-axis as "Sample Count" for now, or assume constant polling rate.
        # Wait, I want time.
        # I'll update Worker to emit time too?
        # Or just append locally.
        
        # For now, let's treat the incoming array as data points.
        
        # Update history
        for i, val in enumerate(values):
            if i < len(self.headers):
                 self.data_history[i].append(val)
        
        # Update plotted curves (only if visible)
        if not self.isVisible():
            return

        selected_items = self.var_tree.selectedItems()
        for i, item in enumerate(selected_items):
            idx = item.data(0, Qt.ItemDataRole.UserRole)
            if idx is None or idx == -1: 
                continue
                
            if idx not in self.curves:
                # Create curve
                color = self.colors[len(self.curves) % len(self.colors)]
                self.curves[idx] = self.graph.plot(pen=color, name=self.headers[idx])
            
            # Update data
            # Use simple numpy conversion
            self.curves[idx].setData(list(self.data_history[idx]))

    def on_selection_changed(self):
        # Update persistence
        selected_items = self.var_tree.selectedItems()
        # 1. Remove all currently displayed headers from persistence
        current_header_names = set(self.headers)
        self.persisted_selection = self.persisted_selection - current_header_names
        
        # 2. Add currently selected items back
        for item in selected_items:
            idx = item.data(0, Qt.ItemDataRole.UserRole)
            if idx is not None and idx != -1:
                name = self.headers[idx]
                self.persisted_selection.add(name)
            
        self.refresh_curves()
