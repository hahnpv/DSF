from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QTreeWidget, QTreeWidgetItem, QSplitter, QHeaderView
from PyQt6.QtCore import Qt, pyqtSlot
import sys
import pyqtgraph as pg
import numpy as np
from collections import deque

class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(False)
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
        self.var_tree.setHeaderLabel("Simulation Data")
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
        self.graph.setLabel('bottom', "Time", units='s')
        self.plot_layout.addWidget(self.graph)
        
        self.splitter.addWidget(self.plot_panel)
        self.splitter.setStretchFactor(1, 4)
        
        # Data Management
        self.time_history = deque(maxlen=2000)
        self.data_history = {} # Key: (block_id, prop_name, sub_index), Value: deque
        self.max_points = 2000
        
        # Plotting
        self.curves = {} # Key: (block_id, prop_name, sub_index), Value: PlotDataItem
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w', 'orange', 'purple']
        
        # Introspection State
        self.known_structure = set() # Set of known keys (block_id, prop_name) to avoid tree rebuilds
        self.block_items = {} # block_id -> QTreeWidgetItem
        self.vehicle_items = {} # vehicle_id -> QTreeWidgetItem
        
        self.persisted_selection = set() # Set of keys (block_id, prop_name, sub_index)

    @pyqtSlot(list)
    def set_headers(self, headers):
        # Legacy support or mixed mode? 
        # For now, we ignore flat headers if we are using Deep Data.
        # But if Deep Data is not available, we could fallback.
        # However, user requested Introspection Driving.
        pass

    @pyqtSlot(list)
    def update_data(self, values):
        # Legacy flat data update. Ignored in favor of update_deep_data for this mode.
        pass

    def update_deep_data(self, t, data):
        """
        t: float (simulation time)
        data: dict { block_id: { prop_name: value, ... } }
        """
        # 1. Update Time
        self.time_history.append(t)
        
        # 2. Process Data
        # We need to detect new structure dynamically
        structure_changed = False
        
        for block_id, props in data.items():
            # Heuristic for Vehicle ID: Split by first underscore? 
            # e.g. "GPS_1_Equinoctial" -> "GPS_1"
            # If no underscore, use block_id as Vehicle (if strictly flat) or "Global"
            
            # Better heuristic: "Vehicle" is usually the top level prefix for components.
            # We can try to infer hierarchy or just group by prefix.
            
            if "_" in block_id:
                # Find the 'Vehicle' part. 
                # Usually standard format: {VehicleName}_{Component}
                # But sometimes {VehicleName} has underscores.
                # Let's assume the LAST part is the Component if multiple parts?
                # Or parsing the known XML structure? 
                # Let's try to match existing Vehicle IDs from MapWidget logic?
                # Simpler: First part is Vehicle.
                parts = block_id.split('_')
                if len(parts) > 1:
                    # Check if first part looks like a vehicle?
                    # "GPS_BIIR-2__(PRN_13)__2_Equinoctial" -> Vehicle is "GPS_BIIR-2__(PRN_13)__2"
                    # The suffix is the dynamic block name.
                    # This is tricky without knowing the exact separator.
                    # But generic "starts with" logic works well.
                    # Let's just USE the whole block_id as the group if we can't be sure?
                    # No, we want grouping.
                    
                    # Let's assume the introspection ID coming from headless_runner 
                    # was constructed as `parentID_childName`.
                    # Recursively: `VehicleID_Equinoctial`.
                    # So the prefix is the parent.
                    # We can visualize this as a tree if we want?
                    
                    # For a simple list: group by top-most prefix?
                    pass
            
            # Simplified Grouping:
            # If we saw this block_id before, skip structure check (optimization)
            # But properties inside might change/appear? usually static.
            
            # For each property:
            for prop_name, val in props.items():
                if isinstance(val, list):
                    # Vector
                    for i, v in enumerate(val):
                        key = (block_id, prop_name, i)
                        self._process_value(key, v, t, structure_changed=False) # Structure check handled separately?
                else:
                    # Scalar
                    key = (block_id, prop_name, None)
                    v = val
                    self._process_value(key, v, t, structure_changed=False)
        
        # Structure Check / Tree Update
        # Doing this per-frame is expensive. 
        # Optimization: Only run structure update if we discover NEW keys.
        self._batch_process_structure(data)
        
        # Update Plots
        if self.isVisible():
            self._update_plot_curves()

    def _process_value(self, key, value, t, structure_changed):
        # Store Data
        if key not in self.data_history:
            self.data_history[key] = deque(maxlen=self.max_points)
            
        try:
            val_float = float(value)
        except (ValueError, TypeError):
            val_float = float('nan')
            
        self.data_history[key].append(val_float)

    def _batch_process_structure(self, data):
        new_structure_found = False
        
        for block_id, props in data.items():
            for prop_name, val in props.items():
                
                # Determine sub-indices
                sub_indices = [None]
                if isinstance(val, list):
                    sub_indices = range(len(val))
                
                for i in sub_indices:
                    key = (block_id, prop_name, i)
                    if key not in self.known_structure:
                        self.known_structure.add(key)
                        self._add_tree_item(block_id, prop_name, i)
                        new_structure_found = True
        
        if new_structure_found:
            self.var_tree.sortItems(0, Qt.SortOrder.AscendingOrder)

    def _add_tree_item(self, block_id, prop_name, sub_index):
        # Hierarchy: Vehicle (inferred) -> Block -> Property -> [Axis]
        
        # 1. Infer Vehicle / Group
        # Heuristic: The standard Vehicle naming in this Sim seems to be "GPS_..."
        # or IDs provided in XML.
        # We can try to split by the last underscore to find the Component name vs Parent ID?
        # e.g. "GPS_1_Equinoctial" -> Parent="GPS_1", Comp="Equinoctial"
        
        if "_Equinoctial" in block_id:
            vid = block_id.replace("_Equinoctial", "")
            comp = "Equinoctial"
        elif "_WGS84" in block_id:
            vid = "Environment"
            comp = "WGS84"
        elif block_id == "WGS84":
            vid = "Environment"
            comp = "WGS84"
        else:
            # Fallback: Treat whole ID as vehicle if no better guess
            # OR Check if it looks like a vehicle (Top Level)?
            # headless_runner recursion naming: parentID_childName
            # Top levels are usually just the ID.
            # So "GPS_1" is a block. "GPS_1_Equinoctial" is a child.
            
            # Let's try to parse the recursion path.
            tokens = block_id.split('_')
            # If we have "GPS_BIIR-2__(PRN_13)__2_Equinoctial", tokens are many.
            
            # General approach:
            # Root Groups: Anything that appears as a prefix to others?
            # Or just flat sorting.
            
            # Requested: Groups by Vehicle.
            # Let's assume the first part of the ID is the grouping key if it starts with "GPS"?
            if block_id.startswith("GPS"):
                # Find the component suffix if any known ones
                # We know standard components: Equinoctial, Aero, Control, Nav...
                # Actually, headless_runner construct: `f"{current_id}_{c_name}"`
                # So it appends `_Name`.
                
                # We can try to match known suffixes.
                known_suffixes = ["_Equinoctial", "_Aero", "_Control", "_Nav", "_Guidance", "_PrescribedMotion", "_State"]
                vid = block_id
                comp = "Main"
                
                for suffix in known_suffixes:
                    if block_id.endswith(suffix):
                        vid = block_id[:-len(suffix)]
                        comp = suffix.strip("_")
                        break
            else:
                 vid = "Global / Other"
                 comp = block_id

        # 2. Get/Create Vehicle Item
        if vid not in self.vehicle_items:
            v_item = QTreeWidgetItem(self.var_tree)
            v_item.setText(0, vid)
            v_item.setExpanded(False)
            self.vehicle_items[vid] = v_item
            self.block_items[vid] = {} # Nested dict for this vehicle
        
        v_node = self.vehicle_items[vid]
        
        # 3. Get/Create Component Item
        # We store comp items in a dict keyed by (vid, comp) to avoid collision?
        # self.block_items structure: { vid: { comp: Item } }
        
        if comp not in self.block_items[vid]:
            c_item = QTreeWidgetItem(v_node)
            c_item.setText(0, comp)
            self.block_items[vid][comp] = c_item
            
        c_node = self.block_items[vid][comp]
        
        # 4. Property Item
        # Display Name: prop or prop[i]
        disp_name = prop_name
        if sub_index is not None:
             axis = ["x", "y", "z", "w"][sub_index] if sub_index < 4 else str(sub_index)
             disp_name = f"{prop_name}.{axis}"
             
        p_item = QTreeWidgetItem(c_node)
        p_item.setText(0, disp_name)
        # Store key
        p_item.setData(0, Qt.ItemDataRole.UserRole, (block_id, prop_name, sub_index))
        p_item.setToolTip(0, f"{block_id}.{prop_name}")

        
    def reset_plots(self):
        self.data_history.clear()
        self.time_history.clear()
        self.graph.clear()
        self.curves.clear()
        # Do NOT clear structure (known_structure, var_tree, items) 
        # so selection persists across resets.
        
        # Reset curves for persisted selection?
        # We need to re-add curves for currently selected items but with empty data
        # Actually on_selection_changed handles curve creation.
        # Calling it effectively refreshes?
        # self.on_selection_changed()
        pass
        
    def _update_plot_curves(self):
        # Synchronize X Axis directly with time history?
        # Yes.
        times = list(self.time_history)
        if not times: return
        
        for key, curve in self.curves.items():
            if key in self.data_history:
                vals = list(self.data_history[key])
                # Ensure length matches (deque might be out of sync slightly if time appended first?)
                # Actually, we append time then values.
                # If a value key was missing in a frame (e.g. structure change), we might have fewer values.
                # Robustness: trim to min length
                
                n = min(len(times), len(vals))
                if n > 0:
                    curve.setData(times[-n:], vals[-n:])
                    
    def on_selection_changed(self):
        selected_items = self.var_tree.selectedItems()
        current_selection = set()
        
        for item in selected_items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                current_selection.add(data) # data is tuple (block_id, prop, index)
                
        # Update curves
        # Add new
        for key in current_selection:
            if key not in self.curves:
                color = self.colors[len(self.curves) % len(self.colors)]
                # Name generation
                block_id, prop, idx = key
                name = f"{block_id}.{prop}"
                if idx is not None:
                    axis = ["x", "y", "z"][idx] if idx < 3 else str(idx)
                    name += f".{axis}"
                    
                self.curves[key] = self.graph.plot(pen=color, name=name)
                
        # Remove old
        remove_keys = []
        for key in self.curves:
            if key not in current_selection:
                remove_keys.append(key)
                
        for key in remove_keys:
            self.graph.removeItem(self.curves[key])
            del self.curves[key]
            
        # Update plotted data immediately
        self._update_plot_curves()
