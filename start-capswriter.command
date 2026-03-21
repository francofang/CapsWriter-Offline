#!/bin/bash

if pgrep -f "core_server.py" > /dev/null; then
    # 先获取 server 主进程的 PID，用 PGID 杀掉整个进程组（含 ASR 子进程）
    SERVER_PID=$(pgrep -f "core_server.py" | head -1)
    pkill -9 -f "core_client.py"
    if [ -n "$SERVER_PID" ]; then
        kill -9 -"$SERVER_PID" 2>/dev/null  # 杀进程组
        kill -9 "$SERVER_PID" 2>/dev/null   # 确保主进程也被杀
    fi
    pkill -9 -f "core_server.py" 2>/dev/null
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
        -- 启动后最小化 Terminal 窗口
        delay 0.5
        set miniaturized of front window to true
    end tell
    '
fi