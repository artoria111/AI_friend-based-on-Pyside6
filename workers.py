import asyncio
import os
import re
import sys
import time

import av
import edge_tts
import numpy as np
import requests
import soundfile as sf
from PySide6.QtCore import QThread, Signal
import speech_recognition as sr
from faster_whisper import WhisperModel


def _default_whisper_settings():
    if sys.platform == "darwin":
        return {
            "model": "small",
            "device": "cpu",
            "compute_type": "int8",
        }
    return {
        "model": "small",
        "device": "cuda",
        "compute_type": "float16",
    }


def _resolve_whisper_settings(config):
    defaults = _default_whisper_settings()
    whisper_config = (config or {}).get("whisper", {})
    return {
        "model": whisper_config.get("model") or defaults["model"],
        "device": whisper_config.get("device") or defaults["device"],
        "compute_type": whisper_config.get("compute_type") or defaults["compute_type"],
    }


_whisper_model = None
_whisper_settings = None


def get_whisper_model(config):
    global _whisper_model, _whisper_settings
    settings = _resolve_whisper_settings(config)
    if _whisper_model is not None and _whisper_settings == settings:
        return _whisper_model

    print(
        "正在装载耳朵(Whisper)... "
        f"model={settings['model']} device={settings['device']} compute_type={settings['compute_type']}"
    )
    _whisper_model = WhisperModel(
        settings["model"],
        device=settings["device"],
        compute_type=settings["compute_type"],
    )
    _whisper_settings = settings
    print("耳朵装载完毕！")
    return _whisper_model

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
        mp3_file = f"{self.base_filename}.mp3"
        output_file = f"{self.base_filename}.wav"
        try:
            async def _generate():
                tts=edge_tts.Communicate(text,"zh-CN-XiaoyiNeural")
                await tts.save(mp3_file)
            asyncio.run(_generate())
            self._convert_audio_to_wav(mp3_file, output_file)
            if os.path.exists(mp3_file):
                os.remove(mp3_file)
            self.finished.emit(output_file)
        except Exception as e:
            print(f"Edge-TTS 引擎故障:{e}")

    def _convert_audio_to_wav(self, input_file, output_file):
        chunks = []
        sample_rate = None
        channels = None
        try:
            with av.open(input_file) as container:
                audio_stream = container.streams.audio[0]
                sample_rate = audio_stream.rate or 24000
                channels = audio_stream.channels or 1
                resampler = av.audio.resampler.AudioResampler(
                    format="s16",
                    layout=audio_stream.layout.name if audio_stream.layout else ("mono" if channels == 1 else "stereo"),
                    rate=sample_rate,
                )

                for frame in container.decode(audio=0):
                    resampled = resampler.resample(frame)
                    if resampled is None:
                        continue
                    frames = resampled if isinstance(resampled, list) else [resampled]
                    for audio_frame in frames:
                        array = audio_frame.to_ndarray()
                        if array.ndim == 2:
                            array = array.T
                        chunks.append(array)

            if not chunks:
                raise RuntimeError("音频转换失败：没有解码到任何音频帧")

            audio_data = np.concatenate(chunks, axis=0)
            sf.write(output_file, audio_data, sample_rate, subtype="PCM_16")
        except Exception:
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception:
                    pass
            raise

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

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        recognizer = sr.Recognizer()
        temp_file = f"temp_record_{int(time.time())}.wav"
        whisper_model = get_whisper_model(self.config)

        with sr.Microphone() as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                with open(temp_file, "wb") as f:
                    f.write(audio.get_wav_data())

                segments, info = whisper_model.transcribe(temp_file, beam_size=5, language="zh")
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
