from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QListWidget, QListWidgetItem, QSplitter
from PyQt6.QtCore import Qt, pyqtSlot
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
        
        self.var_list = QListWidget()
        self.var_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.var_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.selection_layout.addWidget(self.var_list)
        
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
        self.max_points = 1000
        
        self.curves = {} # Key: header_index, Value: PlotDataItem
        
        # Palette for multiple lines
        # Palette for multiple lines
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w']
        
        self.persisted_selection = set() # Stores variable names

    @pyqtSlot(list)
    def set_headers(self, headers):
        print(f"PlotWidget: Received {len(headers)} headers.")
        self.headers = headers
        
        # Block signals effectively during repopulation? 
        # Actually we want signals to fire off selection logic if we select items.
        self.var_list.blockSignals(True)
        self.var_list.clear()
        
        # Populate List
        items_to_select = []
        for i, h in enumerate(headers):
            item = QListWidgetItem(h)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.var_list.addItem(item)
            
            if h in self.persisted_selection:
                item.setSelected(True)
                items_to_select.append(item)
                
        self.var_list.blockSignals(False) # Re-enable
        
        # Clear data but keep curves for selected items if possible? 
        # No, clean slate for new run.
        self.curves.clear()
        self.data_history.clear()
        self.time_history.clear()
        self.graph.clear()
        
        # Initialize history buffers
        for i in range(len(headers)):
            self.data_history[i] = deque(maxlen=self.max_points)
            
        # Trigger curve creation for persisted items
        self.refresh_curves()

    def refresh_curves(self):
        # Update plotted curves based on current selection
        selected_items = self.var_list.selectedItems()
        selected_idxs = set()
        
        # 1. Add new curves
        for item in selected_items:
            idx = item.data(Qt.ItemDataRole.UserRole)
            selected_idxs.add(idx)
            
            if idx not in self.curves:
                color = self.colors[len(self.curves) % len(self.colors)]
                # Ensure header name is valid
                name = self.headers[idx] if idx < len(self.headers) else f"Var {idx}"
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

        selected_items = self.var_list.selectedItems()
        for i, item in enumerate(selected_items):
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx not in self.curves:
                # Create curve
                color = self.colors[len(self.curves) % len(self.colors)]
                self.curves[idx] = self.graph.plot(pen=color, name=self.headers[idx])
            
            # Update data
            # Use simple numpy conversion
            self.curves[idx].setData(list(self.data_history[idx]))

    def on_selection_changed(self):
        # Update persistence
        selected_items = self.var_list.selectedItems()
        # We can't clear persistence entirely because headers might change? 
        # No, for current headers, update persistence.
        # Logic: If item is in current headers, update its status in persistence.
        
        # Actually simplest approach: 
        # 1. Remove all currently displayed headers from persistence (to handle deselection)
        current_header_names = set(self.headers)
        self.persisted_selection = self.persisted_selection - current_header_names
        
        # 2. Add currently selected items back
        for item in selected_items:
            self.persisted_selection.add(item.text())
            
        self.refresh_curves()
