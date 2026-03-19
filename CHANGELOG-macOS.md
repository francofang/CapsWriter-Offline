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
llama_metal_device_init: using device MTL0 (Apple M4) - 12123 MiB free
语音模型载入完成 (fun_asr_nano)
模型加载耗时 7.49s
开始服务                                            ← 服务启动成功
```

---

## Tkinter 线程崩溃修复 (2026-03-19)

### 问题

客户端在 macOS 上使用时偶尔发生 Python crash（SIGABRT / SIGSEGV），macOS 弹出"Python 意外退出"提示。在 2026-03-18 至 2026-03-19 期间累计触发 **12 次崩溃**。

### 诊断过程

1. **收集 crash report**：检查 `~/Library/Logs/DiagnosticReports/Python-*.ips`，发现全部 12 次崩溃都与 Tkinter 相关
2. **分析崩溃栈**：三种崩溃类型均指向同一根因：
   - `EXC_CRASH` (SIGABRT) — `TkMacOSXMakeRealWindowExist` → `NSWindow initWithContentRect`
   - `EXC_BAD_ACCESS` (SIGSEGV) — `_tkinter` 模块
   - `EXC_BREAKPOINT` (SIGTRAP) — `_tkinter` 模块
3. **确认线程上下文**：崩溃发生在 Thread 17（`ToastManagerThread` 守护线程），而非主线程
4. **主线程在做什么**：`asyncio` 事件循环（`select_kqueue_control`）

### 根因

macOS 的 AppKit 框架**要求所有 NSWindow（GUI 窗口）操作必须在主线程（Thread 0）执行**。

原实现中 `ToastMessageManager` 在守护线程中调用 `tk.Tk()` + `mainloop()`。这在 Windows 上没问题，但在 macOS 上违反了 AppKit 的线程安全要求，导致随机崩溃。

### 修复方案

**在 macOS 上将 Tkinter 集成到主线程的 asyncio 事件循环中**，不使用独立的守护线程：

- `ToastMessageManager.__init__()` 检测平台，macOS 上调用 `_init_tk_mainthread()` 在主线程创建 `tk.Tk()`
- 通过 asyncio 任务（`_tk_update_loop`）周期性调用 `root.update()` 处理 Tk 事件，替代 `mainloop()`
- asyncio、Tkinter、pynput 键盘模拟全部在主线程运行，避免线程冲突
- Windows/Linux 保持原有的守护线程模式不变

> **曾尝试的方案（已放弃）**：将 asyncio 移到后台线程、Tkinter 在主线程运行 `mainloop()`。
> 但这导致 pynput 键盘模拟（`TSMGetInputSourceProperty`）也从后台线程调用，触发了新的 `dispatch_assert_queue` 崩溃。
> macOS 上 Tkinter 和 pynput 都需要主线程，因此最终选择了 asyncio `root.update()` 集成方案。

### 修改的文件

#### `util/ui/toast_manager.py`
- macOS 上不启动 `ToastManagerThread` 守护线程
- 新增 `_init_tk_mainthread()`：在主线程创建 `tk.Tk()` 并启动 asyncio 更新任务
- 新增 `_tk_update_loop()`：50Hz 周期调用 `root.update()` 驱动 Tk 事件
- `_on_close()` 增加 asyncio 任务取消逻辑

#### `util/common/lifecycle.py`
- `_register_signals()` 添加 `threading.main_thread()` 检查
- 非主线程跳过 `signal.signal()` 注册（避免 `ValueError`），作为安全防护

---

## 个人配置文件从 Git 跟踪移除 (2026-03-19)

### 问题

`hot.txt`、`hot-rectify.txt`、`hot-rule.txt` 包含用户个人热词和纠错规则，被 git 跟踪后会推送到远程仓库，泄露个人数据。

### 修改

1. 使用 `git rm --cached` 将三个文件从 git 跟踪中移除（本地文件保留）
2. 在 `.gitignore` 中添加这三个文件名
3. 创建 `.example` 模板文件供其他用户参考格式：
   - `hot.txt.example` — 热词文件模板（仅保留注释说明）
   - `hot-rectify.txt.example` — 纠错文件模板（保留格式示例）
   - `hot-rule.txt.example` — 正则规则文件模板（保留通用规则）
