from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsPathItem
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath, QFont

class ConnectionItem(QGraphicsPathItem):
    def __init__(self, start_port, end_port=None):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.setZValue(-1) # Behind blocks
        self.pen = QPen(QColor("#B0B0B0"), 2)
        self.setPen(self.pen)
        self.setAcceptHoverEvents(True)
        self.update_path(start_port.scenePos(), end_port.scenePos() if end_port else start_port.scenePos())

    def hoverEnterEvent(self, event):
        self.setPen(QPen(QColor("#00A0E0"), 3))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPen(QPen(QColor("#B0B0B0"), 2))
        super().hoverLeaveEvent(event)

    def update_path(self, p1, p2):
        path = QPainterPath()
        path.moveTo(p1)
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        ctrl1 = QPointF(p1.x() + dx * 0.5, p1.y())
        ctrl2 = QPointF(p2.x() - dx * 0.5, p2.y())
        path.cubicTo(ctrl1, ctrl2, p2)
        self.setPath(path)
    
    def update_geometry(self):
        if self.start_port and self.end_port:
            self.update_path(self.start_port.scenePos(), self.end_port.scenePos())

class PortItem(QGraphicsItem):
    def __init__(self, name, port_type, is_input, parent=None):
        super().__init__(parent)
        self.name = name
        self.port_type = port_type
        self.is_input = is_input
        self.radius = 6
        self.setAcceptHoverEvents(True)
        self.brush = QBrush(QColor("#00A0E0")) # Blue lines style
        self.connections = [] # Track connected items

    def scenePos(self):
        # Center of port in scene coords
        return self.mapToScene(0, 0)
    
    def mousePressEvent(self, event):
        # Start connection
        if event.button() == Qt.MouseButton.LeftButton:
            self.scene().start_connection(self)
            event.accept()

    def boundingRect(self):
        return QRectF(-self.radius, -self.radius, 2*self.radius, 2*self.radius)

    def paint(self, painter, option, widget):
        painter.setBrush(self.brush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(-self.radius, -self.radius, 2*self.radius, 2*self.radius)

class BlockItem(QGraphicsItem):
    def __init__(self, block_def, instance_id, pos):
        super().__init__()
        self.block_def = block_def
        self.instance_id = instance_id # Unique ID in graph (e.g. "Vehicle_1")
        self.setPos(pos)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        
        self.width = 150
        self.height = 80 # Dynamic?
        self.header_height = 25
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        # Hierarchy
        self.parent_block = None
        self.child_blocks = []
        self.xml_tag = block_def.type_id.lower() # Default
        self.raw_params = {} # Text-only child nodes
        
        # Instance Parameters (Copy defaults)
        self.parameters = {p.name: p.default for p in block_def.properties}
        
        # Setup Ports
        self.inputs = []
        self.outputs = []
        self._create_ports()

    def _create_ports(self):
        y_in = self.header_height + 15
        y_out = self.header_height + 15
        
        for port in self.block_def.ports:
            if port.direction == "input":
                p = PortItem(port.name, port.type, True, self)
                p.setPos(-self.radius_offset(), y_in) # Left side
                self.inputs.append(p)
                y_in += 20
            else:
                p = PortItem(port.name, port.type, False, self)
                p.setPos(self.width + self.radius_offset(), y_out) # Right side
                self.outputs.append(p)
                y_out += 20
        
        self.height = max(self.height, max(y_in, y_out) + 10)
        self.height += 5 # padding

    def radius_offset(self):
        return 0 

    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)

    def add_input_port(self, name, port_type="signal"):
        # Check if already exists
        for p in self.inputs:
            if p.name == name: return p
        from ui.canvas import PortItem
        port = PortItem(name, port_type, True, parent=self)
        self.inputs.append(port)
        self._arrange_ports()
        return port

    def add_output_port(self, name, port_type="signal"):
        # Check if already exists
        for p in self.outputs:
            if p.name == name: return p
        from ui.canvas import PortItem
        port = PortItem(name, port_type, False, parent=self)
        self.outputs.append(port)
        self._arrange_ports()
        return port

    def _arrange_ports(self):
        # Re-distribute ports on sides
        h = self.height
        for i, port in enumerate(self.inputs):
            y = (h / (len(self.inputs) + 1)) * (i + 1)
            port.setPos(0, y)
        for i, port in enumerate(self.outputs):
            y = (h / (len(self.outputs) + 1)) * (i + 1)
            port.setPos(self.width, y)

    def paint(self, painter, option, widget):
        # Body
        r = 10
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, r, r)
        
        # Selection highlight
        if self.isSelected():
            painter.setPen(QPen(QColor("#00D0FF"), 2))
        else:
            painter.setPen(QPen(QColor("#101010"), 1))
            
        painter.setBrush(QBrush(QColor("#303030")))
        painter.drawPath(path)
        
        # Header
        header_path = QPainterPath()
        header_path.moveTo(0, self.header_height)
        header_path.lineTo(0, r)
        header_path.arcTo(0, 0, 2*r, 2*r, 180, -90)
        header_path.lineTo(self.width - r, 0)
        header_path.arcTo(self.width - 2*r, 0, 2*r, 2*r, 90, -90)
        header_path.lineTo(self.width, self.header_height)
        header_path.closeSubpath()
        painter.setBrush(QBrush(QColor("#404040")))
        painter.drawPath(header_path)
        
        # Text
        painter.setPen(QColor("#E0E0E0"))
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(10, 0, self.width-20, self.header_height), Qt.AlignmentFlag.AlignVCenter, self.block_def.type_id)
        
        # ID
        font2 = QFont("Segoe UI", 8)
        painter.setFont(font2)
        painter.setPen(QColor("#808080"))
        painter.drawText(QRectF(10, 25, self.width-20, 15), Qt.AlignmentFlag.AlignRight, self.instance_id)

        # Error state visualization
        if getattr(self, "error_state", None):
            color = QColor("#FF0000") if self.error_state == "error" else QColor("#FFA500")
            glow = QPen(color, 3)
            painter.setPen(glow)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.boundingRect().adjusted(-2,-2,2,2), 10, 10)

    def set_error(self, state):
        self.error_state = state
        self.update()

    def mousePressEvent(self, event):
        self._old_pos = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.pos() != self._old_pos:
            from core.commands import MoveBlockCommand
            main_win = self.scene().views()[0].window()
            undo_stack = getattr(main_win, "undo_stack", None)
            if undo_stack:
                # If multi-selection, we should ideally use a macro, 
                # but simple move is fine for now. 
                # Better: verify if others moved?
                undo_stack.push(MoveBlockCommand(self, self._old_pos, self.pos()))




    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update connections
            for p in self.inputs + self.outputs:
                for c in p.connections:
                    c.update_geometry()
        return super().itemChange(change, value)

class GraphScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 5000, 5000)
        self.setBackgroundBrush(QBrush(QColor("#181818")))
        self.temp_connection = None
        self.start_port = None

    def start_connection(self, port):
        self.start_port = port
        self.temp_connection = ConnectionItem(port, None)
        self.addItem(self.temp_connection)

    def mouseMoveEvent(self, event):
        if self.temp_connection:
            self.temp_connection.update_path(self.start_port.scenePos(), event.scenePos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.temp_connection:
            # Check drop target
            items = self.items(event.scenePos())
            end_port = None
            for item in items:
                if isinstance(item, PortItem) and item != self.start_port:
                    if item.is_input != self.start_port.is_input: # Basic validation
                        # Type Safety Check (Phase 2.1)
                        if item.port_type == self.start_port.port_type:
                            end_port = item
                            break
                        else:
                            print(f"Type mismatch: {self.start_port.port_type} vs {item.port_type}")
            
            if end_port:
                # Create permanent connection
                self.temp_connection.end_port = end_port
                self.temp_connection.update_geometry()
                self.start_port.connections.append(self.temp_connection)
                end_port.connections.append(self.temp_connection)
                self.temp_connection = None
            else:
                self.removeItem(self.temp_connection)
                self.temp_connection = None
                
        super().mouseReleaseEvent(event)
    
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)

class GraphView(QGraphicsView):
    def __init__(self, scene, registry):
        super().__init__(scene)
        self.registry = registry
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)
        self.setSceneRect(0, 0, 5000, 5000)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        
        main_win = self.window()
        if hasattr(main_win, "_copy_selection"):
            menu.addAction("Copy", main_win._copy_selection)
            menu.addAction("Paste", main_win._paste_selection)
            menu.addSeparator()
            menu.addAction("Delete", main_win._delete_selection)
            
        menu.exec(self.viewport().mapToGlobal(pos))


    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        block_id = event.mimeData().text()
        block_def = self.registry.get_block(block_id)
        
        if block_def:
            pos = self.mapToScene(event.position().toPoint())
            count = len([i for i in self.scene().items() if isinstance(i, BlockItem)])
            instance_id = f"{block_id}_{count+1}"
            
            block = BlockItem(block_def, instance_id, pos)
            
            # Wrap in Undo Command
            from core.commands import AddBlockCommand
            main_win = self.window()
            if hasattr(main_win, "undo_stack"):
                main_win.undo_stack.push(AddBlockCommand(self.scene(), block))
            else:
                self.scene().addItem(block)
                
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_items = self.scene().selectedItems()
            if selected_items:
                from core.commands import RemoveBlockCommand
                main_win = self.window()
                undo_stack = getattr(main_win, "undo_stack", None)
                
                # Use a macro for multiple items? Or just loop.
                # Actually QUndoStack.beginMacro() is good.
                if undo_stack:
                    undo_stack.beginMacro("Delete Selection")
                    for item in selected_items:
                        if isinstance(item, BlockItem):
                            undo_stack.push(RemoveBlockCommand(self.scene(), item))
                    undo_stack.endMacro()
                else:
                    for item in selected_items:
                        if isinstance(item, BlockItem):
                            self.scene().removeItem(item)
            event.accept()
        else:
            super().keyPressEvent(event)


    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor

        # Save the scene pos
        old_pos = self.mapToScene(event.position().toPoint())

        # Zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        
        self.scale(zoom_factor, zoom_factor)

        # Get the new position
        new_pos = self.mapToScene(event.position().toPoint())

        # Move scene to old position
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        
        # Update slider if connected (via parent main window usually, but we set it in main_window.py)
        if hasattr(self, 'zoom_slider'):
            # Convert current scale to percentage for slider
            # Handle resetTransform carefully if we used it, but here we use relative scale
            current_scale = self.transform().m11()
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(int(current_scale * 100))
            self.zoom_slider.blockSignals(False)

    def set_zoom(self, value):
        # Scale is 1.0 at value=100
        s = value / 100.0
        # resetTransform() clears translations too, which might jump the view.
        # Better: calculate required scale factor to reach target 's'
        current_s = self.transform().m11()
        if current_s > 0:
            factor = s / current_s
            self.scale(factor, factor)

