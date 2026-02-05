from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from ui.map_widget import MapWidget

class MapWindow(QMainWindow):
    visibilityChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("2D Ground Track")
        self.resize(800, 400)
        
        # Standard Window to avoid tool-window quirks
        self.setWindowFlags(Qt.WindowType.Window)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.map_widget = MapWidget()
        self.layout.addWidget(self.map_widget)

    def set_headers(self, headers):
        self.map_widget.set_headers(headers)

    def update_data(self, values):
        self.map_widget.update_data(values)

    def update_deep_data(self, t, data):
        self.map_widget.update_deep_data(t, data)

    def reset(self):
        self.map_widget.reset()

    def closeEvent(self, event):
        if self.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
            event.accept()
            return
            
        self.visibilityChanged.emit(False)
        self.hide()
        event.ignore()

    def showEvent(self, event):
        self.visibilityChanged.emit(True)
        super().showEvent(event)
