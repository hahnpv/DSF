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
        
        from PyQt6.QtWidgets import QStatusBar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.sim_config = {
            "dt": 0.1,
            "tmax": 100.0,
            "lib_path": ""
        }

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
        self.inspector_widget.sim_config = self.sim_config
        self.inspector_dock.setWidget(self.inspector_widget)
        self.inspector_dock.setWidget(self.inspector_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
        
        # Plot Dock (Bottom)
        from ui.plot_widget import PlotWidget
        self.plot_dock = QDockWidget("Real-Time Plotting", self)
        self.plot_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.plot_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | 
                                   QDockWidget.DockWidgetFeature.DockWidgetMovable | 
                                   QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.plot_widget = PlotWidget()
        self.plot_dock.setWidget(self.plot_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.plot_dock)
        self.plot_dock.hide() # Start hidden
        
        # Simulation Settings Labels (Permanent in Status Bar)
        self.sim_info_label = QLabel(f"dt: {self.sim_config['dt']} | tmax: {self.sim_config['tmax']}")
        self.sim_info_label.setStyleSheet("margin-right: 20px; color: #888;")
        self.status_bar.addPermanentWidget(self.sim_info_label)

        # Force initial inspector view
        self.inspector_widget.set_selection([])
        self.scene.selectionChanged.connect(self._on_selection_changed)

        # Zoom Slider
        from PyQt6.QtWidgets import QSlider, QHBoxLayout
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.valueChanged.connect(self.view.set_zoom)
        self.view.zoom_slider = self.zoom_slider # For bidirectional sync
        
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

        # Simulation State
        self.sim_worker = None

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
        view_menu.addAction(self.plot_dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction("Auto Layout", self._trigger_auto_layout)

    def _trigger_auto_layout(self):
        self.undo_stack.beginMacro("Auto Layout (Nested)")
        
        # 1. Reset Hierarchy (flatten to safe state before re-parenting?)
        # Actually QGraphicsItem reparenting handles scene removal/add automatically.
        
        # Find Roots (Blocks with no parent_block determined by data, OR defined by hierarchy)
        # Note: 'parent_block' attribute is set during import.
        # We need to trust it.
        
        blocks = [i for i in self.scene.items() if isinstance(i, BlockItem)]
        roots = [b for b in blocks if b.parent_block is None]
        
        # Helper to layout a node and its children
        def layout_node_recursive(node):
            # 1. Layout Children First (Bottom-Up)
            if not node.child_blocks:
                # Leaf node: Standard size
                node.set_visual_size(150, node.height) # Reset to default-ish?
                return 150, node.height
                
            # Has children. Layout them in a grid/flow.
            # But wait, children might be containers too.
            
            child_bboxes = []
            for child in node.child_blocks:
                w, h = layout_node_recursive(child)
                child_bboxes.append((child, w, h))
                
            # Grid Layout for children
            import math
            n = len(child_bboxes)
            cols = max(1, round(math.sqrt(n * 1.5))) # slightly wider
            rows = math.ceil(n / cols)
            
            padding = 40
            header_h = node.header_height + 20
            
            current_x = padding
            current_y = header_h
            
            row_heights = [0] * rows
            col_widths = [0] * cols
            
            # First pass: calculate row/col sizes
            for i, (child, w, h) in enumerate(child_bboxes):
                r = i // cols
                c = i % cols
                row_heights[r] = max(row_heights[r], h)
                col_widths[c] = max(col_widths[c], w)
                
            # Total Size
            total_w = sum(col_widths) + (cols + 1) * padding
            total_h = sum(row_heights) + (rows + 1) * padding + header_h
            
            # Position Children
            start_y = header_h
            for r in range(rows):
                start_x = padding
                for c in range(cols):
                    idx = r * cols + c
                    if idx >= n: break
                    
                    child, cw, ch = child_bboxes[idx]
                    
                    # Center in cell
                    cell_w = col_widths[c]
                    cell_h = row_heights[r]
                    
                    off_x = (cell_w - cw) / 2
                    off_y = (cell_h - ch) / 2
                    
                    # Set Parent (Visual Nesting)
                    child.setParentItem(node) 
                    child.setPos(start_x + off_x, start_y + off_y)
                    child.setZValue(node.zValue() + 1) # Ensure on top
                    
                    start_x += col_widths[c] + padding
                start_y += row_heights[r] + padding
                
            # Resize Self
            node.set_visual_size(total_w, total_h)
            return total_w, total_h
            
        # Process Roots
        x_cursor = 0
        y_cursor = 0
        max_h = 0
        
        spacing = 100
        
        for root in roots:
            w, h = layout_node_recursive(root)
            root.setPos(x_cursor, y_cursor)
            x_cursor += w + spacing
            max_h = max(max_h, h)
            
            # Generic Grid for roots if many
            if x_cursor > 2000:
                x_cursor = 0
                y_cursor += max_h + spacing
                max_h = 0
                
        self.undo_stack.endMacro()
        
        # Fit View
        rect = self.scene.itemsBoundingRect()
        self.view.fitInView(rect.adjusted(-100, -100, 100, 100), Qt.AspectRatioMode.KeepAspectRatio)

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
            
            from core.model_registry import PropertyDefinition, PortDefinition
            
            for name in registered_names:
                # Always overwrite or create. If we have metadata, it's better than defaults.
                if True: 
                    # Fetch metadata from C++
                    try:
                        cpp_props, cpp_ports = dsf.get_block_metadata(name)
                    except Exception:
                        cpp_props, cpp_ports = ([], [])

                    # Map properties
                    py_props = []
                    for p in cpp_props:
                        # Map C++ types to GUI types
                        ptype = "string"
                        val = p.defaultValue
                        if p.type in ("double", "float", "int"):
                            ptype = "float"
                            try:
                                val = float(val)
                            except:
                                val = 0.0
                        elif p.type == "bool":
                            ptype = "bool"
                            val = (val.lower() == "true")
                        
                        py_props.append(PropertyDefinition(p.name, ptype, val, p.description))
                    
                    # Map ports
                    py_ports = []
                    for p in cpp_ports:
                        py_ports.append(PortDefinition(p.name, p.type, p.direction))

                    # Create definition
                    new_block = BlockDefinition(
                        type_id=name,
                        category=lib_name,
                        description=f"From {lib_name}",
                        properties=py_props, 
                        ports=py_ports
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
        import os
        serializer = GraphSerializer(self.registry)
        try:
            data = serializer.load_from_file(path)
            if data:
                # Preload Library if specified (CRITICAL for updating registry metadata)
                meta = data.get("metadata", {})
                lib_path = meta.get("lib_path", meta.get("library"))
                
                if lib_path and os.path.exists(lib_path):
                     # Only preload if we haven't loaded a library yet (e.g. via CLI)
                     # Or if we want to enforce the file's library?
                     # CLI override is usually preferred.
                     current_lib = self.sim_config.get("lib_path", "")
                     if not current_lib or not os.path.exists(current_lib):
                         print(f"Preloading library from DSF: {lib_path}")
                         self.load_library_file(lib_path)
                     else:
                         print(f"Using pre-loaded library (CLI override): {current_lib}")
                elif lib_path:
                     print(f"Warning: Library {lib_path} not found.")

                metadata = serializer.reconstruct(self.scene, data)
                # Don't overwrite lib_path if provided by CLI
                if self.sim_config.get("lib_path"):
                    metadata.pop("lib_path", None)
                    metadata.pop("library", None)
                    
                self.sim_config.update(metadata)
                self._refresh_sim_info()
                self.inspector_widget.set_selection([])
                
                # Center view on loaded items
                from PyQt6.QtCore import Qt
                items = [i for i in self.scene.items() if isinstance(i, BlockItem)]
                if items:
                    rect = self.scene.itemsBoundingRect()
                    self.view.setSceneRect(rect.adjusted(-2000, -2000, 2000, 2000))
                    self.view.centerOn(rect.center())
                    self.view.fitInView(rect.adjusted(-100, -100, 100, 100), Qt.AspectRatioMode.KeepAspectRatio)
                
                # Auto-wire implicit connections for legacy DSF files
                created_blocks = {item.instance_id: item for item in self.scene.items() if isinstance(item, BlockItem)}
                self._auto_wire_implicit_connections(created_blocks)

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
            print(f"DEBUG: Validation Failed with {error_count} errors:")
            for err in errors:
                if err.level == "error":
                    print(f"  - {err.block_id}: {err.message}")
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
            
            self._refresh_sim_info()
            
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
                    raw_type = b_data["type"].strip()
                    b_def = self.registry.get_block(raw_type)
                    
                    if not b_def:
                        # Aggressive Search
                        # 1. Case-insensitive
                        # 2. Namespace stripping (e.g. dsf::sim::Tank -> Tank)
                        # 3. Combined
                        
                        target_slug = raw_type.split("::")[-1].lower()
                        
                        for name in self.registry.get_all_block_names():
                            reg_slug = name.split("::")[-1].lower()
                            if reg_slug == target_slug:
                                b_def = self.registry.get_block(name)
                                print(f"DEBUG: Smart-matched '{raw_type}' -> '{name}'")
                                break
                    
                    if not b_def:
                        print(f"WARNING: Count not find definition for '{raw_type}'. Creating GENERIC block (No Ports).")
                        from core.model_registry import BlockDefinition
                        b_def = BlockDefinition(type_id=raw_type, category="Imported", 
                                               description="Imported", properties=[], ports=[])
                        self.registry.add_block(b_def)
                    
                    item = BlockItem(b_def, b_data["id"], QPointF(0, 0))
                    item.xml_tag = b_data.get("tag", item.xml_tag)
                    item.parameters.update(b_data["params"])
                    item.raw_params = b_data.get("raw_params", {}).copy()
                    
                    # Set Hierarchy
                    created_blocks[b_data["id"]] = item
                    if parent_item:
                        item.parent_block = parent_item
                        parent_item.child_blocks.append(item)
                    else:
                        item.parent_block = None
                    
                    self.scene.addItem(item)
                    
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
            self._auto_wire_implicit_connections(created_blocks)


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
                            
                            # 2. strict fallback: if specific port name was requested but not found as explicit port,
                            # checking if target has it as dynamic output?
                            # Actually, if XML says "port='foo'", we expect a port named 'foo' or 'foo_id'.
                            # If connection is implicit (no port spec in XML, but inferred), it usually goes via auto-wire.
                            # But here we are processing explicit <... nav_id="S2_Nav" ...>
                            # This means "connect my 'nav' input to 'S2_Nav'".
                            # 'nav' input exists. 'S2_Nav' block exists.
                            # We need to find the Best Output on S2_Nav.
                            
                            if not start_port:
                                # Try to find an output that matches the input name?
                                # e.g. input "nav" -> output "nav"?
                                for p in target_item.outputs:
                                    if p.name == end_port.name:
                                        start_port = p
                                        break

                            # 3. Fallback: If only one output, use it (Generic)
                            if not start_port and len(target_item.outputs) == 1:
                                start_port = target_item.outputs[0]
                            
                        if not start_port:
                            # 4. Create dynamic output if none exist AND we are desperate?
                            # Better to rely on auto-wire for "smart" connections.
                            # But if XML *explicitly* requested a link, we should probably verify it exists.
                            # If we fail here, the connection is dropped.
                            pass
                        
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

            # Post-pass: Auto-wire implicit connections (e.g. StageManager finding sibling Nav/Control)
            # Only run this at the top level call to avoid recursion redundancy
            if len(created_blocks) > 0 and "sub_blocks" not in b_data: 
                # This condition is tricky inside recursion. 
                # Better to call it explicitly in import_xml_file after reconstruction.
                pass

    def _auto_wire_implicit_connections(self, created_blocks):
        from ui.canvas import ConnectionItem
        
        # Identify Potential Sources (Output Ports)
        # Store by type for quick lookup:  "NavigationBase" -> [port_item, ...]
        available_outputs = {}
        
        for block in created_blocks.values():
            for port in block.outputs:
                if port.port_type not in available_outputs:
                    available_outputs[port.port_type] = []
                available_outputs[port.port_type].append(port)
                
        # Heuristic Matching
        for block in created_blocks.values():
            for in_port in block.inputs:
                # Skip if already connected
                if len(in_port.connections) > 0:
                    continue
                
                # Check if we have candidates for this type
                candidates = available_outputs.get(in_port.port_type, [])
                if not candidates: 
                    continue
                
                # Strategy: 
                # 1. Prefer Siblings (Same Parent)
                # 2. Prefer Children (if block is a Manager)
                # 3. Prefer Cousins (Same Grandparent)
                
                best_match = None
                best_score = 0 # 3=Sibling, 2=Child, 1=Cousin/Any
                
                for out_port in candidates:
                    source_block = out_port.parentItem()
                    if source_block == block: continue # Don't connect to self
                    
                    # RULE 1: Prevent Peer-to-Peer generic signal connections (e.g. Engine -> Engine)
                    if in_port.port_type == "signal" and source_block.block_def.type_id == block.block_def.type_id:
                        continue

                    score = 0
                    
                    # Check Sibling
                    if getattr(source_block, 'parent_block', None) == getattr(block, 'parent_block', None) and getattr(block, 'parent_block', None) is not None:
                        score = 3
                    # Check if Source is Child of Block
                    elif getattr(source_block, 'parent_block', None) == block:
                        score = 2
                    # Check Cousin (Parents are siblings)
                    elif (getattr(block, 'parent_block', None) and getattr(source_block, 'parent_block', None) and 
                          getattr(block.parent_block, 'parent_block', None) == getattr(source_block.parent_block, 'parent_block', None)):
                        score = 1
                    
                    # Bonus: Prioritize Avionics for signals
                    if in_port.port_type == "signal":
                        name_lower = source_block.instance_id.lower()
                        if any(x in name_lower for x in ["fsw", "control", "guidance", "nav"]):
                            score += 0.5
                    
                    if score > best_score:
                        best_score = score
                        best_match = out_port
                    
                    # Tie-breaker: Name matching?
                    # If we have multiple siblings (e.g. 2 props), which one?
                    # Start with first found compliant with C++ 'find first' logic.
                
                if best_match:
                    # Create Connection
                    conn = ConnectionItem(best_match, in_port)
                    self.scene.addItem(conn)
                    best_match.connections.append(conn)
                    in_port.connections.append(conn)
                    print(f"Auto-Wired {block.instance_id}:{in_port.name} -> {best_match.parentItem().instance_id}:{best_match.name}")



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


    def _refresh_sim_info(self):
        """Update status bar label and inspector if showing sim settings."""
        self.sim_info_label.setText(f"dt: {self.sim_config['dt']} | tmax: {self.sim_config['tmax']}")
        if not self.scene.selectedItems():
            self.inspector_widget.set_selection([], force=True)

    def _start_simulation(self):
        # 1. Validation
        errors = self.validator.validate()
        if any(e.level == "error" for e in errors):
            # Show status bar warning? Already glowing.
            self.status_bar.showMessage("Fix errors before running!")
            print(f"Validation Failed with {sum(1 for e in errors if e.level=='error')} errors:")
            for err in errors:
                if err.level == "error":
                    print(f"  - {err.block_id}: {err.message}")
            return

        if not self.sim_config["lib_path"]:
            QMessageBox.information(self, "Load Library", "Please select the simulation library (.so) to proceed.")
            self._load_library()
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
            import traceback
            traceback.print_exc()
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
        self.sim_worker.headers_ready.connect(self.plot_widget.set_headers)
        self.sim_worker.data_ready.connect(self.plot_widget.update_data)
        
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

