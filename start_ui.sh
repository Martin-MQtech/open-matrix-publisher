#!/usr/bin/env bash
# Open Matrix Publisher — Web Dashboard Launcher

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "🚀 正在启动 Open Matrix Publisher 可视化 Web 控制台..."
echo "=========================================================="

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未安装 Python3，请先安装 Python 3.10+"
    exit 1
fi

# Run the Flask bridge server
echo "🌐 后端 API 服务运行于 http://localhost:5001"
echo "💻 正在为您自动打开 Web 控制台页面..."
echo "提示：按 Ctrl+C 可停止控制台服务"
echo "----------------------------------------------------------"

# Open browser automatically after 1 second
(sleep 1.5 && open "http://localhost:5001") &

python3 local_bridge_server.py
