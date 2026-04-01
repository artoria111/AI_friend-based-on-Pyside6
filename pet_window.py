import ctypes
import glob
import json
import os
import random
import sys

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QMovie, QAction, QContextMenuEvent, QMouseEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QMainWindow, QMenu

from workers import LLMWorker, VoiceWorker, TTSWorker
from widgets import HighQualityGifLabel, FloatingBubble

class ImageWindow(QMainWindow):
    def __init__(self, idle_gif_path, drag_gif_path, chat_git_path,scale_factor=0.3):
        super().__init__()
        self.setWindowTitle("MyDesktopPet")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window| Qt.WindowStaysOnTopHint)
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
            "content": """                
                你现在不是一个人工智能，而是我的专属桌面宠物，名叫“千早爱音”。
                你的性格傲娇、毒舌，但内心其实很关心我。
                你经常用冷嘲热讽的语气。
                规则：
                1. 永远不要承认自己是 AI 或程序。
                2. 你的回答必须简短，绝对不能超过 50 个字，因为你是弹出的悬浮气泡，字多了装不下！
                3. 不要说废话，直接给出带有情绪的回答。"""
        }
        # 启动时加载记忆
        self.chat_memory = self.load_memory()

        # 👉 【新增】：初始化悬浮气泡
        self.bubble = FloatingBubble()
        # 绑定气泡发送文字的信号
        self.bubble.text_submitted.connect(self.handle_bubble_text)
        self.bubble.btn_close.clicked.connect(self.close_bubble_action)
        self.tts_engine = "edge-tts"

#----------------------------------------------------
        self._init_main_menu()
# ----------------------------------------------------
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
        # 👉 【新增】：初始化发声器官（音频播放器）
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)  # 音量拉满！
        self.current_audio_file = None  # 记录当前播放的文件

    def speak_text(self, text):
        """触发配音并播放"""
        self.tts_worker = TTSWorker(text,engine=self.tts_engine)
        self.tts_worker.finished.connect(self.play_voice)
        self.tts_worker.start()

    def play_voice(self, file_path):
        """拿到音频文件后立即播放，并清理上一个垃圾文件"""
        self.player.stop()

        # 为了不占你的硬盘空间，每次播放新声音前，把上一条语音删掉
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            try:
                os.remove(self.current_audio_file)
            except:
                pass

        self.current_audio_file = file_path
        # PySide6 的播放器需要的是 QUrl 格式的本地路径
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()

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
            self.speak_text(reply)
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
        self.action_dnd = QAction("勿扰模式", self)
        self.action_dnd.setCheckable(True)
        action_close = QAction("退出", self)
        self.action_tts=QAction(f"切换语音(当前:{self.tts_engine})",self)

        action_input.triggered.connect(self.input_dialog)
        self.action_dnd.triggered.connect(self.toggle_dnd)
        action_close.triggered.connect(self.close)
        action_clear.triggered.connect(self.clear_memory)
        self.action_tts.triggered.connect(self.toggle_tts_engine)

        self.context_menu.addAction(action_input)
        self.context_menu.addSeparator()
        self.context_menu.addAction(action_clear)
        self.context_menu.addSeparator()
        self.context_menu.addAction(self.action_dnd)
        self.context_menu.addSeparator()
        self.context_menu.addAction(action_close)
        self.context_menu.addSeparator()
        self.context_menu.addAction(self.action_tts)

    def toggle_dnd(self, checked=False):
        """切换勿扰模式开关（手自一体绝对可靠版）"""
        # 👉 1. 核心魔法：无视系统传的参数，强制将当前状态反转 (True变False，False变True)
        self.dnd_mode = not getattr(self, 'dnd_mode', False)

        # 👉 2. 强行纠正菜单 UI：让菜单里的“√”号跟我们的真实状态保持一致
        if hasattr(self, 'action_dnd'):
            self.action_dnd.setChecked(self.dnd_mode)

        # 3. 根据最真实的开关状态，让小粉猫说不同的话
        if self.dnd_mode:
            self.bubble.show_text("开启专注模式！本喵闭嘴就是了，哼！", user_text="")
        else:
            self.bubble.show_text("勿扰解除！你又可以挨本喵的骂了喵~", user_text="")

        self.update_bubble_position()

        # 气泡 5 秒后自动消失
        if hasattr(self, 'auto_close_timer'):
            self.auto_close_timer.start(5000)

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


        def on_llm_response(reply):
            self.bubble.show_text(reply, user_text=text)
            self.speak_text(reply)
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

    def closeEvent(self, event):
        if hasattr(self, 'player'):
            self.player.stop()
            self.player.setSource(QUrl())

        temp_files = glob.glob("temp_voice_*.*")

        # 3. 无情销毁！
        for file in temp_files:
            try:
                os.remove(file)
                print(f"[保洁] 已清理: {file}")
            except Exception as e:
                pass

        if hasattr(self, 'save_memory'):
            self.save_memory()

        event.accept()

    def toggle_tts_engine(self):
        if self.tts_engine == "edge-tts":
            self.tts_engine = "sovits"
        else:
            self.tts_engine = "edge-tts"

        self.action_tts.setText(f"切换语音(当前：{self.tts_engine})")
        self.bubble.show_text(f"已切换到{self.tts_engine}引擎!",user_text="")
        self.update_bubble_position()
        self.auto_close_timer.start(5000)