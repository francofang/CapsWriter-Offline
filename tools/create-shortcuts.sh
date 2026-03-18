#!/bin/bash
# CapsWriter-Offline macOS 快捷操作创建脚本
# 使用 AppleScript 通过 Automator.app 创建 Quick Action

CAPSWRITER_DIR="$HOME/Projects/capswriter-mac/CapsWriter-Offline"

echo "=== 创建 CapsWriter 快捷操作 ==="
echo ""

# ---- 1. 添加热词 ----
echo "正在创建「CapsWriter Add Hotword」..."

osascript <<'APPLESCRIPT'
tell application "Automator"
	-- 创建新的 Quick Action
	set newDoc to make new workflow with properties {name:"CapsWriter Add Hotword", workflow type:service workflow}

	-- 关闭（保存到默认位置 ~/Library/Services/）
	save newDoc
	close newDoc
end tell
APPLESCRIPT

# 检查是否创建成功
if [ -d "$HOME/Library/Services/CapsWriter Add Hotword.workflow" ]; then
    echo "✓ workflow 已创建"
else
    echo "✗ 创建失败，请手动在 Automator 中创建"
    echo "  提示：选择「Quick Action」，添加「Run Shell Script」"
fi

# ---- 2. 添加纠错 ----
echo "正在创建「CapsWriter Add Rectify」..."

osascript <<'APPLESCRIPT'
tell application "Automator"
	set newDoc to make new workflow with properties {name:"CapsWriter Add Rectify", workflow type:service workflow}
	save newDoc
	close newDoc
end tell
APPLESCRIPT

if [ -d "$HOME/Library/Services/CapsWriter Add Rectify.workflow" ]; then
    echo "✓ workflow 已创建"
else
    echo "✗ 创建失败，请手动在 Automator 中创建"
fi

# 退出 Automator
osascript -e 'tell application "Automator" to quit'

echo ""
echo "=== 创建完成 ==="
echo ""
echo "但是 Automator 的 AppleScript 接口无法添加 Shell 脚本动作。"
echo "请手动完成以下步骤："
echo ""
echo "【添加热词 workflow】"
echo "  1. 双击打开 ~/Library/Services/CapsWriter Add Hotword.workflow"
echo "  2. 顶部设置：Workflow receives [text] in [any application]"
echo "  3. 搜索并拖入「Run Shell Script」动作"
echo "  4. Shell 选 /bin/bash，Pass input 选 [to stdin]"
echo "  5. 粘贴以下脚本："
echo ""
cat << 'SCRIPT'
HOT_FILE="$HOME/Projects/capswriter-mac/CapsWriter-Offline/hot.txt"
HOTWORD=$(cat | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
[ -z "$HOTWORD" ] && exit 0
echo "$HOTWORD" >> "$HOT_FILE"
osascript -e "display notification \"已添加：$HOTWORD\" with title \"CapsWriter 热词\""
SCRIPT
echo ""
echo "  6. 保存（Cmd+S）"
echo ""
echo "【添加纠错 workflow】"
echo "  1. 双击打开 ~/Library/Services/CapsWriter Add Rectify.workflow"
echo "  2. 顶部设置：Workflow receives [text] in [any application]"
echo "  3. 搜索并拖入「Run Shell Script」动作"
echo "  4. Shell 选 /bin/bash，Pass input 选 [to stdin]"
echo "  5. 粘贴以下脚本："
echo ""
cat << 'SCRIPT'
RECTIFY_FILE="$HOME/Projects/capswriter-mac/CapsWriter-Offline/hot-rectify.txt"
ORIGINAL=$(cat | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
[ -z "$ORIGINAL" ] && exit 0
CORRECTED=$(osascript -e "
set dialogResult to display dialog \"原始文本：$ORIGINAL\" & return & return & \"请输入正确的文字：\" default answer \"\" with title \"CapsWriter 纠错\" buttons {\"取消\", \"确认\"} default button \"确认\"
if button returned of dialogResult is \"确认\" then
    return text returned of dialogResult
end if
" 2>/dev/null)
[ -z "$CORRECTED" ] && exit 0
printf '\n%s\n%s\n---\n' "$ORIGINAL" "$CORRECTED" >> "$RECTIFY_FILE"
osascript -e "display notification \"$ORIGINAL → $CORRECTED\" with title \"CapsWriter 纠错\""
SCRIPT
echo ""
echo "  6. 保存（Cmd+S）"
echo ""
echo "【绑定快捷键】"
echo "  系统设置 → 键盘 → 键盘快捷键 → 服务 → 文本"
echo "  找到 CapsWriter Add Hotword → 绑定 Cmd+Shift+H"
echo "  找到 CapsWriter Add Rectify → 绑定 Cmd+Shift+R"
