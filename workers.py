import os
import re
import time
import requests
from PySide6.QtCore import QThread, Signal
import speech_recognition as sr


class TTSWorker(QThread):
    """专门连接本地 GPT-SoVITS 模型的配音打工人"""
    finished = Signal(str)

    def __init__(self, text):
        super().__init__()
        self.text = text
        # 本地合成一般用 wav 格式，无损且响应快
        self.output_file = os.path.abspath(f"temp_voice_{int(time.time())}.wav")

    def run(self):
        try:
            # 1. 清洗掉大模型生成的动作标签，比如把 "*傲娇地撇嘴* 笨蛋" 变成 "笨蛋"
            clean_text = re.sub(r'\*.*?\*', '', self.text).strip()

            if not clean_text:
                return

            # 2. GPT-SoVITS 的标准本地 API 地址 (默认端口通常是 9880)
            url = "http://127.0.0.1:9880/"

            # 3. 构造请求参数
            # 如果你在 api.py 里已经写死了参考音频，这里只需要传文本就行了！
            payload = {
                "text": clean_text,
                "text_language": "zh"

                # 💡 如果你在 API 端没有设置默认参考音频，就需要在这里把参数传过去，把下面几行取消注释并填好：
                # "ref_audio_path": "D:/GPT-SoVITS/参考音频.wav",
                # "prompt_text": "这是参考音频里面说的话哦",
                # "prompt_lang": "zh"
            }

            # 4. 发送生成请求 (使用 POST 方式更稳定)
            response = requests.post(url, json=payload)
            response.raise_for_status()  # 检查有没有报错

            # 5. 把拿回来的二进制音频数据保存成 .wav 文件
            with open(self.output_file, "wb") as f:
                f.write(response.content)

            # 6. 通知主线程：音频准备好了，快播放！
            self.finished.emit(self.output_file)

        except requests.exceptions.ConnectionError:
            print("\n❌ 语音合成失败：GPT-SoVITS 的 API 后台没启动喵？")
        except Exception as e:
            print(f"\n❌ 配音报错喵: {e}")

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