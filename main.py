import sys
from PyQt6.QtWidgets import QApplication
from ui.pyqt_app import ScalpApp

def main():
    app = QApplication(sys.argv)
    window = ScalpApp()
    window.showMaximized()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
