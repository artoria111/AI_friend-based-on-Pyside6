import sys
import os
if getattr(sys, 'frozen', False):
    log_file = open("pet_error.log", "w", encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = log_file

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

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    base_dir = get_base_path()
    os.chdir(base_dir)
    config_path = os.path.join(base_dir, "config.yaml")
    config=load_config(config_path)
    window = ImageWindow(config=config)
    window.show()

    sys.exit(app.exec())