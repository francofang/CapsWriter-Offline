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


## macOS 版的技术变更与新功能

### 键盘库替换：`keyboard` → `pynput`

原版使用 Python `keyboard` 库监听全局快捷键和模拟按键输入，该库依赖 Win32 API，无法在 macOS 上运行。macOS 移植版改用 `pynput`，通过 `on_press` / `on_release` 回调监听快捷键，通过 `pynput.keyboard.Controller` 模拟 Cmd+V 粘贴。

相关文件：`util/client/shortcut/shortcut_manager.py`、`util/client/shortcut/key_mapper.py`、`util/client/output/text_output.py`

### Tkinter 线程模型重构（修复 Python 崩溃）

原版在守护线程中运行 Tkinter 的 `tk.Tk()` + `mainloop()` 来显示 Toast 弹窗通知。在 macOS 上，AppKit 要求所有窗口操作必须在主线程执行，守护线程创建窗口会导致随机 SIGABRT / SIGSEGV 崩溃。

修复方案：macOS 上不再使用独立的 Tkinter 线程，而是在主线程创建 `tk.Tk()`，通过 asyncio 任务周期性调用 `root.update()` 驱动 Tk 事件循环，替代 `mainloop()`。这样 asyncio、Tkinter、pynput 都在主线程运行，避免线程冲突。Windows/Linux 保持原有的守护线程模式不变。

相关文件：`util/ui/toast_manager.py`、`util/common/lifecycle.py`

### 录音状态浮动指示器（macOS 新增）

录音时在鼠标光标上方显示一个小型半透明浮动窗口，带有绿色圆点流动动画（`●∙∙ 录音中`），录音结束后自动消失。即使 Terminal 最小化也能看到录音状态。

使用 PyObjC 创建 macOS 原生 `NSPanel`（`NSWindowStyleMaskNonactivatingPanel`），不会抢走输入焦点，不影响正在打字的应用。这是 macOS 原生语音输入法使用的相同技术。

相关文件：`util/ui/recording_indicator.py`

### 一键启动/关闭脚本（macOS 新增）

`start-capswriter.command` 是一个 toggle 开关：
- **第一次双击**：在 Terminal 中打开两个 tab，依次启动 Server 和 Client
- **再次双击**：关闭 Server 和 Client，自动关闭 Terminal 窗口（无需手动确认）

启动命令末尾附加 `; exit`，使 Python 进程结束后 shell 自动退出，避免关闭时弹出 "Terminate running processes?" 对话框。

相关文件：`start-capswriter.command`

### 热词/纠错添加方式（macOS 新增）

原版通过 Windows 托盘菜单添加热词和纠错记录。macOS 上托盘菜单不可用，改为 **Automator Quick Action（快捷操作）**：

- **Add Hotword**：弹出对话框，输入热词后自动追加到 `hot.txt`
- **Add Rectify**：弹出对话框，输入原文和修正文本后追加到 `hot-rectify.txt`

安装方式：双击 `tools/Add Hotword.workflow` 和 `tools/Add Rectify.workflow`，或运行 `tools/install-shortcuts.sh`。安装后可在「系统设置 → 键盘 → 键盘快捷键 → 服务」中为它们分配全局快捷键。

相关文件：`tools/Add Hotword.workflow`、`tools/Add Rectify.workflow`

### 文件监控冲突修复

原版的 `LLMFileWatcher` 和 `HotwordManager` 各自创建独立的 watchdog `Observer` 监控项目根目录，在 macOS FSEvents 下会触发重复监控冲突。修复后 `LLMFileWatcher` 仅监控 `LLM/` 目录，热词文件监控由 `HotwordManager` 统一负责。

相关文件：`util/llm/llm_watcher.py`


## 安装指南

> 以下步骤在 macOS 15+ / Apple Silicon (M1–M4) 上验证通过。

### 1. 安装 Homebrew 依赖

```bash
brew install portaudio protobuf ffmpeg git cmake python-tk@3.12
```

### 2. 克隆仓库

```bash
git clone -b macos-port https://github.com/francofang/CapsWriter-Offline.git capswriter-mac
cd capswriter-mac
```

### 3. 创建 Python 虚拟环境

在仓库根目录下执行：

```bash
python3.12 -m venv venv
source venv/bin/activate
```

安装依赖（使用 macOS 专用依赖文件）：

```bash
pip install -r requirements-macos.txt
```

> 注意：macOS 用 `onnxruntime`（标准版），不是 Windows 的 `onnxruntime-directml`。原项目的 `requirements-server.txt` 和 `requirements-client.txt` 是 Windows 取向的，macOS 请使用 `requirements-macos.txt`。

### 4. 下载 llama.cpp 动态库

从 [llama.cpp Releases](https://github.com/ggml-org/llama.cpp/releases) 下载最新的 macOS ARM64 版本：

```bash
# 以 b8400 为例，请替换为最新版本号
VERSION=b8400
curl -L -o /tmp/llama.tar.gz \
  "https://github.com/ggml-org/llama.cpp/releases/download/${VERSION}/llama-${VERSION}-bin-macos-arm64.tar.gz"

cd /tmp && mkdir -p llama_extract && tar xzf llama.tar.gz -C llama_extract

# 回到仓库根目录，复制到项目的 3 个 bin 目录
cd capswriter-mac  # 如果还在仓库根目录则跳过此行
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
# 终端 Tab 1：启动服务端（在仓库根目录执行）
source venv/bin/activate
python core_server.py

# 终端 Tab 2：启动客户端（等服务端显示「开始服务」后）
source venv/bin/activate
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
