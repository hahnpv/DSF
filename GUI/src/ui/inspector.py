from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QScrollArea, QVBoxLayout
from PyQt6.QtCore import Qt

from ui.canvas import BlockItem

class InspectorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.form_layout = QFormLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        
        self.layout.addWidget(self.scroll)
        
        # Placeholder
        self.label = QLabel("Select a block to view properties")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.form_layout.addRow(self.label)

    def set_selection(self, items):
        # Clear layout
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        blocks = [i for i in items if isinstance(i, BlockItem)]
        
        if not blocks:
            self.form_layout.addRow(QLabel("No Selection"))
            return
            
        if len(blocks) > 1:
            self.form_layout.addRow(QLabel(f"{len(blocks)} items selected"))
            return
            
        block = blocks[0]
        self._show_block_properties(block)

    def _show_block_properties(self, block):
        # Header
        header = QLabel(block.instance_id)
        header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        self.form_layout.addRow(header)
        
        self.form_layout.addRow("Type:", QLabel(block.block_def.type_id))
        self.form_layout.addRow("Description:", QLabel(block.block_def.description))
        
        self.form_layout.addRow(QLabel("")) # Spacer
        self.form_layout.addRow(QLabel("Properties:"))
        
        for prop in block.block_def.properties:
            value_label = QLabel(str(prop.default))
            self.form_layout.addRow(prop.name, value_label)
