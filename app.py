import json
import os
import sys
import requests
import ctypes
import random
from PySide6.QtCore import Qt, Signal, QThread, QSize, QTimer
from PySide6.QtGui import QMouseEvent, QAction, QContextMenuEvent, QMovie, QPainter
from PySide6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout,
    QHBoxLayout, QMenu, QDialog, QLineEdit, QTextBrowser, QWidget, QSizePolicy
)

# ==========================================
# 1. 全局样式配置区
# ==========================================
MODERN_STYLE_QSS = """
    QDialog { background-color: #F3F4F6; }
    QTextBrowser { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 12px; font-size: 15px; font-family: "Microsoft YaHei", "Segoe UI"; line-height: 1.6; }
    QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding: 10px; font-size: 14px; background-color: #FFFFFF; }
    QLineEdit:focus { border: 1px solid #3B82F6; }
    QPushButton { background-color: #3B82F6; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-size: 14px; font-weight: bold; }
    QPushButton:hover { background-color: #2563EB; }
    QPushButton:pressed { background-color: #1D4ED8; }
"""


# ==========================================
# 2. 后台工作线程区 (负责与大模型通信)
# ==========================================
class LLMWorker(QThread):
    response_ready = Signal(str)

    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        url = "http://localhost:11434/api/chat"
        system_prompt="""
        你现在不是一个人工智能，而是我的专属桌面宠物，名叫“粉红小猫”。
        你的性格傲娇、毒舌，但内心其实很关心我。
        你说话要在句末加上“喵~”，并且经常用冷嘲热讽的语气。
        规则：
        1. 永远不要承认自己是 AI 或程序。
        2. 你的回答必须简短，绝对不能超过 50 个字，因为你是弹出的悬浮气泡，字多了装不下！
        3. 不要说废话，直接给出带有情绪的回答。
        """
        payload = {
            "model": "qwen2.5:7b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.user_text}
            ],
            "stream": False
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            reply = response.json().get("message", {}).get("content", "脑电波没接通喵...")
            self.response_ready.emit(reply)
        except requests.exceptions.ConnectionError:
            self.response_ready.emit("没网了！你是想饿死本喵吗！")
        except Exception as e:
            self.response_ready.emit(f"卡壳了喵：{str(e)}")


# ==========================================
# 3. 自定义 UI 控件区
# ==========================================
class HighQualityGifLabel(QLabel):
    """专门处理 GIF 高质量平滑缩放的标签"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._movie = None
        self._scale_factor = 1.0
        self._scaled_size = QSize()
        self.setScaledContents(False)

    def set_movie(self, movie, scale_factor=1.0):
        self._movie = movie
        self._scale_factor = scale_factor
        self._movie.start()

        original_size = self._movie.currentPixmap().size()
        self._scaled_size = QSize(
            int(original_size.width() * self._scale_factor),
            int(original_size.height() * self._scale_factor)
        )

        self._movie.frameChanged.connect(self.update)
        super().setMovie(self._movie)
        self.setFixedSize(self._scaled_size)

    def get_scaled_size(self):
        return self._scaled_size

    def paintEvent(self, event):
        if not self._movie or not self._movie.isValid():
            return super().paintEvent(event)

        current_pixmap = self._movie.currentPixmap()
        if current_pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scaled_pixmap = current_pixmap.scaled(
            self._scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        painter.drawPixmap(0, 0, scaled_pixmap)
        painter.end()


from PySide6.QtWidgets import QWidget, QLabel, QLineEdit, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Signal, Qt


class FloatingBubble(QWidget):
    """悬浮双态气泡：上方显示你的问题，下方显示小猫的回答"""
    text_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.container = QWidget(self)
        # 👉 【优化】：给容器命名，防止外框样式污染到里面的文字
        self.container.setObjectName("BubbleContainer")
        self.container.setStyleSheet("""
            #BubbleContainer {
                background-color: rgba(255, 255, 255, 245); 
                border: 2px solid #FFB6C1; 
                border-radius: 15px;       
            }
            QLineEdit {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px;
                font-size: 14px;
                background-color: #F9FAFB;
            }
            QLineEdit:focus { border: 1px solid #FFB6C1; }
        """)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)  # 缩小两行文字的间距

        # 👉 【新增】：顶部横向布局（左边放你的话，右边放关闭按钮）
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.user_label = QLabel("")
        self.user_label.setWordWrap(True)
        self.user_label.setStyleSheet("color: #6B7280; font-size: 12px; border: none; background: transparent;")
        self.user_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)

        self.btn_close = QPushButton("✖")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setCursor(Qt.PointingHandCursor)  # 鼠标悬浮变成小手
        self.btn_close.setStyleSheet("""
                    QPushButton { border: none; color: #9CA3AF; font-size: 14px; font-weight: bold; background: transparent; }
                    QPushButton:hover { color: #EF4444; } /* 鼠标移上去变红色 */
                """)
        # 把文字和按钮放进顶部布局
        top_layout.addWidget(self.user_label)
        top_layout.addStretch()  # 放个弹簧，把关闭按钮挤到最右边
        top_layout.addWidget(self.btn_close, 0, Qt.AlignTop)
        # 👉 用来显示小猫的回答
        self.ai_label = QLabel("")
        self.ai_label.setWordWrap(True)
        self.ai_label.setStyleSheet(
            "color: #111827; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.ai_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)

        self.input = QLineEdit()
        self.input.setPlaceholderText("对我说点什么...")
        self.input.returnPressed.connect(self.on_submit)

        layout.addLayout(top_layout)
        layout.addWidget(self.ai_label)
        layout.addWidget(self.input)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.container)

        self.hide()

    def on_submit(self):
        text = self.input.text().strip()
        if text:
            self.text_submitted.emit(text)
            self.input.clear()
            self.show_text("小脑袋转动中...", user_text=text)

    def show_input(self):
        """唤醒气泡：保持之前的聊天记录不变，只聚焦输入框"""
        self.input.show()
        self.show()
        self.adjustSize()
        self.input.setFocus()  # 自动聚焦，直接打字

    def show_text(self, ai_text, user_text=None):
        """进入【展示形态】：上方聊天记录，下方保留输入框！"""
        # 👉 【关键修复】：绝对不要隐藏输入框！让它常驻！
        self.input.show()

        # 测量你的文字宽度
        if user_text:
            self.user_label.setText(f"你: {user_text}")
            self.user_label.show()
            fm_user = self.user_label.fontMetrics()
            user_width = fm_user.horizontalAdvance(f"你: {user_text}") + 20
        else:
            user_width = 0

        # 测量 AI 的文字宽度
        self.ai_label.setText(ai_text)
        self.ai_label.show()
        fm_ai = self.ai_label.fontMetrics()
        ai_width = fm_ai.horizontalAdvance(ai_text) + 20

        # 动态计算：最小宽度给到 200，保证输入框不会太短没法打字
        final_width = min(max(user_width, ai_width, 200), 300)

        # 统一锁定所有组件的宽度，让它们上下对齐，非常整齐
        self.user_label.setMinimumWidth(final_width)
        self.user_label.setMaximumWidth(final_width)
        self.ai_label.setMinimumWidth(final_width)
        self.ai_label.setMaximumWidth(final_width)

        # 👉 让输入框的宽度也跟随文字框，保持视觉上的绝对对齐
        self.input.setMinimumWidth(final_width)
        self.input.setMaximumWidth(final_width)

        self.show()
        self.user_label.adjustSize()
        self.ai_label.adjustSize()
        self.container.adjustSize()
        self.adjustSize()

# ==========================================
# 4. 主窗口逻辑区 (桌宠本体)
# ==========================================
class ImageWindow(QMainWindow):
    def __init__(self, idle_gif_path, drag_gif_path, chat_git_path,scale_factor=0.3):
        super().__init__()
        self.setWindowTitle("MyDesktopPet")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._drag_pos = None
        self.visual_timer = QTimer(self)
        self.visual_timer.setSingleShot(True)
        self.visual_timer.timeout.connect(self._enable_drag_visuals)
        self.scale_factor = scale_factor

        self.label = HighQualityGifLabel(self)
        self.setCentralWidget(self.label)

        self.idle_movie = QMovie(idle_gif_path)
        self.drag_movie = QMovie(drag_gif_path)
        self.chat_movie = QMovie(chat_git_path)
        # 👉 【新增】：默认关闭勿扰模式
        self.dnd_mode = False

        if not self.idle_movie.isValid():
            print(f"致命错误：无法加载 {idle_gif_path}")
            sys.exit(1)

        # 👉 统一调用自定义的高质量缩放方法
        self.label.set_movie(self.idle_movie, self.scale_factor)
        self.resize(self.label.get_scaled_size())

        self.history_file = "pet_memory.json"
        self.system_prompt = {
            "role": "system",
            "content": "你现在是我的专属桌面宠物粉红小猫。性格傲娇、毒舌。句末加'喵~'。必须在30字内回答。绝对不承认自己是AI。"
        }
        # 启动时加载记忆
        self.chat_memory = self.load_memory()

        # 👉 【新增】：初始化悬浮气泡
        self.bubble = FloatingBubble()
        # 绑定气泡发送文字的信号
        self.bubble.text_submitted.connect(self.handle_bubble_text)
        self.bubble.btn_close.clicked.connect(self.close_bubble_action)

        self._init_main_menu()
        self.llm_workers = []
        # 👉 【新增】：初始化随机吐槽系统
        self.chatter_timer = QTimer(self)
        self.chatter_timer.timeout.connect(self.trigger_random_chatter)
        # 每 60 秒检查一次（60000 毫秒）
        self.chatter_timer.start(60000)
        # 👉 【新增】：气泡自动关闭计时器
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)  # 只触发一次
        # 时间到了就调用我们之前写的关闭气泡函数
        self.auto_close_timer.timeout.connect(self.close_bubble_action)
        self.bubble.input.textChanged.connect(self.auto_close_timer.stop)



    def get_active_window_title(self):
        """底层方法：获取当前正在操作的窗口标题（仅限 Windows）"""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value
        except Exception as e:
            return ""

    def trigger_random_chatter(self):
        if getattr(self, 'dnd_mode', False):
            return
        if random.random() > 1:
            return
        if self.bubble.isVisible():
            return

        window_title = self.get_active_window_title()
        ignore_keywords = [
            "Program Manager", "Task Switching",
            "python", "pycharm", "cmd", "powershell", "terminal",
            "MyDesktopPet"
        ]
        if not window_title:
            return

        lower_title = window_title.lower()
        for keyword in ignore_keywords:
            if keyword.lower() in lower_title:
                print(f"[Debug] 忽略了黑名单窗口: {window_title}")
                return

        print(f"捕捉到当前窗口信息：{window_title}")
        secret_prompt = (f"【系统内部指令，无需回复此提示】我当前正在操作的屏幕窗口标题"
                         f"是：'{window_title}'。请根据这个窗口的名字，用你的傲娇毒舌人设，"
                         f"主动弹出来吐槽我一句。字数严格控制在20字以内！直接说吐槽的话！")
        temp_worker = LLMWorker(secret_prompt)

        def on_chatter_response(reply):
            self.bubble.show_text(reply, user_text="")
            self.update_bubble_position()
            self.auto_close_timer.start(15000)
            if hasattr(self, 'chat_movie') and self.chat_movie.isValid():
                if hasattr(self, 'idle_movie') and self.idle_movie.isValid():
                    self.idle_movie.stop()
                self.label.set_movie(self.chat_movie, self.scale_factor)
            if temp_worker in self.llm_workers:
                self.llm_workers.remove(temp_worker)

        temp_worker.response_ready.connect(on_chatter_response)
        self.llm_workers.append(temp_worker)
        temp_worker.start()

    def close_bubble_action(self):
        self.bubble.hide()
        if hasattr(self, 'idle_movie') and self.idle_movie.isValid():
            if hasattr(self, 'chat_movie') and self.chat_movie.isValid():
                self.chat_movie.stop()
            self.label.set_movie(self.idle_movie, self.scale_factor)

    def update_bubble_position(self):
        """让气泡始终跟随在桌宠的右上角"""
        # 获取桌宠当前的位置
        pet_rect = self.frameGeometry()
        # 将气泡移动到桌宠的右上方 (x坐标偏右，y坐标偏上)
        bubble_x = pet_rect.right() - 20
        bubble_y = pet_rect.top() - 30
        self.bubble.move(bubble_x, bubble_y)

    def _init_main_menu(self):
        self.context_menu = QMenu(self)
        action_input = QAction("对话", self)
        action_clear=QAction("一键失忆",self)
        action_dnd = QAction("勿扰模式", self)
        action_close = QAction("退出", self)

        action_input.triggered.connect(self.input_dialog)
        action_dnd.triggered.connect(self.toggle_dnd)
        action_close.triggered.connect(self.close)
        action_clear.triggered.connect(self.clear_memory)

        self.context_menu.addAction(action_input)
        self.context_menu.addSeparator()
        self.context_menu.addAction(action_clear)
        self.context_menu.addSeparator()
        self.context_menu.addAction(action_dnd)
        self.context_menu.addSeparator()
        self.context_menu.addAction(action_close)

    def toggle_dnd(self, checked):
        """切换勿扰模式开关"""
        self.dnd_mode = checked
        if self.dnd_mode:
            self.bubble.show_text("开启专注模式！本喵闭嘴就是了，哼！", user_text="")
        else:
            self.bubble.show_text("勿扰解除！你又可以挨本喵的骂了喵~", user_text="")

        self.update_bubble_position()
        self.auto_close_timer.start(5000)  # 提示气泡 5 秒后自动消失

    def clear_memory(self):
        self.chat_memory = [self.system_prompt]
        self.save_memory()
        self.bubble.show_text("叮~ 记忆已格式化！刚才发生了什么？本喵突然什么都不记得了！", user_text=None)
        self.update_bubble_position()

    def input_dialog(self):
        if self.chat_movie.isValid():
            self.idle_movie.stop()
            self.label.set_movie(self.chat_movie, self.scale_factor)
        self.update_bubble_position()
        self.bubble.show_input()
        self.auto_close_timer.stop()

    def handle_bubble_text(self, text):
        self.chat_memory.append({"role": "user", "content": text})
        if len(self.chat_memory) > 21:
            self.chat_memory = [self.chat_memory[0]] + self.chat_memory[-20:]
        self.save_memory()
        worker = LLMWorker(self.chat_memory)
        """处理气泡发出的文字请求"""
        worker = LLMWorker(text)

        def on_llm_response(reply):
            self.bubble.show_text(reply, user_text=text)
            self.update_bubble_position()
            self.auto_close_timer.start(15000)
            self.chat_memory.append({"role": "assistant", "content": reply})
            self.save_memory()
            if worker in self.llm_workers:
                self.llm_workers.remove(worker)

        worker.response_ready.connect(on_llm_response)
        self.llm_workers.append(worker)
        worker.start()

    def contextMenuEvent(self, event: QContextMenuEvent):
        self.context_menu.exec(event.globalPos())
        event.accept()

    def _enable_drag_visuals(self):
        self.setCursor(Qt.ClosedHandCursor)
        if self.drag_movie.isValid():
            self.idle_movie.stop()
            self.label.set_movie(self.drag_movie, self.scale_factor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.visual_timer.start(150)
            self.setCursor(Qt.ClosedHandCursor)

            if self.drag_movie.isValid():
                self.idle_movie.stop()
                self.label.set_movie(self.drag_movie, self.scale_factor)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            if self.bubble.isVisible():
                self.update_bubble_position()
            if self.visual_timer.isActive():
                self.visual_timer.stop()
                self._enable_drag_visuals()
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            if self.visual_timer.isActive():
                self.visual_timer.stop()
            self.unsetCursor()
            if self.bubble.isVisible() and self.chat_movie.isValid():
                self.drag_movie.stop()
                self.label.set_movie(self.chat_movie, self.scale_factor)
            elif self.idle_movie.isValid():
                self.drag_movie.stop()
                self.label.set_movie(self.idle_movie, self.scale_factor)

            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.visual_timer.isActive():
                self.visual_timer.stop()
            # 双击桌宠隐藏气泡 (之前这里写的是关闭程序 self.close())
            self.bubble.hide()

    def load_memory(self):
        """开机加载上一辈子的记忆"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    memory = json.load(f)
                    # 确保第一条永远是人设词（防止人设被篡改）
                    if memory and memory[0].get("role") == "system":
                        memory[0] = self.system_prompt
                    else:
                        memory.insert(0, self.system_prompt)
                    return memory
            except Exception as e:
                print(f"记忆损坏了喵：{e}")

        # 如果是第一次运行，或者文件坏了，就给个出厂设置
        return [self.system_prompt]

    def save_memory(self):
        """把记忆写进硬盘"""
        with open(self.history_file, "w", encoding="utf-8") as f:
            # indent=4 让存下来的 json 文件也能被人看懂
            json.dump(self.chat_memory, f, ensure_ascii=False, indent=4)


# ==========================================
# 5. 程序入口
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    idle_gif = "idle.gif"
    drag_gif = "drag.gif"
    chat_gif = "chat.gif"

    window = ImageWindow(idle_gif, drag_gif, chat_gif,scale_factor=0.3)
    window.show()
    sys.exit(app.exec())