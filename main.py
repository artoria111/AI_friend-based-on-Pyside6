import sys
from PySide6.QtWidgets import QApplication
from pet_window import ImageWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageWindow(scale_factor=0.3)
    window.show()
    sys.exit(app.exec())