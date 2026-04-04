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

    def __init__(self, config,text,engine="edge-tts"):
        super().__init__()
        self.text = text
        self.engine=engine
        self.base_filename= os.path.abspath(f"temp_voice_{int(time.time())}")
        self.config = config

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
            print(f"Edge-TTS 引擎故障:{e}")

    def _run_sovits(self, text):
        output_file=f"{self.base_filename}.wav"
        try:
            url = self.config["live2d"]["url"]
            payload = {
                "text": text,
                "text_language": self.config["live2d"]["text_language"]
                # "ref_audio_path": "D:/GPT-SoVITS/参考音频.wav",
                # "prompt_text": "这是参考音频里面说的话哦",
                # "prompt_lang": "zh"
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()  # 检查有没有报错
            with open(output_file, "wb") as f:
                f.write(response.content)

            self.finished.emit(output_file)
        except requests.exceptions.ConnectionError:
            print("\n❌ SoVITS 后台没开！我成哑巴了")
        except Exception as e:
            print(f"\n❌ SoVITS 引擎故障: {e}")

class VoiceWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def run(self):
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = recognizer.recognize_google(audio, language='zh-CN')
                self.finished.emit(text)

            except sr.WaitTimeoutError:
                self.error.emit("怎么不说话？拿我寻开心吗！")
            except sr.UnknownValueError:
                self.error.emit("嘟囔什么呢，大点声！")
            except Exception as e:
                self.error.emit(f"耳朵坏掉了喵：{str(e)}")

class LLMWorker(QThread):
    response_ready = Signal(str)

    def __init__(self, input_data,config):
        super().__init__()
        self.config = config

        if isinstance(input_data, list):
            self.messages = input_data
        else:
            system_prompt = self.config["prompt"]["content"]
            self.messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(input_data)}
            ]

    def run(self):
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": self.config["live2d"]["llm_model"],
            "messages": self.messages,
            "stream": False
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            reply = response.json().get("message", {}).get("content", "脑电波没接通...")
            self.response_ready.emit(reply)
        except requests.exceptions.ConnectionError:
            self.response_ready.emit("没网了！你是想饿死我吗！")
        except Exception as e:
            self.response_ready.emit(f"卡壳了：{str(e)}")