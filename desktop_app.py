import os
import sys
import time
import threading
import subprocess
import webbrowser

# Add current directory to path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

def start_backend():
    """Start local Flask bridge server."""
    from local_bridge_server import app
    app.run(host="127.0.0.1", port=5001, debug=False)

def main():
    print("==========================================================")
    print("🚀 正在启动 Open Matrix Publisher (全域矩阵) 桌面客户端...")
    print("==========================================================")

    # 1. 异步启动 Flask 后端
    backend_thread = threading.Thread(target=start_backend)
    backend_thread.daemon = True
    backend_thread.start()
    time.sleep(1.2)

    app_url = "http://127.0.0.1:5001"

    # 2. 尝试使用 pywebview 打开原生独立桌面窗口
    try:
        import webview
        print("🖥️ 正在创建原生应用视窗 (PyWebView Engine)...")
        window = webview.create_window(
            title="Open Matrix Publisher (全域矩阵) · 16 平台 AI 原生全域分发中枢",
            url=app_url,
            width=1380,
            height=900,
            min_size=(1024, 700),
            background_color="#131110",
            text_select=True
        )
        webview.start(debug=False)
    except ImportError:
        # 回退模式：若环境未装 pywebview，则自动使用系统默认浏览器全屏打开
        print("🌐 正在使用默认系统浏览器打开控制台...")
        webbrowser.open(app_url)
        # 保持主线程存活
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 已安全退出 Open Matrix Publisher。")

if __name__ == "__main__":
    main()
