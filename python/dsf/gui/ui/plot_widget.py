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
        self.path_items = {} # Path string -> QTreeWidgetItem

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
            # For each property:
            for prop_name, val in props.items():
                if isinstance(val, list):
                    # Vector
                    for i, v in enumerate(val):
                        key = (block_id, prop_name, i)
                        self._process_value(key, v, t, structure_changed=False)
                else:
                    # Scalar
                    key = (block_id, prop_name, None)
                    v = val
                    self._process_value(key, v, t, structure_changed=False)
        
        # Structure Check / Tree Update
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
        # Hierarchy: Split block_id by '.' -> Segments
        # e.g. "GPS_1.Equinoctial" -> ["GPS_1", "Equinoctial"]
        
        parts = block_id.split('.')
        
        # Traverse / Build Path
        current_path = ""
        parent_item = self.var_tree # Root
        
        for part in parts:
            if current_path:
                current_path += "." + part
            else:
                current_path = part
                
            if current_path not in self.path_items:
                # Create Node
                if current_path == part:
                     # Top level: Add directly to tree (or use parent_item which is root)
                     item = QTreeWidgetItem(self.var_tree)
                else:
                     # Nested: Add to parent item
                     # Check if parent exists? It must, because we iterate parts in order.
                     # But we need the parent *item object*.
                     # Recover parent path
                     parent_path = current_path.rsplit('.', 1)[0]
                     p_node = self.path_items.get(parent_path, self.var_tree)
                     # If p_node is tree, add top level? (Covered above)
                     # Actually if p_node is QTreeWidgetItem, construct with parent.
                     if isinstance(p_node, QTreeWidget):
                         item = QTreeWidgetItem(p_node)
                     else:
                         item = QTreeWidgetItem(p_node)
                         
                item.setText(0, part)
                item.setExpanded(False) # Default collapsed
                self.path_items[current_path] = item
            
            # Update parent for next iteration
            parent_item = self.path_items[current_path]

        # Now add Property under the final block item
        disp_name = prop_name
        if sub_index is not None:
             axis = ["x", "y", "z", "w"][sub_index] if sub_index < 4 else str(sub_index)
             disp_name = f"{prop_name}.{axis}"
             
        p_item = QTreeWidgetItem(parent_item)
        p_item.setText(0, disp_name)
        # Store key
        p_item.setData(0, Qt.ItemDataRole.UserRole, (block_id, prop_name, sub_index))
        # Tooltip with full path
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
