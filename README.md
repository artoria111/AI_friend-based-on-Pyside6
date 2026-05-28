# 🔮 AI 驱动的 Live2D 桌面精灵

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-GUI-green.svg)
![Live2D](https://img.shields.io/badge/Live2D-Cubism-ff69b4.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![RAG](https://img.shields.io/badge/RAG-ChromaDB-orange.svg)
![Agent](https://img.shields.io/badge/Agent-Function_Calling-purple.svg)

> 不是普通的桌面宠物——她拥有**三层记忆系统**（RAG 语义检索）、**Function Calling 工具链**、**情绪感知**和 Live2D 实时表情反馈。你可以把她当作一个具备长期记忆和主动行动能力的 AI 陪伴角色。

## ✨ 核心特性

### 🧠 三层记忆系统（RAG）
- **工作记忆**：最近 20 轮对话，保存在 `pet_memory.json`
- **语义记忆**：用户事实（生日、偏好等），通过 ChromaDB 向量数据库持久化
- **情节记忆**：每 5 轮对话自动生成摘要，形成"回忆片段"
- 基于 ModelScope `gte_sentence_embedding` 模型做中文语义检索，无需联网

### 🔧 Function Calling 工具链
宠物不仅是"聊天机器人"，她能**主动调用工具**：

| 工具 | 用途 | 示例 |
|------|------|------|
| `write_memory` | 记住用户事实 | "帮我记下我喜欢喝红茶" |
| `set_alarm` | 定时提醒 | "5 分钟后提醒我喝水" |
| `search_memory` | 检索记忆 | "你还记得我喜欢喝什么吗？" |
| `set_mood` | 感知情绪变化 | "今天好开心！" → 自动检测 |
| `get_time` | 获取当前时间 | "现在几点了？" |

### 😊 情绪感知与自适应
- 8 种情绪标签：happy / excited / sad / worried / angry / tired / bored / neutral
- **趋势追踪**：最近 3 次情绪变化，判断"持续开心""在好转""在变差"等趋势
- **自适应提示词**：根据情绪动态注入引导语（低落时温柔安慰，兴奋时热烈回应）
- **Live2D 表情同步**：情绪变化实时映射到模型表情（眯眼笑、星光大眼、委屈、嘟嘴等）

### 🎭 Live2D 实时渲染
- 基于 `live2d-py` + OpenGL 硬件加速，透明无框窗口 + 始终置顶
- Lip-Sync 口型同步：`soundfile` 实时解析 RMS 音频包络，驱动 Live2D 嘴部参数

### 🗣️ 语音交互
- 支持 Edge-TTS（免部署）和 GPT-SoVITS（高拟真度）双引擎
- 语音识别：Whisper + VAD 降噪，支持中文语音输入
- 自动过滤 emoji：TTS 合成前剥离表情符号，避免朗读乱码

### 📊 评估框架
- 独立的 `eval_framework.py`，无 GUI 依赖，可 CLI 直接运行
- 四个维度自动评测：Tool Calling / Memory Recall / Mood Perception / Persona Consistency
- 输出 `eval_report.md` 评分报告

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| GUI | PySide6 (Qt), OpenGL |
| 模型渲染 | live2d-py (Cubism 3) |
| 大语言模型 | DeepSeek V4 Pro / Qwen2.5 (本地 GGUF) |
| 向量数据库 | ChromaDB (PersistentClient, cosine 相似度) |
| Embedding | ModelScope `gte_sentence_embedding_chinese-small` (512d) |
| TTS | Edge-TTS / GPT-SoVITS |
| ASR | faster-whisper + speech_recognition |
| 协议 | OpenAI Function Calling (tool_calls loop) |

## 🚀 快速开始

### 1. 环境准备

```bash
git clone <repo-url>
cd AI_friend

# 创建虚拟环境（推荐 uv）
uv venv
.venv\Scripts\activate

# 安装依赖
uv pip install -r requirements.txt
```

### 2. 配置 LLM

编辑 `config.yaml`：

```yaml
llm:
  mode: "api"                              # api 或 local
  api_url: "https://api.deepseek.com"      # API 地址
  api_key: "sk-xxxxxxxx"                   # 你的 API Key
  api_model: "deepseek-v4-pro"             # 模型名称
```

或使用本地模型：

```yaml
llm:
  mode: "local"
  local_path: "models/qwen2.5-3b-instruct-q4_k_m.gguf"
```

### 3. 放置 Live2D 模型

将模型文件夹放入 `model/` 目录，修改 `config.yaml`：

```yaml
live2d:
  model_path: "model/mao_pro_zh/runtime/mao_pro.model3.json"
```

### 4. 运行

```bash
python main.py
```

**Release 版**：直接下载 Releases 中的压缩包，解压运行 `AI_friend.exe`。

## 🎮 互动指南

| 操作 | 效果                                |
|------|-----------------------------------|
| 左键拖拽 | 移动宠物位置                            |
| 右键菜单 | 对话 / 一键失忆 / 勿扰模式 / 音量 / 切换语音 / 退出 |
| 点击气泡输入框 | 文字聊天（按 Enter 发送）                  |
| 点击 🎤 按钮 | 语音输入（Whisper 识别）                  |
| 双击宠物 | 关闭气泡                              |
| 托盘图标 | 显示 / 隐藏 / 音量 / 退出                 |

## 🧪 运行评估

```bash
python eval_framework.py
```

会在控制台实时输出评分，并生成 `eval_report.md` 详细报告。

## 📂 项目结构

```
AI_friend/
├── main.py              # 入口
├── pet_window.py        # 主窗口 + 交互逻辑 + 记忆/情绪集成
├── widgets.py           # Live2DWidget + FloatingBubble
├── workers.py           # LLMWorker (工具链循环) + TTSWorker + VoiceWorker
├── memory_manager.py    # 三层记忆系统 (ChromaDB + Embedding)
├── mood_tracker.py      # 情绪追踪与自适应提示词
├── tools.py             # Function Calling 工具定义与执行器
├── eval_framework.py    # 独立评估脚本
├── config.yaml          # 全局配置
├── requirements.txt     # Python 依赖
├── model/               # Live2D 模型
├── pet_chroma_db/       # 向量数据库 (自动生成)
└── pet_memory.json      # 工作记忆 (自动生成)
```

## 📄 License

MIT License.

注：Live2D 引擎及相关模型版权归属于 Live2D Inc. 及原画师/模型师，请遵循官方最终用户许可协议。
