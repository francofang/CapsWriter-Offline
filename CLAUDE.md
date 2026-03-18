# CapsWriter-Offline macOS Port

## Fork 说明

本仓库是 [HaujetZhao/CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline) 的 fork，目标是将 CapsWriter-Offline 从 Windows 移植到 **macOS (Apple Silicon ARM64)**。

- **原项目**: https://github.com/HaujetZhao/CapsWriter-Offline
- **原版本**: v2.5-alpha
- **移植分支**: `macos-port`
- **目标平台**: macOS 15+ (Apple Silicon M4 Mac mini)

## 移植进度

### 第一阶段：服务端 (ASR 引擎) - 已完成

服务端 (`core_server.py`) 已可在 macOS 上正常启动，Fun-ASR-Nano 模型加载成功，Metal GPU 加速生效。

**改动的文件**：
- [`config_server.py`](config_server.py) - 默认模型切换为 `fun_asr_nano`，Vulkan 自动按平台禁用
- [`util/fun_asr_gguf/inference/core/model_manager.py`](util/fun_asr_gguf/inference/core/model_manager.py) - macOS 跳过 Vulkan 环境变量
- [`util/qwen_asr_gguf/inference/asr.py`](util/qwen_asr_gguf/inference/asr.py) - 同上
- [`.gitignore`](.gitignore) - 添加 `*.dylib` 忽略

**无需修改的文件**（已有跨平台支持）：
- `util/fun_asr_gguf/inference/llama.py` - 已有 darwin/dylib 分支
- `util/qwen_asr_gguf/inference/llama.py` - 同上
- `util/fun_asr_gguf/inference/encoder.py` - DmlExecutionProvider 检测安全
- `util/fun_asr_gguf/inference/ctc.py` - 同上
- `util/ui/tray.py` - 非 Windows 自动跳过

### 第二阶段：客户端 (录音 + 输入) - 已完成

客户端 (`core_client.py`) 已适配 macOS，可以初始化所有组件。

**改动的文件**：
- [`config_client.py`](config_client.py) - macOS 默认快捷键改为 `right_shift`（CapsLock 不可靠）
- [`core_client.py`](core_client.py) - macOS 权限检查改为提示授权辅助功能（不再强制 sudo）
- [`util/client/shortcut/key_mapper.py`](util/client/shortcut/key_mapper.py) - 添加 `pynput_key_to_name()` 跨平台函数，Win32 逻辑按平台隔离
- [`util/client/shortcut/shortcut_manager.py`](util/client/shortcut/shortcut_manager.py) - macOS 使用 `on_press`/`on_release` 替代 `win32_event_filter`
- [`util/llm/llm_get_selection.py`](util/llm/llm_get_selection.py) - `keyboard` → pynput，macOS 用 Cmd+C
- [`util/llm/llm_output_typing.py`](util/llm/llm_output_typing.py) - `keyboard.write()` → macOS 自动降级为剪贴板粘贴
- [`util/client/output/text_output.py`](util/client/output/text_output.py) - `_type_text()` macOS 分支用粘贴
- [`util/client/output/result_processor.py`](util/client/output/result_processor.py) - debug 函数 macOS 跳过

**已知限制**：
- macOS 上鼠标侧键 (x1/x2) 监听不支持（pynput 限制）
- macOS 上 `keyboard.write()` 流式打字不可用，自动降级为粘贴模式
- 需要在「系统设置 → 隐私与安全 → 辅助功能」中授权终端应用

### 第三阶段：录音悬浮提示窗 - 已完成

macOS 上按住快捷键录音时，屏幕底部弹出悬浮窗作为视觉反馈（类似系统听写功能）。

**新增文件**：
- [`util/client/ui/recording_overlay.py`](util/client/ui/recording_overlay.py) - 录音悬浮提示窗（Tkinter subprocess 实现，圆角半透明窗口，红点呼吸动画）

**改动的文件**：
- [`util/client/shortcut/task.py`](util/client/shortcut/task.py) - `launch()`/`finish()`/`cancel()` 中调用 overlay 的 show/hide
- [`util/client/startup.py`](util/client/startup.py) - macOS 上自动启动 overlay 子进程
- [`util/client/state.py`](util/client/state.py) - `ClientState` 增加 `recording_overlay` 属性
- [`util/client/cleanup.py`](util/client/cleanup.py) - 退出时清理 overlay 子进程

**技术说明**：
- 使用 subprocess + Tkinter 架构，避免与主线程 asyncio 事件循环冲突
- 通过 ctypes 调用 ObjC 运行时设置 `NSApplicationActivationPolicyAccessory`（不在 Dock 显示、不抢焦点）
- macOS 专属，Windows 上不启动（`sys.platform == 'darwin'` 守卫）

## macOS 运行前提

### 1. Homebrew 依赖

```bash
brew install portaudio protobuf ffmpeg git cmake python-tk@3.12
```

### 2. Python 虚拟环境

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install sherpa-onnx numpy gguf onnxruntime rich websockets watchdog pypinyin pystray Pillow markdown tkhtmlview srt
```

注意：
- 安装 `onnxruntime`（标准版），**不是** `onnxruntime-directml`（Windows 专用）
- `keyboard` 库在 macOS 上不能用，客户端阶段再用 `pynput` 替代

### 3. llama.cpp 动态库

从 https://github.com/ggml-org/llama.cpp/releases 下载最新的 macOS ARM64 版本：

```bash
# 示例：b8400 版本
curl -L -o /tmp/llama.tar.gz https://github.com/ggml-org/llama.cpp/releases/download/b8400/llama-b8400-bin-macos-arm64.tar.gz
cd /tmp && mkdir llama_extract && tar xzf llama.tar.gz -C llama_extract

# 复制到 3 个 bin 目录（需保留版本号符号链接）
for dest in \
  util/fun_asr_gguf/inference/bin \
  util/qwen_asr_gguf/inference/bin \
  util/llama/bin; do
  cp -a /tmp/llama_extract/llama-b8400/libggml*.dylib "$dest/"
  cp -a /tmp/llama_extract/llama-b8400/libllama*.dylib "$dest/"
done
```

必须保留带版本号的文件（如 `libggml-cpu.0.9.7.dylib`）和对应的符号链接（如 `libggml-cpu.0.dylib` → `libggml-cpu.0.9.7.dylib`），因为 dylib 之间通过 `@rpath` 引用版本号名称。

### 4. 模型文件

从 https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models 下载：

- **Fun-ASR-Nano-GGUF**（当前默认）→ 解压到 `models/Fun-ASR-Nano/Fun-ASR-Nano-GGUF/`
  - `Fun-ASR-Nano-Encoder-Adaptor.int4.onnx`
  - `Fun-ASR-Nano-CTC.int4.onnx`
  - `Fun-ASR-Nano-Decoder.q5_k.gguf`
  - `tokens.txt`

- **Qwen3-ASR**（可选）→ 解压到 `models/Qwen3-ASR/Qwen3-ASR-1.7B/`

### 5. 启动服务端

```bash
cd CapsWriter-Offline
source ../venv/bin/activate
python core_server.py
```

看到 `开始服务` 即表示启动成功。Metal GPU 加速自动生效（M 系列芯片）。

## 原项目架构 (参考)

### C/S 架构
- **Server** (`core_server.py`): WebSocket 主进程 + 独立识别子进程（防止 CPU 密集的推理阻塞网络心跳）
- **Client** (`core_client.py`): 全局快捷键监听、录音采集、结果上屏、LLM 润色

### 识别链路
Client 按住快捷键 → 录音流式发送 → Server ONNX 编码 + GGUF LLM 解码 → 返回文本 → Client 热词校正 + LLM 润色 → 上屏

### 关键路径
- **配置**: `config_server.py` / `config_client.py`
- **热词**: `hot.txt`（音素 RAG）、`hot-rule.txt`（正则替换）、`hot-rectify.txt`（历史修正）
- **LLM 角色**: `LLM/*.py`（支持 Ollama/OpenAI/DeepSeek/Claude/Gemini 等）
- **模型引擎**: `util/fun_asr_gguf/`（ONNX + llama.cpp 混合）、`util/qwen_asr_gguf/`
- **日志**: `logs/server.log` & `logs/client.log`
