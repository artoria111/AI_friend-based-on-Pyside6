import sys
from PySide6.QtWidgets import QApplication
from pet_window import ImageWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    idle_gif = "idle.gif"
    drag_gif = "drag.gif"
    chat_gif = "chat.gif"

    window = ImageWindow(idle_gif, drag_gif, chat_gif,scale_factor=0.3)
    window.show()
    sys.exit(app.exec())