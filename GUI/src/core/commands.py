from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import QPointF

class AddBlockCommand(QUndoCommand):
    def __init__(self, scene, block_item):
        super().__init__(f"Add {block_item.instance_id}")
        self.scene = scene
        self.block_item = block_item

    def redo(self):
        self.scene.addItem(self.block_item)

    def undo(self):
        self.scene.removeItem(self.block_item)

class RemoveBlockCommand(QUndoCommand):
    def __init__(self, scene, block_item):
        super().__init__(f"Remove {block_item.instance_id}")
        self.scene = scene
        self.block_item = block_item
        # Store connections to restore them
        self.connections = []
        for p in self.block_item.inputs + self.block_item.outputs:
            self.connections.extend(p.connections)

    def redo(self):
        # Remove connections first
        for conn in self.connections:
            self.scene.removeItem(conn)
        self.scene.removeItem(self.block_item)

    def undo(self):
        self.scene.addItem(self.block_item)
        # Restore connections
        for conn in self.connections:
            self.scene.addItem(conn)

class MoveBlockCommand(QUndoCommand):
    def __init__(self, block_item, old_pos, new_pos):
        super().__init__(f"Move {block_item.instance_id}")
        self.block_item = block_item
        self.old_pos = old_pos
        self.new_pos = new_pos

    def redo(self):
        self.block_item.setPos(self.new_pos)

    def undo(self):
        self.block_item.setPos(self.old_pos)
