from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QScrollArea, QVBoxLayout, QLineEdit, QComboBox
from PyQt6.QtCore import Qt

from ui.canvas import BlockItem

class InspectorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_block = None
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

    def set_selection(self, items):
        new_selection = set(items)
        if new_selection == self.current_selection:
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
        header = QLabel(block.instance_id)
        header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px; color: #00A0E0;")
        self.form_layout.addRow(header)
        
        self.form_layout.addRow("Type:", QLabel(block.block_def.type_id))
        
        self.form_layout.addRow(QLabel("")) # Spacer
        self.form_layout.addRow(QLabel("Properties:"))
        
        for prop in block.block_def.properties:
            value = block.parameters.get(prop.name, prop.default)
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
