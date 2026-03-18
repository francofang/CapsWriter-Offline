#!/bin/bash
cd "$(dirname "$0")"

# 激活虚拟环境
source ~/Projects/capswriter-mac/venv/bin/activate

# 启动服务端（后台运行）
python core_server.py &
SERVER_PID=$!
echo "✅ 服务端已启动 (PID: $SERVER_PID)"
echo "⏳ 等待模型加载..."
sleep 10

# 启动客户端（前台运行）
echo "✅ 启动客户端..."
python core_client.py

# 客户端退出后，也关掉服务端
kill $SERVER_PID 2>/dev/null
echo "👋 已退出"
