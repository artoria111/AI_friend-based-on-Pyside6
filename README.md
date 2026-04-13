# 🔮 AI 驱动的 Live2D 桌面精灵

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-GUI-green.svg)
![Live2D](https://img.shields.io/badge/Live2D-Cubism-ff69b4.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

这是一个基于 Python 和 PySide6 开发的桌面级 AI 虚拟陪伴宠物。她不仅拥有原生的透明无框 Live2D 躯壳，还接入了本地 LLM 大模型与 TTS 语音合成，希望能给你增添一些乐趣。

当前仓库已经完成一轮 macOS 适配，并保留了 Windows 分支逻辑。macOS 上已验证可启动、可语音输入、可语音播报；Windows 代码路径仍然保留，但建议在目标机器上再做一次实际回归。

## ✨ 核心特性 (Features)

- **🎭 原生 Live2D 渲染**：基于 `live2d-py` 与 OpenGL 的硬件加速渲染，完美支持透明背景、物理碰撞与随机待机动作，极低性能开销。
- **🗣️ 实时语音与动态口型 (Lip-Sync)**：集成 GPT-SoVITS / Edge-TTS，当前默认会将 Edge-TTS 输出转换为 `wav` 后播放，并通过 `soundfile` 实时解析音频 RMS 包络线驱动 Live2D 口型，降低 macOS 下短语音首字延迟与吞字问题。
- **🧠 大语言模型大脑**：支持自定义 System Prompt，塑造独一无二的傲娇/毒舌/温柔人设。
- **⏰ 强制霸屏提醒系统**：AI 语义提取日程安排，时间一到强制接管屏幕中心，不互动绝不退让的“硬核”监督。
- **⚙️ 全局 YAML 配置**：通过 `config.yaml` 零代码热切换模型、调整视口坐标、切换语音引擎和更改人设。

## 🛠️ 技术栈 (Tech Stack)

- **GUI 框架**: PySide6 (Qt for Python)
- **图形渲染**: OpenGL, live2d-py
- **音频处理**: soundfile, numpy, PySide6.QtMultimedia
- **AI 交互**: requests (对接本地LLM 接口), GPT-SoVITS 

## 🚀 快速开始 (Getting Started)

### 1. 环境准备
推荐使用 Python 3.10+ 与独立虚拟环境。

Windows:
```bash
uv venv
.venv\Scripts\activate
```

macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

推荐先确认当前使用的是项目虚拟环境里的 Python：

```bash
which python
# 期望输出:
# /Users/你的用户名/.../AI_friend-based-on-Pyside6/.venv/bin/python
```

如果你准备在 macOS 上使用语音输入，先安装 PortAudio：

```bash
brew install portaudio
```

如果你的虚拟环境里没有 `pip`，先补上：

```bash
python -m ensurepip --upgrade
python -m pip install --upgrade pip setuptools wheel
```

### 2. 下载项目依赖
```bash
uv sync
# 或者
uv pip install -r requirements.txt
```

如果在 macOS 上安装 `pyaudio` 失败，可以在激活虚拟环境后单独重试：

```bash
pip install pyaudio
```

如果你不使用 `uv`，也可以直接：

```bash
pip install -r requirements.txt
```

### 3. 准备本地大模型
使用 Ollama 本地部署大模型（如果没有 Ollama 请先安装它）：

```bash
ollama pull qwen2.5:7b
ollama run qwen2.5:7b
```

`qwen2.5:7b` 为默认模型，可以通过修改 `config.yaml` 中的 `live2d.llm_model` 切换为其他模型。

如果模型已经下载过，后续通常只需要：

```bash
ollama run qwen2.5:7b
```

注意：

- `ollama serve` 只需要有一个实例在运行，不要重复执行
- 如果看到 `listen tcp 127.0.0.1:11434: bind: address already in use`，通常表示 Ollama 服务已经启动了
- `ollama pull` 下载中断后可以直接重试，通常会续传

### 4. 准备 Live2D 模型
将你的 Live2D 运行时模型文件夹（需包含 .model3.json, .moc3 等文件）放置在model目录下。

打开 config.yaml，修改 live2d.model_path 指向你的模型配置文件。

### 5. 配置说明
项目默认使用 `edge-tts`。如果你没有本地部署 GPT-SoVITS，可以直接保持 `config.yaml` 中的 `live2d.tts_engine: "edge-tts"`。

`config.yaml` 中新增了 `whisper` 配置项：

```yaml
whisper:
  model: "small"
  device: ""
  compute_type: ""
```

- 留空时会按平台自动选择：macOS 默认 `cpu + int8`，Windows 默认 `cuda + float16`
- 你也可以手动指定：例如 `device: "cpu"`、`compute_type: "int8"`

音频和口型同步相关配置：

```yaml
audio:
  start_delay_ms: 0

lip_sync:
  offset_ms: 180
```

- `audio.start_delay_ms`：音频调用 `play()` 前的额外延迟，默认 `0`
- `lip_sync.offset_ms`：口型相对声音时间轴的偏移量；macOS 下如果仍然感觉嘴比声音早，可以继续增大这个值，例如 `220`、`260`
- 当前默认播放链路更偏向“先保证声音尽快出来，再用 `lip_sync.offset_ms` 微调嘴型同步”

### 6. 运行
项目默认使用 edge-tts，如果你没有本地部署 GPT-SoVITS，可以直接运行下列命令：

```bash
python main.py
```

或者显式使用项目虚拟环境中的解释器：

```bash
.venv/bin/python main.py
```

如果你部署了 GPT-SoVITS，请将 `config.yaml` 中的 `live2d.tts_engine` 修改为 `sovits`，并确保 SoVITS API 已开启。

macOS 额外注意：

- 第一次使用麦克风时，请到“系统设置 > 隐私与安全性 > 麦克风”允许你的终端、IDE 或 Python。
- 随机互动功能会尝试读取当前前台应用/窗口标题；如果系统没有授予“辅助功能”或“自动化”权限，程序会自动降级为不读取窗口标题，但不会崩溃。
- 托盘图标在不同 macOS 版本上的表现可能略有差异；如果系统托盘不可用，程序会自动跳过托盘初始化。
- `python main.py` 启动后终端不会立刻返回提示符，这是正常现象，因为 GUI 事件循环已经在运行。
- 桌宠默认出现在屏幕右下角附近；如果终端没有报错但你没看到窗口，请先看屏幕边缘和托盘区域。

注意：如果你修改过config.yaml，请你重启她

### 7. macOS 常见问题

1. `ModuleNotFoundError: No module named 'live2d'`

通常表示当前运行的不是项目虚拟环境里的 Python。请先执行：

```bash
source .venv/bin/activate
which python
python main.py
```

2. 运行 `python main.py` 后“卡住不动”

如果没有报错，这通常不是卡死，而是 GUI 程序正在前台运行。可以检查：

- 桌宠是否已经出现在屏幕右下角
- 是否被其他窗口遮挡
- 是否已经缩到托盘

3. 点击语音按钮后没有识别到声音

先确认 macOS 麦克风权限已经给到你实际启动程序的终端或 IDE。

然后可以在虚拟环境里测试麦克风枚举：

```bash
python - <<'PY'
import speech_recognition as sr
print(sr.Microphone.list_microphone_names())
PY
```

如果输出是空列表 `[]`，通常说明：

- 麦克风权限没有开启
- 当前没有可用输入设备
- `PyAudio/PortAudio` 输入链路没有正确工作

4. 角色说话时开头被吞字

目前项目已经把 Edge-TTS 的播放链路改成了更适合短语音的 `wav + 低延迟播放` 方案，macOS 下“吞前几个字”的问题已经明显改善。

如果仍然感觉“嘴先动、声音后到”或偶发吞字，请优先检查：

- 当前系统音频输出设备是否切换频繁
- 是否有其他程序占用音频设备
- 是否是特定 TTS 引擎或特定短句更明显
- 是否需要继续调大 `config.yaml` 中的 `lip_sync.offset_ms`
## 🎮 互动指南 
1.唤醒与拖拽：鼠标左键按住身体可自由拖拽位置,默认生成位置为屏幕右下角（可在config.yaml中更改）

2.菜单互动：右击加载好的live2d可以弹出菜单栏

3.语音聊天：点击气泡上的麦克风按钮输入文字（或语音），等待她回复并开口说话。

4.日程提醒：直接对她说：“10分钟后提醒我喝水”，她会自动记录并在倒计时结束后“突脸”提醒。

5.随机互动：她会读取当前窗口的标题，并产生随机互动。


## 📄 开源协议
本项目基于 MIT License 开源。

注：Live2D 引擎及相关模型版权归属于 Live2D 

Inc. 及原画师/模型师，请遵循官方最终用户许可协议。
