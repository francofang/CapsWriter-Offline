# CHANGELOG - macOS 移植记录

## 第一阶段：服务端适配 (2026-03-18)

### 目标
让 ASR 服务端 (`core_server.py`) 在 M4 Mac mini (macOS, Apple Silicon ARM64) 上正常运行。

### 结果
**成功** - 服务端可正常启动，Fun-ASR-Nano 模型在 7.49 秒内加载完成，Metal GPU 加速生效，WebSocket 监听 `0.0.0.0:6016`。

---

### 修改的文件

#### `config_server.py`
- **改动**: `model_type` 从 `'qwen_asr'` 改为 `'fun_asr_nano'`
  - **原因**: Qwen3-ASR 模型文件未下载，Fun-ASR-Nano 模型已就位
- **改动**: 添加 `import sys` 和 `_platform = sys.platform`
- **改动**: `FunASRNanoGGUFArgs.vulkan_enable` 和 `Qwen3ASRGGUFArgs.vulkan_enable` 从 `True` 改为 `_platform != 'darwin'`
  - **原因**: macOS 上 llama.cpp 自动使用 Metal 加速，不需要 Vulkan；设置 Vulkan 环境变量可能干扰 Metal 初始化

#### `util/fun_asr_gguf/inference/core/model_manager.py`
- **改动**: Vulkan 环境变量设置（`VK_ICD_FILENAMES`、`GGML_VK_DISABLE_F16`）包裹在 `if sys.platform != 'darwin':` 判断中
  - **原因**: 这些环境变量在 macOS 上无意义且可能产生副作用

#### `util/qwen_asr_gguf/inference/asr.py`
- **改动**: 同上，Vulkan 环境变量设置加平台判断
  - **原因**: 同上

#### `.gitignore`
- **改动**: 添加 `*.dylib` 到忽略列表
  - **原因**: llama.cpp 动态库是平台相关的二进制文件，需按平台下载，不应提交到 git

#### `CLAUDE.md`
- **改动**: 补充 macOS 开发环境说明，改为 macOS port fork 的项目文档

### 无需修改的文件

以下文件已有跨平台支持，无需改动：

- **`util/fun_asr_gguf/inference/llama.py`** (第 183-194 行): 已有 `sys.platform == "darwin"` 分支，正确加载 `.dylib` 文件
- **`util/qwen_asr_gguf/inference/llama.py`**: 同上
- **`util/fun_asr_gguf/inference/encoder.py`** (第 95-97 行): ONNX provider 选择已做安全检测 `'DmlExecutionProvider' in onnxruntime.get_available_providers()`，macOS 上自动 fallback 到 CPU
- **`util/fun_asr_gguf/inference/ctc.py`** (第 38-40 行): 同上
- **`util/qwen_asr_gguf/inference/encoder.py`** (第 135-137 行): 同上
- **`util/ui/tray.py`** (第 52-55 行): `_check_tray_available()` 在非 Windows 系统上返回 False，自动跳过
- **`util/tools/empty_working_set.py`**: 使用 `ctypes.windll` 但只在函数体内，不在导入时执行；调用处已有 `if system() == 'Windows':` 保护

---

### 安装的依赖

#### Homebrew
```
portaudio, protobuf, ffmpeg, git, cmake, python-tk@3.12
```

`python-tk@3.12` 是运行中发现缺失后补装的（见下方报错记录）。

#### Python (venv, pip)
```
sherpa-onnx, numpy, gguf, onnxruntime, rich, websockets, watchdog, pypinyin, pystray, Pillow, markdown, tkhtmlview, srt
```

与原项目 `requirements-server.txt` 的区别：
- `onnxruntime-directml` → `onnxruntime`（DirectML 是 Windows 专用，macOS 用标准版）
- 额外安装了 `srt`（原 requirements 未列出但代码 import 了）

---

### 遇到的报错和解决方法

#### 1. llama.cpp dylib 加载失败：找不到版本号文件

**报错**:
```
dlopen(libggml.dylib): Library not loaded: @rpath/libggml-cpu.0.dylib
```

**原因**: 最初只复制了不带版本号的文件（如 `libggml.dylib`），但 dylib 之间通过 `@rpath` 引用带版本号的名称（如 `libggml-cpu.0.dylib` → `libggml-cpu.0.9.7.dylib`）。

**解决**: 使用 `cp -a` 复制所有 dylib 文件，保留版本号文件和对应的符号链接：
```
libggml-cpu.0.9.7.dylib     ← 实际文件
libggml-cpu.0.dylib         → libggml-cpu.0.9.7.dylib (symlink)
libggml-cpu.dylib           → libggml-cpu.0.dylib (symlink)
```

#### 2. tkinter 未安装

**报错**:
```
ModuleNotFoundError: No module named '_tkinter'
```

**原因**: Homebrew 安装的 Python 3.12 默认不包含 tkinter，需要额外安装。

**解决**:
```bash
brew install python-tk@3.12
```

#### 3. srt 模块缺失

**报错**:
```
ModuleNotFoundError: No module named 'srt'
```

**原因**: `util/fun_asr_gguf/inference/srt_utils.py` 依赖 `srt` 库，但 `requirements-server.txt` 中未列出。

**解决**:
```bash
pip install srt
```

---

### llama.cpp 二进制文件

- **版本**: b8400
- **来源**: https://github.com/ggml-org/llama.cpp/releases/download/b8400/llama-b8400-bin-macos-arm64.tar.gz
- **放置位置** (3 个目录):
  - `util/fun_asr_gguf/inference/bin/`
  - `util/qwen_asr_gguf/inference/bin/`
  - `util/llama/bin/`
- **所需文件**: `libggml*.dylib`, `libllama*.dylib`（包含 Metal、CPU、BLAS 等后端）
- **Metal 着色器**: 已嵌入 `libggml-metal.dylib` 中，无需单独的 `.metallib` 文件

---

### 服务端启动日志摘要

```
托盘功能不可用，跳过启用                          ← macOS 不支持 Windows 托盘，自动跳过
模型文件检查通过 (fun_asr_nano)
[Encoder] 加载模型: Fun-ASR-Nano-Encoder-Adaptor.int4.onnx (Providers: ['CPUExecutionProvider'])
[CTC] 加载模型: Fun-ASR-Nano-CTC.int4.onnx (Providers: ['CPUExecutionProvider'])
ggml_metal_device_init: GPU name: MTL0                ← Metal 后端成功初始化
ggml_metal_device_init: GPU family: MTLGPUFamilyApple9
ggml_metal_device_init: has unified memory = true
ggml_metal_device_init: has bfloat = true
llama_model_load_from_file_impl: using device MTL0 (Apple M4) - 12123 MiB free
语音模型载入完成 (fun_asr_nano)
模型加载耗时 7.49s
开始服务                                            ← 服务启动成功
```
