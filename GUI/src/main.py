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
    parser.add_argument("--import-xml", help="Import DSF XML configuration")
    parser.add_argument("file", nargs="?", help="Open .dsf or .xml file")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    
    # Apply Dark Theme
    app.setStyleSheet(qdarktheme.load_stylesheet())

    window = MainWindow()
    
    # Handle CLI actions
    if args.load_lib:
        for lib in args.load_lib:
            window.load_library_file(lib)
            
    if args.import_xml:
        window.import_xml_file(args.import_xml)
    elif args.file:
        if args.file.lower().endswith(".xml"):
            window.import_xml_file(args.file)
        else:
            window.load_dsf_file(args.file)

    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
