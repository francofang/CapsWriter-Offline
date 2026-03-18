# CapsWriter-Offline macOS Port

> **CapsWriter-Offline 的 macOS (Apple Silicon) 移植版，按一下右 Shift 说话，再按一下就上屏。完全离线，Metal GPU 加速。**

本仓库是 [HaujetZhao/CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline) v2.5-alpha 的 fork，将原本仅支持 Windows 的语音输入工具移植到了 **macOS (Apple Silicon)**。

原项目因底层 `keyboard` 库不支持 macOS、以及 Vulkan/DirectML 显卡加速仅限 Windows 等原因，无法在 Mac 上运行。本 fork 逐一解决了这些问题，使其在 M 系列芯片 Mac 上完整可用。


## 移植了什么

| 改动领域 | 原版 (Windows) | macOS 移植版 |
|---------|---------------|-------------|
| GPU 加速 | Vulkan / DirectML | Metal（自动生效） |
| 全局快捷键 | `keyboard` 库 + Win32 API | `pynput` + on_press/on_release |
| 默认快捷键 | CapsLock / 鼠标侧键 X2 | 右 Shift（CapsLock 在 macOS 上不可靠） |
| 文字上屏 | `keyboard.write()` 流式打字 | 剪贴板粘贴（Cmd+V） |
| 选中文字读取 | Ctrl+C | Cmd+C |
| 权限模型 | 管理员权限 / sudo | 辅助功能授权（系统设置） |
| 动态库 | `.dll` | `.dylib`（llama.cpp macOS ARM64） |
| 鼠标侧键 | 支持 X1/X2 | 不支持（pynput 限制） |

核心识别逻辑（ONNX 编码 + llama.cpp 解码）、WebSocket 通信、热词系统、LLM 角色等**完全不变**，与原版行为一致。


## 安装指南

> 以下步骤在 macOS 15+ / Apple Silicon (M1–M4) 上验证通过。

### 1. 安装 Homebrew 依赖

```bash
brew install portaudio protobuf ffmpeg git cmake python-tk@3.12
```

### 2. 克隆仓库

```bash
cd ~/Projects
git clone -b macos-port https://github.com/francofang/CapsWriter-Offline.git capswriter-mac
```

### 3. 创建 Python 虚拟环境

```bash
cd ~/Projects/capswriter-mac
python3.12 -m venv venv
source venv/bin/activate
```

安装依赖（注意：macOS 用 `onnxruntime`，不是 Windows 的 `onnxruntime-directml`）：

```bash
pip install sherpa-onnx numpy gguf onnxruntime rich websockets watchdog \
    pypinyin pystray Pillow markdown tkhtmlview srt pynput pyclip sounddevice
```

### 4. 下载 llama.cpp 动态库

从 [llama.cpp Releases](https://github.com/ggml-org/llama.cpp/releases) 下载最新的 macOS ARM64 版本：

```bash
# 以 b8400 为例，请替换为最新版本号
VERSION=b8400
curl -L -o /tmp/llama.tar.gz \
  "https://github.com/ggml-org/llama.cpp/releases/download/${VERSION}/llama-${VERSION}-bin-macos-arm64.tar.gz"

cd /tmp && mkdir -p llama_extract && tar xzf llama.tar.gz -C llama_extract

# 复制到项目的 3 个 bin 目录
cd ~/Projects/capswriter-mac/CapsWriter-Offline
for dest in \
  util/fun_asr_gguf/inference/bin \
  util/qwen_asr_gguf/inference/bin \
  util/llama/bin; do
  cp -a /tmp/llama_extract/llama-${VERSION}/libggml*.dylib "$dest/"
  cp -a /tmp/llama_extract/llama-${VERSION}/libllama*.dylib "$dest/"
done
```

> **重要**：必须保留带版本号的文件（如 `libggml-cpu.0.9.7.dylib`）和符号链接（如 `libggml-cpu.0.dylib`），dylib 之间通过 `@rpath` 互相引用。

### 5. 下载模型文件

从 [Models Release](https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models) 下载模型：

**Qwen3-ASR-1.7B**（推荐，中英混合识别更好）：
```
models/Qwen3-ASR/Qwen3-ASR-1.7B/
├── qwen3_asr_encoder_frontend.fp16.onnx
├── qwen3_asr_encoder_backend.fp16.onnx
└── qwen3_asr_llm.q4_k.gguf
```

**Fun-ASR-Nano-GGUF**（更轻量）：
```
models/Fun-ASR-Nano/Fun-ASR-Nano-GGUF/
├── Fun-ASR-Nano-Encoder-Adaptor.int4.onnx
├── Fun-ASR-Nano-CTC.int4.onnx
├── Fun-ASR-Nano-Decoder.q5_k.gguf
└── tokens.txt
```

### 6. 授权辅助功能权限

**系统设置 → 隐私与安全性 → 辅助功能**，将你使用的终端应用（Terminal.app / iTerm2 / Warp 等）添加到允许列表。

这是 macOS 全局键盘监听的必要权限。


## 使用方法

### 一键启动

双击 `start-capswriter.command`，会在 Terminal 的同一窗口开两个 tab：
- Tab 1：服务端（ASR 引擎）
- Tab 2：客户端（等待 8 秒后自动启动）

### 分开启动

```bash
# 终端 Tab 1：启动服务端
cd ~/Projects/capswriter-mac/CapsWriter-Offline
source ../venv/bin/activate
python core_server.py

# 终端 Tab 2：启动客户端（等服务端显示「开始服务」后）
cd ~/Projects/capswriter-mac/CapsWriter-Offline
source ../venv/bin/activate
python core_client.py
```

也可以直接双击 `start-server.command` 和 `start-client.command` 分别启动。

### 开始语音输入

服务端显示「开始服务」、客户端连接成功后：

1. 按一下 **右 Shift** → 开始录音
2. 说话
3. 再按一下 **右 Shift** → 结束录音，识别结果自动粘贴到光标位置


## 配置说明

所有配置在项目根目录的两个文件中：

### 切换模型（`config_server.py`）

```python
# 语音模型选择：'fun_asr_nano', 'sensevoice', 'paraformer', 'qwen_asr'
model_type = 'qwen_asr'       # 当前默认，中英混合好
# model_type = 'fun_asr_nano' # 更轻量，纯中文也很好
```

### 切换录音模式（`config_client.py`）

```python
'hold_mode': False,  # 当前：单击模式（按一下开始，再按一下结束）
'hold_mode': True,   # 可选：按住模式（按住录音，松开结束）
```

### 切换快捷键（`config_client.py`）

```python
'key': 'shift_r',   # 当前：右 Shift
# 其他可选：'f12', 'ctrl_r', 'alt_r' 等（见文件末尾的完整按键列表）
```

### LLM 角色

在 `LLM/` 目录下配置角色文件，支持 Ollama 本地模型或在线 API（DeepSeek、Claude、Gemini 等）。录音时开头说角色名即可触发，如「翻译，今天天气好」。


## 已知限制

- **鼠标侧键不可用**：pynput 在 macOS 上不支持 X1/X2 监听
- **无流式打字**：`keyboard.write()` 在 macOS 不可用，文字通过剪贴板粘贴上屏（会短暂覆盖剪贴板内容，之后自动恢复）
- **CapsLock 不可靠**：macOS 对 CapsLock 有特殊处理（长按才触发），因此默认改为右 Shift
- **需要辅助功能权限**：每次更换终端应用都需要重新授权


## 致谢

- 原项目 [HaujetZhao/CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline) — 感谢作者开发了如此出色的离线语音输入工具
- [llama.cpp](https://github.com/ggml-org/llama.cpp) — GGUF 模型推理引擎，Metal GPU 加速
- [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx) / [FunASR](https://github.com/alibaba-damo-academy/FunASR) — ASR 模型框架
- 移植过程使用 Claude Code 辅助完成
