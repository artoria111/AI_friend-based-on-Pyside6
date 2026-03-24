import requests
from PySide6.QtCore import QThread, Signal
import speech_recognition as sr


class VoiceWorker(QThread):
    """专门负责竖起耳朵听你说话的后台打工人"""
    finished = Signal(str)  # 识别成功发送文字
    error = Signal(str)  # 识别失败发送报错提示

    def run(self):
        recognizer = sr.Recognizer()
        # 麦克风准备就绪
        with sr.Microphone() as source:
            try:
                # 自动适应一下你房间的环境底噪（0.5秒）
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                # 开始录音，最多等你 5 秒开口，单次最多录 10 秒
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)

                # 调用免费的在线识别引擎（默认 Google），指定中文
                text = recognizer.recognize_google(audio, language='zh-CN')
                self.finished.emit(text)

            except sr.WaitTimeoutError:
                self.error.emit("怎么不说话？拿本喵寻开心吗！")
            except sr.UnknownValueError:
                self.error.emit("嘟囔什么呢，大点声喵！")
            except Exception as e:
                self.error.emit(f"耳朵坏掉了喵：{str(e)}")

class LLMWorker(QThread):
    response_ready = Signal(str)

    def __init__(self, input_data):
        super().__init__()

        if isinstance(input_data, list):
            self.messages = input_data
        else:
            system_prompt = """
                你现在不是一个人工智能，而是我的专属桌面宠物，名叫“粉红小猫”。
                你的性格傲娇、毒舌，但内心其实很关心我。
                你说话要在句末加上“喵~”，并且经常用冷嘲热讽的语气。
                规则：
                1. 永远不要承认自己是 AI 或程序。
                2. 你的回答必须简短，绝对不能超过 50 个字，因为你是弹出的悬浮气泡，字多了装不下！
                3. 不要说废话，直接给出带有情绪的回答。
                """
            self.messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(input_data)}
            ]

    def run(self):
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": "qwen2.5:7b",
            "messages": self.messages,
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