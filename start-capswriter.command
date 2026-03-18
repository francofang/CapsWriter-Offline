#!/bin/bash

# Tab 1：启动服务端（当前 tab）

osascript -e '

tell application "Terminal"

    activate

    -- 第一个 tab 跑服务端

    do script "cd ~/Projects/capswriter-mac && source venv/bin/activate && cd CapsWriter-Offline && python core_server.py"

    delay 1

    -- 同一个窗口开第二个 tab 跑客户端

    tell application "System Events" to keystroke "t" using command down

    delay 0.5

    do script "cd ~/Projects/capswriter-mac && source venv/bin/activate && cd CapsWriter-Offline && sleep 8 && python core_client.py" in front window

end tell

'
