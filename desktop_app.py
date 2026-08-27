import os
import sys
import time
import threading
import subprocess
import webbrowser

# Add current directory to path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)


def _resolve_sau_root():
    """定位 SAU（social-auto-upload）目录。

    优先级：OMP_BUNDLED_SAU env > 打包内嵌 > 项目同级 > 默认 ~/social-auto-upload。
    打包态（PyInstaller）下，SAU 的 conf/uploader/utils 等子目录会被打进 _MEIPASS，
    我们把它的父目录也注册到 SAU_ROOT。
    """
    env = os.environ.get("SAU_ROOT")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = os.path.join(meipass, "social-auto-upload")
        if os.path.isdir(bundled):
            os.environ["SAU_ROOT"] = bundled
            return bundled
    sibling = os.path.join(os.path.dirname(PROJECT_DIR), "social-auto-upload")
    if os.path.isdir(sibling):
        os.environ["SAU_ROOT"] = sibling
        return sibling
    default = os.path.expanduser("~/social-auto-upload")
    if os.path.isdir(default):
        os.environ["SAU_ROOT"] = default
        return default
    return default  # 即便不存在也返回默认路径，UI 会引导用户


# 启动时尽早确定 SAU_ROOT
_sau_root = _resolve_sau_root()
# 把 SAU 根目录加进 sys.path，让 SAU 的 conf/uploader/utils 子包可被 import
if _sau_root and os.path.isdir(_sau_root) and _sau_root not in sys.path:
    sys.path.insert(0, _sau_root)

def start_backend():
    """Start local Flask bridge server via waitress (prod)."""
    from local_bridge_server import app
    try:
        from waitress import serve
        serve(app, host="127.0.0.1", port=5001, threads=4, ident="omp")
    except ImportError:
        app.run(host="127.0.0.1", port=5001, debug=False)

def selftest():
    """打包产物自检模式（--selftest）：启动内嵌后端 → 轮询 /api/health →
    写 selftest_result.json → 退出（0=通过，1=失败）。
    供 CI 在真实 runner 上对打包产物做冒烟测试，防止"构建成功但跑不起来"。
    """
    import json as _json
    import time
    import urllib.request

    t = threading.Thread(target=start_backend, daemon=True)
    t.start()
    ok = False
    for _ in range(30):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen("http://127.0.0.1:5001/api/health", timeout=2) as r:
                if _json.loads(r.read().decode()).get("status") == "ok":
                    ok = True
                    break
        except Exception:
            pass
    result = {"ok": ok, "service": "open-matrix-publisher", "mode": "selftest"}
    with open("selftest_result.json", "w", encoding="utf-8") as f:
        _json.dump(result, f, ensure_ascii=False)
    print(f"SELFTEST {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
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
            title="Open Matrix Publisher (全域矩阵) · 一条内容，多域分发",
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
