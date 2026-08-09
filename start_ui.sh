#!/usr/bin/env bash
# Open Matrix Publisher — Web 控制台启动器
#
# 运行环境说明：
#   本工具依赖 social-auto-upload（SAU）提供的 patchright/playwright 浏览器引擎，
#   因此控制台（Flask 桥接服务）与上传任务统一使用 SAU 的 venv Python，
#   该环境已包含 flask / browser_cookie3 / patchright / playwright。
#   可通过环境变量 SAU_ROOT 覆盖 SAU 安装路径（默认 /Users/martin/social-auto-upload）。

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

export SAU_ROOT="${SAU_ROOT:-/Users/martin/social-auto-upload}"
PY="$SAU_ROOT/.venv/bin/python"

if [ ! -x "$PY" ]; then
    echo "❌ 未找到 SAU 虚拟环境 Python：$PY"
    echo "   请先安装依赖：social-auto-upload（含 .venv），或用 SAU_ROOT 指定其路径。"
    exit 1
fi

echo "=========================================================="
echo "🚀 正在启动 Open Matrix Publisher 可视化 Web 控制台..."
echo "=========================================================="

# 补全依赖（若 flask / browser_cookie3 缺失则静默安装）
"$PY" -c "import flask, browser_cookie3" 2>/dev/null || "$PY" -m pip install -q flask browser_cookie3

echo "🌐 后端 API 服务运行于 http://localhost:5001"
echo "💻 即将自动打开 Web 控制台页面..."
echo "提示：按 Ctrl+C 可停止控制台服务"
echo "----------------------------------------------------------"

# 1.5 秒后自动打开浏览器
( sleep 1.5 && open "http://localhost:5001" ) &

"$PY" local_bridge_server.py
