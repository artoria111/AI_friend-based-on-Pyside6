import sys
import yaml
from PySide6.QtWidgets import QApplication
from pet_window import ImageWindow


def load_config(config_path="config.yaml"):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 配置文件读取失败，将使用默认参数。错误：{e}")
        return {}


if __name__ == "__main__":
    app = QApplication(sys.argv)
    config = load_config("config.yaml")
    window = ImageWindow(config=config)
    window.show()

    sys.exit(app.exec())