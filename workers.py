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
        if not self.text:
            print("🈳 没收到要说的话，发声车间罢工了~")
            return
        safe_text = str(self.text)
        clean_text = re.sub(r'\*.*?\*', '', safe_text).strip()
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

    def __init__(self, whisper_model):
        super().__init__()
        self.whisper_model = whisper_model

    def run(self):
        recognizer = sr.Recognizer()
        temp_file = f"temp_record_{int(time.time())}.wav"

        with sr.Microphone() as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                with open(temp_file, "wb") as f:
                    f.write(audio.get_wav_data())

                segments, info = self.whisper_model.transcribe(
                    temp_file,
                    beam_size=5,
                    language="zh",
                    initial_prompt="以下是一段普通话日常对话。",
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
                text = "".join([segment.text for segment in segments]).strip()

                if not text:
                    self.error.emit("没听到声音喵~")
                else:
                    self.finished.emit(text)

            except sr.WaitTimeoutError:
                self.error.emit("怎么不说话？拿我寻开心吗！")
            except Exception as e:
                print(f"Error: {repr(e)}")
                self.error.emit(f"耳朵坏掉了喵：{str(e)}")
            finally:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        print(f"[保洁] 已清理临时录音文件: {temp_file}")
                    except Exception as e:
                        print(f"清理临时录音文件失败: {e}")


class LLMWorker(QThread):
    response_ready = Signal(str)
    def __init__(self, input_data, config, llm):
        super().__init__()
        self.config = config
        self.llm = llm
        self.llm_mode = self.config.get("llm", {}).get("mode", "local")

        if isinstance(input_data, list):
            self.messages = input_data
        else:
            system_prompt = self.config["prompt"]["content"]
            self.messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(input_data)}
            ]

    def run(self):
        try:
            if self.llm_mode == "api":
                response = self.llm.chat.completions.create(
                    model=self.config["llm"]["api_model"],
                    messages=self.messages,
                    temperature=0.7
                )
                # 提取回复内容
                reply = response.choices[0].message.content
            else:
                response = self.llm.create_chat_completion(
                    messages=self.messages,
                    max_tokens=self.config.get("live2d", {}).get("max_tokens", 100),
                    temperature=self.config.get("live2d", {}).get("temperature", 0.7)
                )
                reply = response["choices"][0]["message"]["content"]
            self.response_ready.emit(reply)

        except Exception as e:
            self.response_ready.emit(f"大脑短路了喵：{str(e)}")


from PySide6.QtCore import QThread, Signal

class BrainLoaderThread(QThread):
    brain_ready = Signal(object)
    error_occurred = Signal(str)
    progress_updated = Signal(float)

    def __init__(self, model_path):
        super().__init__()
        self.model_path = model_path

    def run(self):
        try:
            from llama_cpp import Llama
            def my_progress_callback(progress_val: float):
                self.progress_updated.emit(progress_val)
                return None

            print("🧠 后台线程：开始搬运大脑到显卡...")
            # 这里的耗时操作不会卡住界面了
            llm = Llama(
                model_path=self.model_path,
                n_gpu_layers=-1,
                n_ctx=2048,
                use_mmap=False,
                verbose=False,
                progress_callback=my_progress_callback
            )
            print("🧠 后台线程：大脑搬运完毕！")
            self.brain_ready.emit(llm) # 把大脑递给主窗口
        except Exception as e:
            self.error_occurred.emit(f"脑电波连接失败：{str(e)}")


from PySide6.QtCore import QThread, Signal


class WhisperLoaderThread(QThread):
    whisper_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, model_size="medium", device="cuda", compute_type="float16"):
        super().__init__()
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    def run(self):
        try:
            # 👉 绝对核心：延迟导入！把这句从文件最上面挪到这里来！
            from faster_whisper import WhisperModel

            print("👂 后台线程：开始加载听觉神经 (Whisper)...")

            # 初始化模型（这里可能会耗时几秒到十几秒）
            whisper_model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )

            print("👂 后台线程：听觉神经加载完毕！")
            # 把耳朵递给主窗口
            self.whisper_ready.emit(whisper_model)

        except Exception as e:
            self.error_occurred.emit(f"听觉神经加载失败：{str(e)}")