from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

class PlotWindow(QMainWindow):
    visibilityChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Real-Time Plotting")
        self.resize(800, 600)
        
        # Use standard Window type. Tool windows can have weird hide/show behavior on some Linux WMs.
        self.setWindowFlags(Qt.WindowType.Window)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.plot_widget = None

    def set_plot_widget(self, widget):
        if self.plot_widget:
            self.layout.removeWidget(self.plot_widget)
        self.plot_widget = widget
        self.layout.addWidget(self.plot_widget)

    def hideEvent(self, event):
        self.visibilityChanged.emit(False)
        super().hideEvent(event)

    def closeEvent(self, event):
        if self.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
            event.accept()
            return
            
        # We just hide the window when the user clicks 'X'
        self.visibilityChanged.emit(False)
        self.hide()
        event.ignore()
