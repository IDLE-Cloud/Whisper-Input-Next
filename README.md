# Whisper-Input-Windows

<p align="center">
  <img src="docs/whisper_claudecode.png" alt="Project Poster" />
</p>

<p align="center">
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.10+-green.svg" alt="Python" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License" />
  </a>
  <a href="https://github.com/Mor-Li/Whisper-Input-Next">
    <img src="https://img.shields.io/badge/upstream-Mor--Li%2FWhisper--Input--Next-orange.svg" alt="Upstream" />
  </a>
</p>

基于 [Mor-Li/Whisper-Input-Next](https://github.com/Mor-Li/Whisper-Input-Next) 的 **Windows 完整适配版本**，在原版基础上增加了实时流式输出、润色模式、浮动控制栏等功能。

---

## ✨ 功能特性

### Windows 支持
- 原版仅支持 macOS，本 fork 完整适配 Windows 10/11
- 浮动预览窗口（tkinter 实现，`WS_EX_NOACTIVATE` 不抢焦点）
- 系统托盘状态改为控制台输出，不依赖 macOS AppKit
- 自动检测 Windows 常见麦克风设备名（Realtek、USB Mic 等）
- 修复 pynput 在 Windows 下 `Key.ctrl_l` 与 `Key.ctrl` 不相等的问题
- 粘贴前自动还原目标窗口焦点，后台持续跟踪前台窗口

### 两种语音输入模式

| 快捷键 | 模式 | 说明 |
|--------|------|------|
| **Ctrl+Q** | 快速模式 | 说话时实时输出，definite 文字立即出现在光标处 |
| **Ctrl+空格** | 润色模式 | 说完整段后交 LLM 整理成书面语再输出 |

### 浮动控制栏
- 屏幕右下角常驻工具栏，鼠标点击即可控制
- 点击不抢焦点，目标窗口光标位置保持不变
- 可拖动，两个按钮：`🎤 快速` / `✏️ 润色`

### 豆包 Seed-ASR 2.0 流式识别
- 边说边识别，definite 段实时输入到目标应用
- pending 文字显示在浮动预览窗口
- 支持新版火山引擎控制台的单 Key 认证（`X-Api-Key`）

### 润色模式
- 说完整段按 Ctrl+空格 结束，全文发送给 LLM 整理
- 支持任意 OpenAI 兼容 API（DeepSeek、Qwen、SiliconFlow 等）
- 支持 Anthropic API（Claude 系列）
- 自动去除语气词、重复、口语化表达，输出书面语

---

## 📦 快速开始

### 环境要求
- Windows 10/11
- Python 3.10+

### 安装步骤

**1. 克隆仓库**
```bash
git clone https://github.com/IDLE-Cloud/Whisper-Input-Next.git
cd Whisper-Input-Next
```

**2. 创建虚拟环境**
```bash
python -m venv .venv
.venv\Scripts\activate        # CMD
# 或
source .venv/Scripts/activate  # Git Bash
```

**3. 安装依赖**
```bash
pip install -r requirements-windows.txt
```

**4. 配置 .env**
```bash
cp env.example .env
```

编辑 `.env`，至少填入以下内容：

```ini
# 豆包 Seed-ASR 2.0（新版控制台，推荐）
# 获取地址：https://console.volcengine.com/speech/app
DOUBAO_API_KEY=your-api-key-here
TRANSCRIPTION_SERVICE=doubao
SYSTEM_PLATFORM=win

# 快捷键配置（可自定义，避免与常用软件冲突）
TRANSCRIPTIONS_BUTTON=q       # Ctrl+Q 快速模式
TRANSLATIONS_BUTTON=ctrl
```

**5. 启动**
```bash
python main.py
```

---

## ⚙️ 配置说明

### 豆包 API Key

火山引擎控制台有新旧两种认证方式，本版本均支持：

| 控制台版本 | 配置项 |
|-----------|--------|
| 新版（推荐） | `DOUBAO_API_KEY=xxx` |
| 旧版 | `DOUBAO_APP_KEY=xxx` + `DOUBAO_ACCESS_KEY=xxx` |

### 润色模式配置（可选）

```ini
# 支持 OpenAI 兼容格式（DeepSeek、Qwen 等）
POLISH_PROVIDER=openai
POLISH_API_KEY=sk-xxx
POLISH_BASE_URL=https://api.deepseek.com
POLISH_MODEL=deepseek-chat

# 或 Anthropic 格式（Claude）
# POLISH_PROVIDER=anthropic
# POLISH_API_KEY=sk-ant-xxx
# POLISH_MODEL=claude-haiku-4-5-20251001
```

### 完整配置项

```ini
# ASR 服务
DOUBAO_API_KEY=            # 豆包 API Key（新版控制台）
DOUBAO_APP_KEY=            # APP ID（旧版控制台）
DOUBAO_ACCESS_KEY=         # Access Token（旧版控制台）
TRANSCRIPTION_SERVICE=doubao

# 快捷键
TRANSCRIPTIONS_BUTTON=q    # Ctrl+Q 快速模式
TRANSLATIONS_BUTTON=ctrl
SYSTEM_PLATFORM=win        # 必须设置为 win

# 功能开关
CONVERT_TO_SIMPLIFIED=false
ADD_SYMBOL=false

# 润色模式 LLM
POLISH_PROVIDER=openai
POLISH_API_KEY=
POLISH_BASE_URL=
POLISH_MODEL=
```

---

## 🎮 使用方式

### 快捷键

| 快捷键 | 操作 |
|--------|------|
| `Ctrl+Q` | 开始 / 停止快速录音（实时流式输出） |
| `Ctrl+空格` | 开始 / 停止润色录音（说完整段后 LLM 润色输出） |

### 控制栏按钮

屏幕右下角浮动工具栏，鼠标点击与快捷键等效：
- `🎤 快速`：开始 / 停止快速模式
- `✏️ 润色`：开始 / 停止润色模式

### 焦点跟踪

无需担心焦点问题：
- 程序后台持续监控前台窗口
- 按 Ctrl+Q 时自动记录目标窗口
- 粘贴前自动还原焦点，文字输入到正确位置

---

## 🗂️ 项目结构

```
src/
├── audio/
│   └── recorder.py          # 录音器（含 Windows 设备检测）
├── keyboard/
│   ├── listener.py          # 键盘监听（含焦点跟踪、粘贴还原）
│   └── inputState.py        # 状态枚举
├── llm/
│   └── polish.py            # 润色处理器（OpenAI / Anthropic）
├── transcription/
│   └── doubao_streaming.py  # 豆包流式 ASR（含新版 API Key）
└── ui/
    ├── control_bar.py       # 浮动控制栏（tkinter）
    ├── floating_preview.py  # 浮动预览窗口（tkinter / AppKit）
    └── status_bar.py        # 状态栏（控制台 / macOS 系统托盘）
```

---

## 📝 与上游的主要差异

| 功能 | 上游 (Mor-Li) | 本版本 |
|------|--------------|--------|
| Windows 支持 | 开发中 | 完整支持 |
| 平台 UI | macOS AppKit | tkinter（Windows/macOS 均可） |
| 流式输出时机 | 说完才输出 | definite 段实时输出 |
| 润色模式 | 无 | Ctrl+空格，支持多种 LLM |
| 控制栏 | 无 | 浮动工具栏，鼠标操控 |
| 豆包认证 | 仅旧版双 Key | 新旧版均支持 |
| 焦点管理 | 无 | 自动跟踪并还原 |

---

## 🙏 致谢

- [Mor-Li/Whisper-Input-Next](https://github.com/Mor-Li/Whisper-Input-Next) — 上游项目
- [ErlichLiu/Whisper-Input](https://github.com/ErlichLiu/Whisper-Input) — 原始项目
- [ByteDance/Volcengine](https://www.volcengine.com/) — 豆包 Seed-ASR 2.0

---

**⭐ 如果这个项目对你有帮助，欢迎 Star 支持！**
