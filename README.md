# 🔮 AI 驱动的 Live2D 桌面精灵

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-GUI-green.svg)
![Live2D](https://img.shields.io/badge/Live2D-Cubism-ff69b4.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

这是一个基于 Python 和 PySide6 开发的桌面级 AI 虚拟陪伴宠物。她不仅拥有原生的透明无框 Live2D 躯壳，还接入了本地 LLM 大模型与 TTS 语音合成，希望能给你增添一些乐趣。

## ✨ 核心特性 (Features)

- **🎭 原生 Live2D 渲染**：基于 `live2d-py` 与 OpenGL 的硬件加速渲染，完美支持透明背景、物理碰撞与随机待机动作，极低性能开销。
- **🗣️ 实时语音与动态口型 (Lip-Sync)**：集成 GPT-SoVITS / Edge-TTS，通过 `soundfile` 实时解析音频 RMS 包络线，驱动 Live2D 模型参数实现完美对口型。
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
推荐使用Python 包管理器 `uv` 来建立独立的虚拟环境：

```bash
# 创建并激活虚拟环境
uv venv
.venv\Scripts\activate
```

### 2. 下载项目依赖
```bash
uv sync
#或者
uv pip install -r requirements.txt
```
使用ollama来本地部署大模型(如果没有ollama请去官网下载)
```bash
ollama run qwen2.5:7b
```
qwen2.5为默认模型，可以使用其他模型（修改config.yaml中的模型即可）

### 3.准备Live2D模型
将你的 Live2D 运行时模型文件夹（需包含 .model3.json, .moc3 等文件）放置在项目根目录下。

打开 config.yaml，修改 live2d.model_path 指向你的模型配置文件。

### 4.运行
项目默认使用edge-tts，如果你没有本地部署GPT-SoVITS，可以直接运行下列命令
```bash
python main.py
```
如果你部署了GPT-SoVITS，请将config.yaml中的live2d.tts_engine修改为sovits，并确保sovits的api已开启

注意：如果你修改过config.yaml，请你重启她
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