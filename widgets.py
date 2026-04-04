from PySide6.QtWidgets import QHBoxLayout, QPushButton,QWidget, QLabel, QLineEdit, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Signal, Qt,QTimer
import live2d.v3 as live2d
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from workers import VoiceWorker

MODERN_STYLE_QSS = """
    QDialog { background-color: #F3F4F6; }
    QTextBrowser { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 12px; font-size: 15px; font-family: "Microsoft YaHei", "Segoe UI"; line-height: 1.6; }
    QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding: 10px; font-size: 14px; background-color: #FFFFFF; }
    QLineEdit:focus { border: 1px solid #3B82F6; }
    QPushButton { background-color: #3B82F6; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-size: 14px; font-weight: bold; }
    QPushButton:hover { background-color: #2563EB; }
    QPushButton:pressed { background-color: #1D4ED8; }
"""

class Live2DWidget(QOpenGLWidget):
    def __init__(self, model_json_path, config,parent=None):
        super().__init__(parent)
        self.config = config
        self.model_json_path = model_json_path
        self.model = None

        # 👉 【极其关键】：配置 OpenGL 的背景为透明，否则小猫背后会是个大黑框！
        format = self.format()
        format.setAlphaBufferSize(8)
        self.setFormat(format)
        self.setAttribute(Qt.WA_AlwaysStackOnTop)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 👉 创建一个 60 帧的“心脏起搏器”，让画面动起来
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000 // 60)  # 约 16ms 刷新一次 (60 FPS)
        self.mouth_open = 0.0

    def initializeGL(self):
        # 初始化 Live2D 环境
        live2d.init()
        live2d.glInit()

        try:
            self.model = live2d.LAppModel()
            self.model.LoadModelJson(self.model_json_path)
            self.model.StartRandomMotion("Idle", 3)
            print("Live2D 模型加载成功！")
        except Exception as e:
            print(f"❌ 模型加载失败，是不是路径不对？错误信息：{e}")

    def resizeGL(self, w, h):
        if self.model:
            self.model.Resize(w, h)

        try:
            self.model.SetScale(self.config["live2d"]["scale"])
            self.model.SetOffset(self.config["live2d"]["offset_x"], self.config["live2d"]["offset_y"])
        except Exception as e:
            print(f"视角微调失败: {e}")


    def paintGL(self):
        live2d.clearBuffer()
        if self.model:
            self.model.Update()
            if self.mouth_open > 0:
                self.model.SetParameterValue("ParamA", self.mouth_open)
            self.model.Draw()

    def trigger_action(self, motion_group="TapBody"):
        if self.model:
            self.model.StartRandomMotion(motion_group, 3)


class FloatingBubble(QWidget):
    text_submitted = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_recording = False
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        self.setAttribute(Qt.WA_TranslucentBackground)

        self.container = QWidget(self)
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
        layout.setSpacing(4)
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
        top_layout.addWidget(self.user_label)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_close, 0, Qt.AlignTop)
        self.ai_label = QLabel("")
        self.ai_label.setWordWrap(True)
        self.ai_label.setStyleSheet(
            "color: #111827; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.ai_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.input = QLineEdit()
        self.input.setPlaceholderText("对我说点什么...")
        self.input.returnPressed.connect(self.on_submit)

        self.voice_worker = None
        self.btn_voice = QPushButton("🎤")
        self.btn_voice.setFixedSize(36, 36)
        self.btn_voice.setCursor(Qt.PointingHandCursor)
        self.btn_voice.setStyleSheet("""
                    QPushButton { border: 1px solid #E5E7EB; border-radius: 18px; background-color: #F9FAFB; font-size: 16px; }
                    QPushButton:hover { background-color: #FFB6C1; border-color: #FFB6C1; color: white; }
                """)
        self.btn_voice.clicked.connect(self.start_voice_input)

        input_layout.addWidget(self.input)
        input_layout.addWidget(self.btn_voice)

        layout.addLayout(top_layout)
        layout.addWidget(self.ai_label)
        layout.addWidget(self.input)
        layout.addLayout(input_layout)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.container)

    def start_voice_input(self):
        self.is_recording = True
        self.input.clear()
        self.input.setPlaceholderText("竖起耳朵聆听中...")
        self.btn_voice.setEnabled(False)  # 防止狂点录音
        self.btn_voice.setStyleSheet("background-color: #FFB6C1; border-radius: 18px; color: white;")
        self.voice_worker = VoiceWorker()

        def on_voice_success(text):
            self.reset_voice_ui()
            self.input.setText(text)
            self.on_submit()

        def on_voice_error(err_msg):
            self.reset_voice_ui()
            self.input.setPlaceholderText(err_msg)

        self.voice_worker.finished.connect(on_voice_success)
        self.voice_worker.error.connect(on_voice_error)
        self.voice_worker.start()

    def reset_voice_ui(self):
        self.is_recording = False
        self.input.setPlaceholderText("对我说点什么...")
        self.btn_voice.setEnabled(True)
        self.btn_voice.setStyleSheet("""
            QPushButton { border: 1px solid #E5E7EB; border-radius: 18px; background-color: #F9FAFB; font-size: 16px; }
            QPushButton:hover { background-color: #FFB6C1; border-color: #FFB6C1; color: white; }
        """)

    def on_submit(self):
        text = self.input.text().strip()
        if text:
            self.text_submitted.emit(text)
            self.input.clear()
            self.show_text("小脑袋转动中...", user_text=text)

    def show_input(self):
        self.input.show()
        self.show()
        self.adjustSize()
        self.input.setFocus()  # 自动聚焦，直接打字

    def show_text(self, ai_text, user_text=None):
        self.input.show()
        if user_text:
            self.user_label.setText(f"你: {user_text}")
            self.user_label.show()
            fm_user = self.user_label.fontMetrics()
            user_width = fm_user.horizontalAdvance(f"你: {user_text}") + 20
        else:
            user_width = 0

        self.ai_label.setText(ai_text)
        self.ai_label.show()
        fm_ai = self.ai_label.fontMetrics()
        ai_width = fm_ai.horizontalAdvance(ai_text) + 20
        final_width = min(max(user_width, ai_width, 200), 300)
        self.user_label.setMinimumWidth(final_width)
        self.user_label.setMaximumWidth(final_width)
        self.ai_label.setMinimumWidth(final_width)
        self.ai_label.setMaximumWidth(final_width)
        self.input.setMinimumWidth(final_width)
        self.input.setMaximumWidth(final_width)
        self.show()
        self.user_label.adjustSize()
        self.ai_label.adjustSize()
        self.container.adjustSize()
        self.adjustSize()

