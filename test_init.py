import sys
import os
# Mock tvDatafeed to avoid network issues and login requirement
sys.path.insert(0, os.getcwd())
import unittest
from unittest.mock import MagicMock

# Mock the TvDatafeed and other network dependencies
import tvDatafeed
tvDatafeed.TvDatafeed = MagicMock()

from PyQt6.QtWidgets import QApplication
from ui.pyqt_app import ScalpApp

def test():
    app = QApplication(sys.argv)
    try:
        window = ScalpApp()
        print("ScalpApp initialized successfully")
    except Exception as e:
        print(f"Failed to initialize ScalpApp: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test()
