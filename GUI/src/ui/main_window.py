import sys
from PyQt6.QtWidgets import QMainWindow, QDockWidget, QLabel, QWidget, QVBoxLayout, QProgressBar, QMessageBox
from PyQt6.QtCore import Qt, QThread, QPointF
from ui.canvas import BlockItem

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DSF Configuration Editor")
        self.resize(1200, 800)
        
        from PyQt6.QtGui import QUndoStack
        self.undo_stack = QUndoStack(self)
        
        self._setup_ui()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Auto-fit if there are items and the window is actually visible/sized
        if hasattr(self, "scene") and self.scene.items():
            rect = self.scene.itemsBoundingRect()
            if not rect.isEmpty():
                self.view.fitInView(rect.adjusted(-50, -50, 50, 50), Qt.AspectRatioMode.KeepAspectRatio)

    def _setup_ui(self):
        # Dependencies
        from core.model_registry import ModelRegistry
        from ui.canvas import GraphScene, GraphView
        from ui.palette import PaletteWidget
        from ui.inspector import InspectorWidget # Keep original InspectorWidget import
        from utils.serializer import GraphSerializer
        from core.validation_engine import ValidationEngine
        
        self.registry = ModelRegistry()
        self.scene = GraphScene()
        self.view = GraphView(self.scene, self.registry)
        self.serializer = GraphSerializer(self.registry)
        self.validator = ValidationEngine(self.scene)

        # Connect scene changes to validation
        self.scene.changed.connect(self._run_validation)

        self.setCentralWidget(self.view)

        # Palette Dock (Left)
        self.palette_dock = QDockWidget("Block Palette", self)
        self.palette_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.palette_widget = PaletteWidget(self.registry)
        self.palette_dock.setWidget(self.palette_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.palette_dock)

        # Inspector Dock (Right)
        from ui.inspector import InspectorWidget
        self.inspector_dock = QDockWidget("Property Inspector", self)
        self.inspector_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.inspector_widget = InspectorWidget()
        self.inspector_dock.setWidget(self.inspector_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
        
        # Signals
        self.scene.selectionChanged.connect(self._on_selection_changed)

        # Zoom Slider
        from PyQt6.QtWidgets import QSlider, QHBoxLayout, QStatusBar
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.valueChanged.connect(self.view.set_zoom)
        self.view.zoom_slider = self.zoom_slider # For bidirectional sync
        
        # Status Bar with Zoom & Progress
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(15)
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.status_bar.addPermanentWidget(QLabel("Zoom:"))
        self.status_bar.addPermanentWidget(self.zoom_slider)

        # Toolbar
        toolbar = self.addToolBar("Main")
        load_lib_action = toolbar.addAction("Load Shared Object")
        load_lib_action.triggered.connect(self._load_library)
        toolbar.addSeparator()

        # Simulation Toolbar
        sim_toolbar = self.addToolBar("Simulation")
        self.start_action = sim_toolbar.addAction("▶ Start")
        self.start_action.setToolTip("Start simulation with current settings")
        self.start_action.triggered.connect(self._start_simulation)
        
        self.stop_action = sim_toolbar.addAction("⏹ Stop")
        self.stop_action.setToolTip("Stop running simulation")
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(self._stop_simulation)
        
        sim_toolbar.addSeparator()
        self.sim_settings_action = sim_toolbar.addAction("⚙ Settings")
        self.sim_settings_action.setToolTip("Configure dt, tmax, and library path")
        self.sim_settings_action.triggered.connect(self._show_simulation_settings)

        # Simulation State
        self.sim_worker = None
        self.sim_config = {
            "dt": 0.1,
            "tmax": 100.0,
            "lib_path": ""
        }

        # Menu Bar
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction("New", self._new_file)
        file_menu.addAction("Open...", self._open_file)
        file_menu.addAction("Save...", self._save_file)
        file_menu.addSeparator()
        file_menu.addAction("Export XML...", self._export_xml)
        file_menu.addAction("Import XML...", self._import_xml)
        file_menu.addSeparator()
        file_menu.addAction("Load Library...", self._load_library)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        # Edit Menu
        edit_menu = menu.addMenu("&Edit")
        undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        undo_action.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_action)
        
        redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        redo_action.setShortcut("Ctrl+Y")
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        edit_menu.addAction("Copy", "Ctrl+C", self._copy_selection)
        edit_menu.addAction("Paste", "Ctrl+V", self._paste_selection)
        edit_menu.addAction("Delete", "Delete", self._delete_selection)

        view_menu = menu.addMenu("&View")
        view_menu.addAction(self.palette_dock.toggleViewAction())
        view_menu.addAction(self.inspector_dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction("Auto Layout", self._trigger_auto_layout)

    def _trigger_auto_layout(self):
        import math
        
        blocks = [i for i in self.scene.items() if isinstance(i, BlockItem)]
        if not blocks: return
        
        self.undo_stack.beginMacro("Auto Layout")
        
        # Sort blocks to maintain some order (e.g., by ID)
        blocks.sort(key=lambda x: x.instance_id)
        
        n = len(blocks)
        view_rect = self.view.viewport().rect()
        aspect = view_rect.width() / max(1, view_rect.height())
        
        cols = max(1, round(math.sqrt(aspect * n)))
        rows = math.ceil(n / cols)
        
        spacing_x = 300
        spacing_y = 250
        
        for i, block in enumerate(blocks):
            r = i // cols
            c = i % cols
            # Check if block moved to record for undo
            old_pos = block.pos()
            new_pos = QPointF(c * spacing_x, r * spacing_y)
            if old_pos != new_pos:
                block.setPos(new_pos)
                # Note: For full undo support, we should use MoveBlockCommand, 
                # but for a mass layout, a macro with direct setPos is simpler for now 
                # as long as we don't need to undo each individual move separately.
        
        self.undo_stack.endMacro()
        
        # Fit view
        rect = self.scene.itemsBoundingRect()
        self.view.fitInView(rect.adjusted(-50, -50, 50, 50), Qt.AspectRatioMode.KeepAspectRatio)

    def _on_selection_changed(self):
        # Prevent crash on shutdown if scene is already deleted
        try:
            items = self.scene.selectedItems()
            self.inspector_widget.set_selection(items)
        except RuntimeError:
            pass

    def _load_library(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Load Shared Library", "", "Shared Libraries (*.so *.dll);;All Files (*)")
        if path:
            self.load_library_file(path)

    def load_library_file(self, path):
        from PyQt6.QtWidgets import QMessageBox
        import sys
        import os
        import ctypes
        
        # Helper to find build dir for dsf binding
        # Assuming we are in GUI/src/ui/main_window.py
        # Path to navigate: ui -> src -> GUI -> Root -> build
        build_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../build"))
        if build_path not in sys.path:
            sys.path.append(build_path)
            
        try:
            # Load library
            # Must set RTLD_GLOBAL for singletons
            sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)
            ctypes.CDLL(path, mode=os.RTLD_GLOBAL | os.RTLD_LAZY)
            
            # Update simulation config with the loaded library path
            self.sim_config["lib_path"] = os.path.abspath(path)
            
            # Import dsf binding to check registration
            import dsf
            registered_names = dsf.get_registered_blocks()
            
            # Add to registry
            from core.model_registry import BlockDefinition
            
            count = 0
            # Identify library name for grouping
            lib_name = os.path.basename(path)
            
            for name in registered_names:
                if not self.registry.get_block(name):
                    # Create generic definition
                    # Group by Library Name as "Inheritance/Grouping" is not available in C++ factory
                    new_block = BlockDefinition(
                        type_id=name,
                        category=lib_name, # Group by SO name
                        description=f"From {lib_name}",
                        properties=[], 
                        ports=[]
                    )
                    self.registry.add_block(new_block)
                    count += 1
            
            if count > 0:
                # Refresh palette
                self.palette_widget._populate() 
                print(f"Loaded {count} blocks from {lib_name}")
                # Only show msg box if window is visible (not purely CLI) - check implementation context? 
                # For now keep it simple, main loop handles events.
            else:
                print(f"Library {lib_name} loaded but no new blocks found.")

        except Exception as e:
            print(f"Error loading library {path}: {e}")
            QMessageBox.critical(self, "Load Error", str(e))

    def load_dsf_file(self, path):
        """Helper to load a DSF project with full UI state restoration."""
        from utils.serializer import GraphSerializer
        serializer = GraphSerializer(self.registry)
        try:
            data = serializer.load_from_file(path)
            if data:
                metadata = serializer.reconstruct(self.scene, data)
                self.sim_config.update(metadata)
                self.inspector_widget.set_selection([])
                
                # Center view on loaded items
                from PyQt6.QtCore import Qt
                items = [i for i in self.scene.items() if isinstance(i, BlockItem)]
                if items:
                    rect = self.scene.itemsBoundingRect()
                    self.view.setSceneRect(rect.adjusted(-2000, -2000, 2000, 2000))
                    self.view.centerOn(rect.center())
                    self.view.fitInView(rect.adjusted(-100, -100, 100, 100), Qt.AspectRatioMode.KeepAspectRatio)
                
                self.status_bar.showMessage(f"Loaded {path}")
                return True
        except Exception as e:
            print(f"Error loading DSF: {e}")
            self.status_bar.showMessage(f"Error loading: {e}")
            QMessageBox.critical(self, "Load Error", f"Failed to load project: {e}")
        return False

    def _new_file(self):
        self.scene.clear()
        self.inspector_widget.set_selection([])

    def _open_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Open DSF Configuration", "", "DSF Files (*.dsf);;All Files (*)")
        if path:
            self.load_dsf_file(path)

    def _save_file(self):
        from PyQt6.QtWidgets import QFileDialog
        from utils.serializer import GraphSerializer
        
        path, _ = QFileDialog.getSaveFileName(self, "Save DSF Configuration", "", "DSF Files (*.dsf);;All Files (*)")
        if path:
            if not path.endswith(".dsf"):
                path += ".dsf"
            serializer = GraphSerializer(self.registry)
            try:
                serializer.save(self.scene, path, self.sim_config)
                self.status_bar.showMessage(f"Saved {path}")
            except Exception as e:
                print(f"Error saving file: {e}")

    def _export_xml(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from utils.xml_generator import XMLGenerator
        
        path, _ = QFileDialog.getSaveFileName(self, "Export XML", "", "XML Files (*.xml);;All Files (*)")
        if path:
            if not path.endswith(".xml"):
                path += ".xml"
            generator = XMLGenerator(self.scene)
            try:
                xml_content = generator.generate(
                    dt=self.sim_config["dt"],
                    tmax=self.sim_config["tmax"],
                    library=self.sim_config["lib_path"]
                )
                with open(path, 'w') as f:
                    f.write(xml_content)
                self.status_bar.showMessage(f"Exported XML to {path}")
                print(f"Exported XML to {path}")
            except Exception as e:
                print(f"Error exporting XML: {e}")
                QMessageBox.critical(self, "Export Error", str(e))

    def _run_validation(self):
        try:
            errors = self.validator.validate()
        except RuntimeError:
            return
        
        # Clear all block errors first
        from ui.canvas import BlockItem
        for item in self.scene.items():
            if isinstance(item, BlockItem):
                item.set_error(None)
                
        # Set new errors
        error_count = 0
        warning_count = 0
        
        for err in errors:
            # Find block
            for item in self.scene.items():
                if isinstance(item, BlockItem) and item.instance_id == err.block_id:
                    # Upgrade from warning to error if already set? No, error wins.
                    current = getattr(item, "error_state", None)
                    if current != "error":
                        item.set_error(err.level)
            
            if err.level == "error": error_count += 1
            else: warning_count += 1
            
        # Update Status Bar
        msg = "Validation: "
        if error_count == 0 and warning_count == 0:
            msg += "OK"
        else:
            msg += f"{error_count} Errors, {warning_count} Warnings"
        self.statusBar().showMessage(msg)

    def _import_xml(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Import XML", "", "XML Files (*.xml);;All Files (*)")
        if path:
            self.import_xml_file(path)

    def import_xml_file(self, path):
        import os
        from PyQt6.QtWidgets import QMessageBox
        from utils.xml_parser import XMLParser
        from ui.canvas import BlockItem
        from PyQt6.QtCore import QPointF, Qt
        
        parser = XMLParser(self.registry)
        try:
            parsed_data = parser.parse_file(path)
            blocks_data = parsed_data["blocks"]
            sim_metadata = parsed_data["sim_metadata"]

            # Apply simulation settings if present
            if "dt" in sim_metadata: self.sim_config["dt"] = sim_metadata["dt"]
            if "tmax" in sim_metadata: self.sim_config["tmax"] = sim_metadata["tmax"]
            if "library" in sim_metadata: self.sim_config["lib_path"] = sim_metadata["library"]
            
            self.undo_stack.beginMacro(f"Import {os.path.basename(path)}")
            self.scene.clear()
            
            # Reconstruction logic
            created_blocks = {} # id -> BlockItem
            
            def layout_subtree(data_list, x_start, y_start, parent_item=None):
                """Lays out a list of siblings in a grid and recursively handles children below them."""
                if not data_list:
                    return 0, 0 # width, height
                
                import math
                n = len(data_list)
                # Compute aspect ratio of the available view space
                view_rect = self.view.viewport().rect()
                aspect = view_rect.width() / max(1, view_rect.height())
                
                # Target aspect ratio for subgrids
                cols = max(1, round(math.sqrt(aspect * n)))
                rows = math.ceil(n / cols)
                
                row_heights = [0] * rows
                col_widths = [0] * cols
                
                # First pass: Create blocks and measure their immediate subtrees
                grid_items = [] # list of (item, [child_blocks], subtree_w, subtree_h)
                
                for i, b_data in enumerate(data_list):
                    b_def = self.registry.get_block(b_data["type"])
                    if not b_def:
                        for name in self.registry.get_all_block_names():
                            if name.lower() == b_data["type"].lower():
                                b_def = self.registry.get_block(name)
                                break
                    if not b_def:
                        from core.model_registry import BlockDefinition
                        b_def = BlockDefinition(type_id=b_data["type"], category="Imported", 
                                               description="Imported", properties=[], ports=[])
                        self.registry.add_block(b_def)
                    
                    item = BlockItem(b_def, b_data["id"], QPointF(0, 0))
                    item.xml_tag = b_data.get("tag", item.xml_tag)
                    item.parameters.update(b_data["params"])
                    item.raw_params = b_data.get("raw_params", {}).copy()
                    
                    # Set Hierarchy
                    if parent_item:
                        item.parent_block = parent_item
                        parent_item.child_blocks.append(item)
                    
                    self.scene.addItem(item)
                    created_blocks[b_data["id"]] = item
                    if parent_item:
                        print(f"DEBUG: Setting {item.instance_id} parent to {parent_item.instance_id}")
                    else:
                        print(f"DEBUG: {item.instance_id} is a ROOT")
                    
                    sub_blocks = b_data.get("sub_blocks", [])
                    grid_items.append({
                        "item": item,
                        "sub_blocks": sub_blocks,
                        "w": item.width + 100,
                        "h": item.height + 150
                    })

                # Second pass: Arrange in grid
                current_y = y_start
                max_subtree_h_at_bottom = 0
                
                total_w = 0
                total_h = 0

                for r in range(rows):
                    row_max_h = 0
                    row_x = x_start
                    for c in range(cols):
                        idx = r * cols + c
                        if idx >= n: break
                        
                        entry = grid_items[idx]
                        item = entry["item"]
                        
                        # Position parent
                        item.setPos(row_x, current_y)
                        
                        # Layout subtrees below current parent
                        # Subtrees start at current_y + item.height + spacing
                        sub_w, sub_h = layout_subtree(entry["sub_blocks"], row_x, current_y + item.height + 60, parent_item=item)
                        
                        entry["total_w"] = max(entry["w"], sub_w)
                        entry["total_h"] = entry["h"] + sub_h
                        
                        row_x += entry["total_w"]
                        row_max_h = max(row_max_h, entry["total_h"])
                    
                    total_w = max(total_w, row_x - x_start)
                    current_y += row_max_h
                    total_h = current_y - y_start

                return total_w, total_h

            layout_subtree(blocks_data, 0, 0)
            
            # Reconstruct connections
            self._reconstruct_connections(blocks_data, created_blocks)


            self.undo_stack.endMacro()
            
            # Center view and zoom out slightly to see all
            if created_blocks:
                rect = self.scene.itemsBoundingRect()
                self.view.setSceneRect(rect.adjusted(-1000, -1000, 1000, 1000))
                self.view.centerOn(rect.center())
                self.view.fitInView(rect.adjusted(-50, -50, 50, 50), Qt.AspectRatioMode.KeepAspectRatio)
                
            print(f"Successfully imported {len(created_blocks)} blocks from {path}")
            
        except Exception as e:
            print(f"Error importing XML: {e}")
            if hasattr(self, "show") and self.isVisible():
                QMessageBox.critical(self, "Import Error", str(e))

    def _reconstruct_connections(self, data_list, created_blocks):
        from ui.canvas import ConnectionItem
        for b_data in data_list:
            if b_data["id"] in created_blocks:
                block_item = created_blocks[b_data["id"]]
                for conn_info in b_data.get("connections", []):
                    target_id = conn_info["target"]
                    if target_id in created_blocks:
                        target_item = created_blocks[target_id]
                        
                        # Find ports
                        # End port is an input on block_item
                        end_port = None
                        target_port_name = conn_info["port"]
                        
                        # Try exact match or with _id suffix
                        for p in block_item.inputs:
                            if p.name == target_port_name or p.name == f"{target_port_name}_id":
                                end_port = p
                                break
                        
                        # Dynamic creation if really needed
                        if not end_port:
                            # Use 'signal' as default if we can't infer better
                            end_port = block_item.add_input_port(target_port_name, "signal")
                        
                        # Start port is an output on target_item
                        start_port = None
                        if target_item.outputs:
                            # 1. Try to match by type if we have multiple
                            for p in target_item.outputs:
                                if p.port_type == end_port.port_type:
                                    start_port = p
                                    break
                            
                            # 2. Specialized mappings for known mission blocks
                            if not start_port:
                                name_lower = end_port.name.lower()
                                if "tank" in name_lower:
                                    # Link engines to fuel/ox tanks
                                    for p in target_item.outputs:
                                        if "flow" in p.port_type.lower() or "tank" in p.name.lower():
                                            start_port = p
                                            break
                                elif "nav" in name_lower or "guid" in name_lower or "ctrl" in name_lower:
                                    # Link avionics layers together
                                    if target_item.outputs:
                                        start_port = target_item.outputs[0]
                            
                            # 3. Fallback: If only one output, or no type match, use the first one
                            if not start_port and len(target_item.outputs) == 1:
                                start_port = target_item.outputs[0]
                            
                        if not start_port:
                            # 4. Create dynamic output if none exist
                            start_type = end_port.port_type if end_port.port_type != "signal" else "signal"
                            start_port = target_item.add_output_port("out", start_type)
                        
                        if start_port and end_port:
                            # Prevent duplicate connections
                            already_connected = False
                            for c in start_port.connections:
                                if c.end_port == end_port:
                                    already_connected = True
                                    break
                            
                            if not already_connected:
                                conn = ConnectionItem(start_port, end_port)
                                self.scene.addItem(conn)
                                start_port.connections.append(conn)
                                end_port.connections.append(conn)
            
            if "sub_blocks" in b_data:
                self._reconstruct_connections(b_data["sub_blocks"], created_blocks)



    def _delete_selection(self):
        # Trigger delete by sending key event to view or just calling logic
        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtGui import QKeyEvent
        key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
        self.view.keyPressEvent(key_event)

    def _copy_selection(self):
        from ui.canvas import BlockItem
        items = self.scene.selectedItems()
        blocks = [i for i in items if isinstance(i, BlockItem)]
        if not blocks:
            return
            
        import json
        data = []
        for b in blocks:
            data.append({
                "type": b.block_def.type_id,
                "parameters": b.parameters
            })
        
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(json.dumps(data))

    def _paste_selection(self):
        from PyQt6.QtWidgets import QApplication
        import json
        text = QApplication.clipboard().text()
        try:
            data = json.loads(text)
            if not isinstance(data, list): return
            
            from core.commands import AddBlockCommand
            from ui.canvas import BlockItem
            from PyQt6.QtCore import QPointF
            
            self.undo_stack.beginMacro("Paste")
            for b_data in data:
                b_def = self.registry.get_block(b_data["type"])
                if b_def:
                    # offset from mouse or original? Let's just offset slightly from center
                    pos = self.view.mapToScene(self.view.viewport().rect().center())
                    pos += QPointF(20, 20)
                    
                    # unique id
                    count = len([i for i in self.scene.items() if isinstance(i, BlockItem)])
                    instance_id = f"{b_data['type']}_{count+1}"
                    
                    block = BlockItem(b_def, instance_id, pos)
                    block.parameters = b_data["parameters"].copy()
                    
                    self.undo_stack.push(AddBlockCommand(self.scene, block))
            self.undo_stack.endMacro()
        except Exception:
            pass

    def _show_simulation_settings(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDoubleSpinBox, QLineEdit, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle("Simulation Settings")
        layout = QFormLayout(dialog)
        
        dt_spin = QDoubleSpinBox()
        dt_spin.setRange(0.001, 10.0)
        dt_spin.setValue(self.sim_config["dt"])
        dt_spin.setDecimals(3)
        
        tmax_spin = QDoubleSpinBox()
        tmax_spin.setRange(0.1, 10000.0)
        tmax_spin.setValue(self.sim_config["tmax"])
        
        lib_edit = QLineEdit(self.sim_config["lib_path"])
        
        layout.addRow("Timestep (dt):", dt_spin)
        layout.addRow("Max Time (tmax):", tmax_spin)
        layout.addRow("Library Path:", lib_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec():
            self.sim_config["dt"] = dt_spin.value()
            self.sim_config["tmax"] = tmax_spin.value()
            self.sim_config["lib_path"] = lib_edit.text()
            self.status_bar.showMessage(f"Sim settings updated: dt={self.sim_config['dt']}, tmax={self.sim_config['tmax']}")

    def _start_simulation(self):
        # 1. Validation
        errors = self.validator.validate()
        if any(e.level == "error" for e in errors):
            # Show status bar warning? Already glowing.
            self.status_bar.showMessage("Fix errors before running!")
            return

        if not self.sim_config["lib_path"]:
            QMessageBox.warning(self, "Missing Library", "Please specify the simulation library path in Settings.")
            self._show_simulation_settings()
            if not self.sim_config["lib_path"]: return

        # 2. Export tentative XML
        import tempfile
        import os
        temp_xml = os.path.join(tempfile.gettempdir(), "dsf_runtime.xml")
        debug_xml = "gui_runtime_debug.xml" # Save to workspace for comparison
        from utils.xml_generator import XMLGenerator
        generator = XMLGenerator(self.scene)
        try:
            xml_content = generator.generate(
                dt=self.sim_config["dt"], 
                tmax=self.sim_config["tmax"],
                library=self.sim_config["lib_path"]
            )
            with open(temp_xml, 'w') as f:
                f.write(xml_content)
            with open(debug_xml, 'w') as f:
                f.write(xml_content)
            print(f"Debug XML saved to {debug_xml}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate runtime XML: {e}")
            return

        # 3. Start Worker
        from execution.simulation_worker import SimulationWorker
        self.sim_worker = SimulationWorker(
            temp_xml, 
            self.sim_config["lib_path"],
            self.sim_config["dt"],
            self.sim_config["tmax"]
        )
        self.sim_worker.progress.connect(self._on_sim_progress)
        self.sim_worker.finished.connect(self._on_sim_finished)
        self.sim_worker.error.connect(self._on_sim_error)
        
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Simulation Running...")
        
        self.sim_worker.start()

    def _stop_simulation(self):
        if self.sim_worker:
            self.sim_worker.stop()
            self.status_bar.showMessage("Stopping Simulation...")
            self.stop_action.setEnabled(False)

    def _on_sim_progress(self, val):
        self.progress_bar.setValue(int(val))

    def _on_sim_finished(self, msg):
        self.status_bar.showMessage(msg)
        self.progress_bar.setVisible(False)
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        QMessageBox.information(self, "Simulation Finished", msg)

    def _on_sim_error(self, err):
        self.status_bar.showMessage("Error!")
        self.progress_bar.setVisible(False)
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        QMessageBox.critical(self, "Simulation Error", err)

