#!/bin/bash

if pgrep -f "core_server.py" > /dev/null; then
    pkill -9 -f "core_client.py"
    pkill -9 -f "core_server.py"
    osascript -e 'display notification "Server 和 Client 已关闭" with title "CapsWriter" sound name "Purr"' &
    # Python 被杀后，启动命令末尾的 "; exit" 会让 shell 自动退出
    # 等 shell 退出后关闭窗口，不会弹 Terminate 确认框
    (sleep 1.5 && osascript -e 'tell application "Terminal" to close every window saving no') &
    exit 0
else
    osascript -e '
    tell application "Terminal"
        activate
        do script "cd ~/Projects/capswriter-mac && source venv/bin/activate && cd CapsWriter-Offline && python core_server.py; exit"
        delay 1
        tell application "System Events" to keystroke "t" using command down
        delay 0.5
        do script "cd ~/Projects/capswriter-mac && source venv/bin/activate && cd CapsWriter-Offline && sleep 3 && python core_client.py; exit" in front window
    end tell
    '
fi