from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QScrollArea, QVBoxLayout, QLineEdit, QComboBox
from PyQt6.QtCore import Qt

from ui.canvas import BlockItem

class InspectorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_block = None
        self.sim_config = None # Reference to MainWindow.sim_config
        self.current_selection = set()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Don't steal focus from children
        self.scroll_content = QWidget()
        self.form_layout = QFormLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        
        self.layout.addWidget(self.scroll)
        
        # Placeholder
        self.placeholder_label = QLabel("Select a block to view properties")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.form_layout.addRow(self.placeholder_label)

    def set_selection(self, items, force=False):
        new_selection = set(items)
        if not force and new_selection == self.current_selection:
            return
        
        self.current_selection = new_selection
        
        # Clear layout
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        blocks = [i for i in items if isinstance(i, BlockItem)]
        
        if not blocks:
            self.current_block = None
            if self.sim_config:
                self._show_sim_settings()
            else:
                self.form_layout.addRow(QLabel("No Selection"))
            return
            
        if len(blocks) > 1:
            self.current_block = None
            self.form_layout.addRow(QLabel(f"{len(blocks)} items selected"))
            return
            
        self.current_block = blocks[0]
        self._show_block_properties(self.current_block)
    def _show_block_properties(self, block):
        # Header
        header = QLabel(f"Block: {block.instance_id}")
        header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px; color: #00A0E0;")
        self.form_layout.addRow(header)
        # ...

    def _show_sim_settings(self):
        header = QLabel("Simulation Settings")
        header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px; color: #FFA500;")
        self.form_layout.addRow(header)
        
        # dt
        dt_edit = QLineEdit(str(self.sim_config["dt"]))
        dt_edit.editingFinished.connect(lambda: self._on_sim_val_changed("dt", dt_edit))
        self.form_layout.addRow("Timestep (dt):", dt_edit)
        
        # tmax
        tmax_edit = QLineEdit(str(self.sim_config["tmax"]))
        tmax_edit.editingFinished.connect(lambda: self._on_sim_val_changed("tmax", tmax_edit))
        self.form_layout.addRow("Max Time (tmax):", tmax_edit)
        
        # lib
        lib_edit = QLineEdit(self.sim_config["lib_path"])
        lib_edit.editingFinished.connect(lambda: self._on_sim_val_changed("lib_path", lib_edit))
        self.form_layout.addRow("Library Path:", lib_edit)
        
        hint = QLabel("\n(Click Start to apply changes)")
        hint.setStyleSheet("font-style: italic; color: #808080; font-size: 10px;")
        self.form_layout.addRow(hint)

    def _on_sim_val_changed(self, key, editor):
        if not self.sim_config: return
        text = editor.text()
        try:
            if key in ("dt", "tmax"):
                val = float(text)
                self.sim_config[key] = val
            else:
                self.sim_config[key] = text
            print(f"Updated global {key} = {self.sim_config[key]}")
            
            # Notify MainWindow to update status bar
            main_window = self.window()
            if hasattr(main_window, "_refresh_sim_info"):
                # We only want to update the LABEL, not re-set the selection 
                # (which would cause infinite loop or lose focus)
                main_window.sim_info_label.setText(f"dt: {self.sim_config['dt']} | tmax: {self.sim_config['tmax']}")
                
        except ValueError:
            editor.setText(str(self.sim_config[key]))

    def _show_block_properties(self, block):
        print(f"DEBUG INSPECTOR: Showing properties for {block.instance_id} (Type: {block.block_def.type_id})")
        # Header
        header = QLabel(block.instance_id)
        header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px; color: #00A0E0;")
        self.form_layout.addRow(header)
        
        self.form_layout.addRow("Type:", QLabel(block.block_def.type_id))
        
        self.form_layout.addRow(QLabel("")) # Spacer
        self.form_layout.addRow(QLabel("Properties:"))
        
        props = block.block_def.properties
        print(f"DEBUG INSPECTOR: Found {len(props)} properties definition.")
        
        for prop in props:
            value = block.parameters.get(prop.name, prop.default)
            print(f"  - Prop: {prop.name}, Val: {value}")
            editor = self._create_editor(prop, value)
            self.form_layout.addRow(prop.name + ":", editor)

    def _create_editor(self, prop_def, current_value):
        if prop_def.options:
            editor = QComboBox()
            editor.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            editor.addItems(prop_def.options)
            if current_value in prop_def.options:
                editor.setCurrentText(str(current_value))
            # Use activated to only trigger when user specifically picks an item
            editor.activated.connect(lambda i, p=prop_def.name: self._on_property_changed(p, editor.itemText(i)))
            return editor
        
        # Default to LineEdit
        editor = QLineEdit()
        editor.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if prop_def.type == "vec3":
            if isinstance(current_value, list):
                editor.setText(", ".join(map(str, current_value)))
            else:
                editor.setText(str(current_value))
        else:
            editor.setText(str(current_value))
            
        # Update immediately on text change? No, safer on editingFinished
        editor.editingFinished.connect(lambda p=prop_def.name, e=editor, t=prop_def.type: self._on_text_property_changed(p, e, t))
        return editor

    def _on_property_changed(self, prop_name, value):
        if self.current_block:
            self.current_block.parameters[prop_name] = value
            print(f"Updated {self.current_block.instance_id}.{prop_name} = {value}")

    def _on_text_property_changed(self, prop_name, editor, prop_type):
        if not self.current_block:
            return
            
        text = editor.text()
        try:
            if prop_type == "float":
                value = float(text)
            elif prop_type == "bool":
                value = text.lower() in ("true", "1", "yes")
            elif prop_type == "vec3":
                # Parse "1, 2, 3"
                parts = text.split(",")
                value = [float(p.strip()) for p in parts]
                if len(value) != 3:
                    raise ValueError("Vec3 requires 3 components")
            else:
                value = text # string
                
            self.current_block.parameters[prop_name] = value
            print(f"Updated {self.current_block.instance_id}.{prop_name} = {value}")
        except ValueError as e:
            # Revert or show error? For MVP just log and reset text?
            print(f"Invalid value for {prop_name}: {e}")
            # Reset text to current stored value
            current_val = self.current_block.parameters.get(prop_name, "")
            if isinstance(current_val, list):
                editor.setText(", ".join(map(str, current_val)))
            else:
                editor.setText(str(current_val))
