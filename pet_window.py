import ctypes
import glob
import json
import os
import random
import soundfile as sf
import numpy as np

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import  QAction, QContextMenuEvent, QMouseEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QMainWindow, QMenu, QApplication

from workers import LLMWorker, TTSWorker
from widgets import Live2DWidget, FloatingBubble

class ImageWindow(QMainWindow):
    def __init__(self, config,scale_factor=0.3):
        super().__init__()
        self.setWindowTitle("MyDesktopPet")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.config = config

        self._drag_pos = None
        self.visual_timer = QTimer(self)
        self.visual_timer.setSingleShot(True)
        self.visual_timer.timeout.connect(self._enable_drag_visuals)
        self.scale_factor = scale_factor

        model_path = "mao_pro_zh/runtime/mao_pro.model3.json"
        self.view = Live2DWidget(model_path, self.config,self)
        self.setCentralWidget(self.view)
        w=config['window']['width']
        h=config['window']['height']
        self.resize(w, h)
        self.set_initial_position()
        
        # 👉 【新增】：默认关闭勿扰模式
        self.dnd_mode = False

        self.history_file = "pet_memory.json"
        self.system_prompt = {
            "role": "system",
            "content": config["prompt"]["content"]
        }
        # 启动时加载记忆
        self.chat_memory = self.load_memory()

        # 👉 【新增】：初始化悬浮气泡
        self.bubble = FloatingBubble()
        # 绑定气泡发送文字的信号
        self.bubble.text_submitted.connect(self.handle_bubble_text)
        self.bubble.btn_close.clicked.connect(self.close_bubble_action)
        self.tts_engine = self.config["live2d"]["tts_engine"]
        self.diary_file = "pet_diary.json"
        self.reminders = []  # 存放待触发的提醒任务


#----------------------------------------------------
        self._init_main_menu()
# ----------------------------------------------------
        self.llm_workers = []
        self.chatter_timer = QTimer(self)
        self.chatter_timer.timeout.connect(self.trigger_random_chatter)
        self.chatter_timer.start(60000)
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.close_bubble_action)
        self.bubble.input.textChanged.connect(self.auto_close_timer.stop)
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(config["live2d"]["volume"])
        self.current_audio_file = None
        self.volume_data = [] 
        self.lip_sync_timer = QTimer(self)
        self.lip_sync_timer.timeout.connect(self.update_lip_sync)

    def speak_text(self, text):
        """触发配音并播放"""
        self.tts_worker = TTSWorker(text,self.config,engine=self.tts_engine)
        self.tts_worker.finished.connect(self.play_voice)
        self.tts_worker.start()

    def play_voice(self, file_path):
        if hasattr(self, 'player'):
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.volume_data = self.analyze_audio_volume(file_path)
            self.player.play()
            self.lip_sync_timer.start(33)
        self.player.stop()
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            try:
                os.remove(self.current_audio_file)
            except:
                pass

        self.current_audio_file = file_path
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()

    def get_active_window_title(self):
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
        if random.random() > self.config['live2d']['random_chatter']:
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
                         f"是：'{window_title}'。请根据这个窗口的名字，用你的人设，"
                         f"主动弹出来吐槽我一句。字数严格控制在20字以内！直接说吐槽的话！")
        temp_worker = LLMWorker(secret_prompt,self.config)

        def on_chatter_response(reply):
            self.bubble.show_text(reply, user_text="")
            self.speak_text(reply)
            self.update_bubble_position()
            self.auto_close_timer.start(15000)
            if temp_worker in self.llm_workers:
                self.llm_workers.remove(temp_worker)

        temp_worker.response_ready.connect(on_chatter_response)
        self.llm_workers.append(temp_worker)
        temp_worker.start()

    def close_bubble_action(self):
        self.bubble.hide()


    def update_bubble_position(self):
        pet_rect = self.frameGeometry()
        bubble_x = pet_rect.left()+self.config['bubble']['bubble_x']
        bubble_y = pet_rect.top()+self.config['bubble']['bubble_y']
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
        self.dnd_mode = not getattr(self, 'dnd_mode', False)
        if hasattr(self, 'action_dnd'):
            self.action_dnd.setChecked(self.dnd_mode)

        if self.dnd_mode:
            self.bubble.show_text("开启专注模式！我闭嘴就是了，哼！", user_text="")
        else:
            self.bubble.show_text("勿扰解除！我又回来了", user_text="")

        self.update_bubble_position()

        if hasattr(self, 'auto_close_timer'):
            self.auto_close_timer.start(5000)

    def clear_memory(self):
        self.chat_memory = [self.system_prompt]
        self.save_memory()
        self.bubble.show_text("叮~ 记忆已格式化！刚才发生了什么？我突然什么都不记得了！", user_text=None)
        self.update_bubble_position()

    def input_dialog(self):
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
            if reply.startswith("[ALARM:"):
                try:
                    seconds = int(reply.split(":")[1].split("]")[0])
                    msg = reply.split("]")[1].strip()
                    QTimer.singleShot(seconds * 1000, lambda: self.trigger_hardcore_reminder(msg))
                    display_reply = msg
                except:
                    display_reply = reply

            elif reply.startswith("[MEMO]"):
                display_reply = reply.replace("[MEMO]", "").strip()
                self.save_to_diary(text)

            else:
                display_reply = reply
            self.bubble.show_text(display_reply, user_text=text)
            self.speak_text(display_reply)
            self.update_bubble_position()
            self.auto_close_timer.start(15000)
            if hasattr(self, 'view'):
                self.view.trigger_action("")
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


    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.visual_timer.start(150)
            self.setCursor(Qt.ClosedHandCursor)
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

            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.visual_timer.isActive():
                self.visual_timer.stop()
            # 双击桌宠隐藏气泡 (之前这里写的是关闭程序 self.close())
            self.bubble.hide()

    def load_memory(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    memory = json.load(f)
                    if memory and memory[0].get("role") == "system":
                        memory[0] = self.system_prompt
                    else:
                        memory.insert(0, self.system_prompt)
                    return memory
            except Exception as e:
                print(f"记忆损坏了：{e}")

        return [self.system_prompt]

    def save_memory(self):
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

    def save_to_diary(self, content):
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {"time": timestamp, "content": content}
        diary_data = []
        if os.path.exists(self.diary_file):
            with open(self.diary_file, "r", encoding="utf-8") as f:
                diary_data = json.load(f)

        diary_data.append(entry)

        with open(self.diary_file, "w", encoding="utf-8") as f:
            json.dump(diary_data, f, ensure_ascii=False, indent=4)

    def trigger_hardcore_reminder(self, msg):
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center() - self.rect().center())

        reminder_text = f"时间到了！该去‘{msg}’了！我会一直盯着你的>_<"
        self.bubble.show_text(reminder_text, user_text="")
        self.bubble.btn_close.hide()

        self.bubble.input.setPlaceholderText("输入‘我知道了’解除霸屏...")

    def set_initial_position(self):
        screen_geo = QApplication.primaryScreen().availableGeometry()
        pet_width = self.width()
        pet_height = self.height()
        target_x = screen_geo.width() - self.config['window']['margin_x']-pet_width
        target_y = screen_geo.height() - self.config['window']['margin_y']-pet_height
        self.move(target_x, target_y)

    def analyze_audio_volume(self, audio_path):
        try:
            data, samplerate = sf.read(audio_path)

            # 如果是双声道音频，我们只取其中一个声道来计算
            if len(data.shape) > 1:
                data = data[:, 0]

            # 按 30fps 切片计算均方根 (RMS) 音量
            chunk_size = samplerate // 30
            volumes = []

            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                # 计算这段时间的平均音量大小
                rms = np.sqrt(np.mean(chunk ** 2))
                volumes.append(float(rms))

            # 归一化：把最大音量变成 1.0
            if volumes:
                max_vol = max(volumes)
                if max_vol > 0:
                    volumes = [v / max_vol for v in volumes]

            return volumes

        except Exception as e:
            print(f"❌ 强悍解析器也失败了，格式有问题: {e}")
            return []

    def update_lip_sync(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            current_time_ms = self.player.position()
            chunk_index = int(current_time_ms / (1000 / 30))

            if chunk_index < len(self.volume_data):
                volume = self.volume_data[chunk_index]
                mouth_open = min(volume * 2.0, 1.0)
                if hasattr(self, 'view'):
                    self.view.mouth_open = mouth_open
        else:
            self.lip_sync_timer.stop()
            if hasattr(self, 'view'):
                self.view.mouth_open = 0.0