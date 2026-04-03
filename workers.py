import asyncio
import os
import re
import time

import edge_tts
import requests
from PySide6.QtCore import QThread, Signal
import speech_recognition as sr


class TTSWorker(QThread):
    finished = Signal(str)

    def __init__(self, text,engine="edge-tts"):
        super().__init__()
        self.text = text
        self.engine=engine
        self.base_filename= os.path.abspath(f"temp_voice_{int(time.time())}")

    def run(self):
        clean_text = re.sub(r'\*.*?\*', '', self.text).strip()
        if not clean_text:
            return

        if self.engine=="edge-tts":
            self._run_edge_tts(clean_text)
        elif self.engine=="sovits":
            self._run_sovits(clean_text)

    def _run_edge_tts(self, text):
        output_file=f"{self.base_filename}.mp3"
        try:
            async def _generate():
                tts=edge_tts.Communicate(text,"zh-CN-XiaoyiNeural")
                await tts.save(output_file)
            asyncio.run(_generate())
            self.finished.emit(output_file)
        except Exception as e:
            print(f"Edge-TTS 引擎故障喵:{e}")

    def _run_sovits(self, text):
        output_file=f"{self.base_filename}.wav"
        try:
            url = "http://127.0.0.1:9880/"
            payload = {
                "text": text,
                "text_language": "zh"
                # "ref_audio_path": "D:/GPT-SoVITS/参考音频.wav",
                # "prompt_text": "这是参考音频里面说的话哦",
                # "prompt_lang": "zh"
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()  # 检查有没有报错
            with open(self.output_file, "wb") as f:
                f.write(response.content)

            self.finished.emit(self.output_file)
        except requests.exceptions.ConnectionError:
            print("\n❌ SoVITS 后台没开！本喵成了小哑巴")
        except Exception as e:
            print(f"\n❌ SoVITS 引擎故障喵: {e}")

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
                
                如果你发现主人想让你“记住”某事，请在回复的开头加上 [MEMO] 标记。
                如果你发现主人想让你“提醒”某事（带具体时间），请在开头加上 [ALARM:时间(秒)] 标记。
                示例：
                用户：帮我记下今天代码写得很顺。
                回复：[MEMO] 记下来了喵！今天也是个高产的笨蛋呢。
                用户：30分钟后叫我喝水。
                回复：[ALARM:1800] 知道了喵，半小时后本喵会来吵死你的！
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