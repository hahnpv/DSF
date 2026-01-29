import sys
import os
import qdarktheme
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    # Ensure current dir is in path for imports if needed, 
    # though usually running as python -m or setting PYTHONPATH is better.
    # Here we assume running from GUI/src or root.
    sys.path.append(os.path.dirname(__file__))

    # Parse Args
    import argparse
    parser = argparse.ArgumentParser(description="DSF Configuration Editor")
    parser.add_argument("--load-lib", action="append", help="Load shared library (e.g. libsixdof.so)", default=[])
    parser.add_argument("file", nargs="?", help="Open .dsf file")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    
    # Apply Dark Theme
    app.setStyleSheet(qdarktheme.load_stylesheet())

    window = MainWindow()
    
    # Handle CLI actions
    if args.load_lib:
        for lib in args.load_lib:
            window.load_library_file(lib)
            
    if args.file:
        from utils.serializer import GraphSerializer
        serializer = GraphSerializer(window.registry)
        try:
            serializer.load(window.scene, args.file)
        except Exception as e:
            print(f"Error loading file {args.file}: {e}")

    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
