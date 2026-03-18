#!/bin/bash
# CapsWriter-Offline macOS 快捷操作安装脚本
# 将 Automator Quick Action (.workflow) 安装到系统服务目录

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICES_DIR="$HOME/Library/Services"

echo "=== CapsWriter 快捷操作安装 ==="
echo ""

# 安装 Add Hotword
if [ -d "$SCRIPT_DIR/Add Hotword.workflow" ]; then
    cp -R "$SCRIPT_DIR/Add Hotword.workflow" "$SERVICES_DIR/"
    echo "✓ 已安装：Add Hotword（添加热词）"
else
    echo "✗ 未找到 Add Hotword.workflow"
fi

# 安装 Add Rectify
if [ -d "$SCRIPT_DIR/Add Rectify.workflow" ]; then
    cp -R "$SCRIPT_DIR/Add Rectify.workflow" "$SERVICES_DIR/"
    echo "✓ 已安装：Add Rectify（添加纠错）"
else
    echo "✗ 未找到 Add Rectify.workflow"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "下一步：绑定快捷键"
echo "  1. 打开「系统设置 → 键盘 → 键盘快捷键 → 服务 → 文本」"
echo "  2. 找到 Add Hotword，绑定快捷键（建议 Cmd+Shift+H）"
echo "  3. 找到 Add Rectify，绑定快捷键（建议 Cmd+Shift+R）"
echo ""
echo "使用方法："
echo "  添加热词：选中文字 → 按快捷键 → 自动添加到 hot.txt"
echo "  添加纠错：选中错误文字 → 按快捷键 → 输入正确文字 → 写入 hot-rectify.txt"
