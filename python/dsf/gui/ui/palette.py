from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDrag

from dsf.gui.core.model_registry import ModelRegistry

class PaletteWidget(QTreeWidget):
    def __init__(self, registry: ModelRegistry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.setHeaderHidden(True)
        self.setIndentation(20)
        self.setDragEnabled(True)
        self._populate()

    def _populate(self):
        self.clear()
        categories = self.registry.get_categories()
        for cat in categories:
            cat_item = QTreeWidgetItem(self, [cat])
            cat_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            cat_item.setExpanded(True)
            
            blocks = self.registry.get_blocks_by_category(cat)
            for block in blocks:
                item = QTreeWidgetItem(cat_item, [block.type_id])
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)
                item.setData(0, Qt.ItemDataRole.UserRole, block.type_id)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item or not item.data(0, Qt.ItemDataRole.UserRole):
            return
            
        block_id = item.data(0, Qt.ItemDataRole.UserRole)
        
        mime = QMimeData()
        mime.setText(block_id)
        
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(supportedActions)
