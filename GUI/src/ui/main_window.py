import sys
from PyQt6.QtWidgets import QMainWindow, QDockWidget, QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DSF Configuration Editor")
        self.resize(1200, 800)
        
        self._setup_ui()

    def _setup_ui(self):
        # Dependencies
        from core.model_registry import ModelRegistry
        from ui.canvas import GraphScene, GraphView
        from ui.palette import PaletteWidget
        
        self.registry = ModelRegistry()

        # Central Canvas
        self.scene = GraphScene()
        self.view = GraphView(self.scene, self.registry)
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
        
        # Status Bar with Zoom
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.addPermanentWidget(QLabel("Zoom:"))
        self.status_bar.addPermanentWidget(self.zoom_slider)


        # Toolbar
        toolbar = self.addToolBar("Main")
        load_lib_action = toolbar.addAction("Load Shared Object")
        load_lib_action.triggered.connect(self._load_library)
        toolbar.addSeparator()

        # Menu Bar
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction("New", self._new_file)
        file_menu.addAction("Open...", self._open_file)
        file_menu.addAction("Save...", self._save_file)
        file_menu.addSeparator()
        file_menu.addAction("Export XML...", self._export_xml)
        file_menu.addSeparator()
        file_menu.addAction("Load Library...", self._load_library)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

    def _on_selection_changed(self):
        self.inspector_widget.set_selection(self.scene.selectedItems())

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

    def _new_file(self):
        self.scene.clear()
        self.inspector_widget.set_selection([])

    def _open_file(self):
        from PyQt6.QtWidgets import QFileDialog
        from utils.serializer import GraphSerializer
        
        path, _ = QFileDialog.getOpenFileName(self, "Open DSF Configuration", "", "DSF Files (*.dsf);;All Files (*)")
        if path:
            serializer = GraphSerializer(self.registry)
            try:
                serializer.load(self.scene, path)
                self.inspector_widget.set_selection([])
            except Exception as e:
                print(f"Error loading file: {e}")

    def _save_file(self):
        from PyQt6.QtWidgets import QFileDialog
        from utils.serializer import GraphSerializer
        
        path, _ = QFileDialog.getSaveFileName(self, "Save DSF Configuration", "", "DSF Files (*.dsf);;All Files (*)")
        if path:
            serializer = GraphSerializer(self.registry)
            try:
                serializer.save(self.scene, path)
            except Exception as e:
                print(f"Error saving file: {e}")

    def _export_xml(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from utils.xml_generator import XMLGenerator
        
        path, _ = QFileDialog.getSaveFileName(self, "Export XML", "", "XML Files (*.xml);;All Files (*)")
        if path:
            generator = XMLGenerator(self.scene)
            try:
                xml_content = generator.generate()
                with open(path, 'w') as f:
                    f.write(xml_content)
                QMessageBox.information(self, "Export Successful", "XML exported successfully.")
            except Exception as e:
                print(f"Error exporting XML: {e}")
                QMessageBox.critical(self, "Export Error", str(e))
