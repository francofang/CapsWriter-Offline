# Release 打包计划

> 目标：创建一个 GitHub Release，用户下载后运行 `setup.sh` + 双击 `start-capswriter.command` 即可使用。

## Release 包含内容

### 1. 代码包（`CapsWriter-Offline-macOS-vX.X.zip`）

打包整个 `CapsWriter-Offline/` 目录，**排除**以下内容：

```
排除项：
- models/          （模型文件太大，单独下载）
- logs/            （运行时生成）
- 20*/             （日记归档，运行时生成）
- __pycache__/     （Python 缓存）
- .git/            （版本控制）
- .claude/         （开发工具配置）
- .DS_Store        （macOS 系统文件）
- *.pyc            （编译缓存）
- venv/            （虚拟环境，用户自己创建）
- docs/PRIVATE-NOTES.md  （私有笔记）
```

**包含**以下关键文件：

```
包含项：
- *.py             （所有 Python 源码）
- util/            （工具模块）
- LLM/             （角色配置）
- tools/           （Quick Action workflow）
- assets/          （图标等资源）
- hot*.txt.example （热词模板）
- hot-server.txt   （服务端热词）
- start-*.command  （启动脚本）
- setup.sh         （一键安装脚本，需新建）
- README-macOS.md  （安装和使用指南）
- FEATURES-macOS.md（功能清单）
- requirements-*.txt（依赖列表）
```

### 2. llama.cpp 动态库（包含在代码包内）

从 llama.cpp releases 下载 macOS ARM64 版本的 dylib 文件，放入代码包的 3 个 bin 目录：

```
util/fun_asr_gguf/inference/bin/libggml*.dylib, libllama*.dylib
util/qwen_asr_gguf/inference/bin/libggml*.dylib, libllama*.dylib
util/llama/bin/libggml*.dylib, libllama*.dylib
```

> 注意：dylib 文件约 100MB，包含在代码包内。

### 3. 模型文件（单独下载）

用户从原项目的 [Models Release](https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models) 下载，解压到 `models/` 目录。

README 中已有详细的模型下载说明。

## 需要新建的文件

### `setup.sh` — 一键安装脚本

功能：
1. 检查 Homebrew 是否安装
2. 安装 Homebrew 依赖（portaudio, protobuf, ffmpeg, python-tk@3.12）
3. 创建 Python 虚拟环境（venv）
4. 安装 Python 依赖（pip install）
5. 复制 hot*.txt.example 为 hot*.txt（如果不存在）
6. 提示用户下载模型文件
7. 提示用户授权辅助功能权限

```bash
#!/bin/bash
set -e

echo "=== CapsWriter-Offline macOS 安装脚本 ==="

# 1. 检查 Homebrew
if ! command -v brew &>/dev/null; then
    echo "❌ 请先安装 Homebrew: https://brew.sh"
    exit 1
fi

# 2. 安装系统依赖
echo "📦 安装系统依赖..."
brew install portaudio protobuf ffmpeg python-tk@3.12

# 3. 创建虚拟环境
echo "🐍 创建 Python 虚拟环境..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."
python3.12 -m venv venv
source venv/bin/activate

# 4. 安装 Python 依赖
echo "📥 安装 Python 依赖..."
pip install --upgrade pip
pip install sherpa-onnx numpy gguf onnxruntime rich websockets watchdog \
    pypinyin pystray Pillow markdown tkhtmlview srt pynput pyclip \
    sounddevice colorama typer pyobjc-framework-Cocoa pyobjc-framework-Quartz

# 5. 初始化热词文件
cd CapsWriter-Offline
for f in hot.txt hot-rectify.txt hot-rule.txt; do
    if [ ! -f "$f" ] && [ -f "${f}.example" ]; then
        cp "${f}.example" "$f"
        echo "✅ 已创建 $f（从模板复制）"
    fi
done

echo ""
echo "=== 安装完成 ==="
echo ""
echo "⚠️  还需要手动完成以下步骤："
echo ""
echo "1. 下载模型文件："
echo "   https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models"
echo "   解压到 models/ 目录"
echo ""
echo "2. 授权辅助功能权限："
echo "   系统设置 → 隐私与安全性 → 辅助功能 → 添加 Terminal.app"
echo ""
echo "3. 双击 start-capswriter.command 启动"
```

### `zip_release.py` 的 macOS 适配（或新建打包脚本）

项目已有 `zip_release.py`，但它是为 Windows 打包设计的。需要新建一个 macOS 打包脚本，或者修改现有脚本添加 macOS 分支。

## 打包步骤（手动执行）

```bash
# 1. 确保代码是最新的
git checkout macos-port
git pull

# 2. 下载最新 llama.cpp dylib（如果还没有）
# 参考 README-macOS.md 的第 4 步

# 3. 运行打包脚本
python zip_release_macos.py
# 或者手动打包：
cd ~/Projects/capswriter-mac
zip -r CapsWriter-Offline-macOS-v2.5.zip CapsWriter-Offline/ \
    -x "CapsWriter-Offline/models/*" \
    -x "CapsWriter-Offline/.git/*" \
    -x "CapsWriter-Offline/__pycache__/*" \
    -x "CapsWriter-Offline/logs/*" \
    -x "CapsWriter-Offline/20*/*" \
    -x "CapsWriter-Offline/venv/*" \
    -x "CapsWriter-Offline/.claude/*" \
    -x "CapsWriter-Offline/.DS_Store" \
    -x "CapsWriter-Offline/docs/PRIVATE-NOTES.md"

# 4. 在 GitHub 创建 Release
#    - Tag: v2.5-macos
#    - Title: CapsWriter-Offline v2.5 macOS Port
#    - 上传 zip 文件
#    - Release notes 中说明需要单独下载模型文件
```

## 用户安装流程（最终效果）

```
1. 从 GitHub Release 下载 CapsWriter-Offline-macOS-v2.5.zip
2. 解压到任意目录（如 ~/Projects/capswriter-mac/）
3. 运行 setup.sh（一次性，安装依赖 + 创建 venv）
4. 下载模型文件，解压到 models/ 目录
5. 系统设置 → 辅助功能 → 授权 Terminal
6. 双击 start-capswriter.command 启动
7. 按右 Shift 说话，再按一下上屏
```
