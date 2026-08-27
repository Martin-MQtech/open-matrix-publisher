# -*- coding: utf-8 -*-
"""CDP Cookie 拉取 —— Agent 启动独立 Chrome 窗口，用户在窗口里手动登录后拉 cookie。

设计：
- 启动一个**独立 Chrome 进程**（独立 user-data-dir，不影响用户主 Chrome）
- 带 --remote-debugging-port=9223
- 用 Chrome DevTools Protocol (CDP) 通过 WebSocket 连过去
- 用户在那个独立窗口里手动登录（扫码/账号密码均可）
- 用户在 OMP 点"我登录好了" → 后端 CDP 拉所有页面的 cookie
- 写入 SAU_DIR + 本地加密 双目录
- 拉完自动关闭那个独立 Chrome

为什么不用 Playwright：依赖更少、用户主 Chrome 不动、独立实例隔离。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import requests
import websocket  # websocket-client

CDP_PORT = 9223
PROFILE_DIR = Path.home() / "Library" / "Application Support" / "omp-cdp-profile"
CHROME_BUNDLE_MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_BUNDLE_WIN = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
CHROME_BUNDLE_LINUX = "/usr/bin/google-chrome"


# ── Chrome 进程管理 ──

_chrome_proc: Optional[subprocess.Popen] = None
_session_started_at: Optional[float] = None


def _chrome_path() -> Optional[str]:
    """找到 Chrome 可执行文件路径。"""
    candidates = [CHROME_BUNDLE_MAC]
    if sys.platform == "win32":
        candidates.insert(0, CHROME_BUNDLE_WIN)
    elif sys.platform.startswith("linux"):
        candidates.insert(0, CHROME_BUNDLE_LINUX)
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def start_session() -> dict:
    """启动一个独立 Chrome 实例（带远程调试端口），返回 session_id + 状态。"""
    global _chrome_proc, _session_started_at

    # 若已有实例在跑且还活着，直接复用
    if _chrome_proc and _chrome_proc.poll() is None and _is_debug_port_open():
        return {"status": "running", "session_id": _current_session_id(),
                "msg": "调试 Chrome 已在运行，请在弹出的窗口里登录后点『我登录好了』"}

    chrome = _chrome_path()
    if not chrome:
        return {"status": "error",
                "msg": f"未找到 Chrome 安装路径（尝试过 {CHROME_BUNDLE_MAC} 等）。请确认 Chrome 已安装。"}

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    # 关闭可能残留的进程（用同一个 profile 目录的）
    _kill_stale_chrome()

    cmd = [
        chrome,
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        # 第一个页面让用户看到 OMP 控制台，方便知道这是 Agent 拉的窗口
        "http://127.0.0.1:5001",
    ]
    try:
        _chrome_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=(sys.platform != "win32")
        )
    except Exception as e:
        return {"status": "error", "msg": f"启动 Chrome 失败：{e}"}

    _session_started_at = time.time()

    # 等调试端口就绪（最多 8 秒）
    for _ in range(40):
        if _is_debug_port_open():
            return {
                "status": "started",
                "session_id": _current_session_id(),
                "msg": "已弹出独立 Chrome 窗口。请在该窗口里扫码/账号登录你要授权的平台，"
                       "登录完成后回到 OMP 控制台点『我登录好了』按钮。"
            }
        time.sleep(0.2)

    return {"status": "timeout",
            "msg": "Chrome 启动后调试端口未在 8 秒内就绪，请重试。"}


def _kill_stale_chrome():
    """杀掉用同一个 PROFILE_DIR 的残留进程。"""
    try:
        subprocess.run(
            ["pkill", "-f", f"--user-data-dir={PROFILE_DIR}"],
            timeout=3, check=False
        )
    except Exception:
        pass


def _is_debug_port_open() -> bool:
    try:
        r = requests.get(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1)
        return r.status_code == 200
    except Exception:
        return False


def _current_session_id() -> str:
    global _session_started_at
    if _session_started_at is None:
        _session_started_at = time.time()
    return str(int(_session_started_at))


# ── CDP 拉取 ──

def list_targets() -> list[dict]:
    """列出当前所有可调试的页面（target）。"""
    try:
        r = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=3)
        return r.json()
    except Exception as e:
        return [{"error": str(e)}]


def _ws_url_for_target(ws_url: str) -> str:
    """CDP 返回的 webSocketDebuggerUrl 形如 ws://127.0.0.1:9223/devtools/page/...，可直接用。"""
    return ws_url


def _cdp_call(ws, method: str, params: Optional[dict] = None, _id: list = None) -> dict:
    """通过 WebSocket 调一次 CDP 方法。_id 是用作 msg_id 计数器的列表。"""
    if _id is None:
        _id = [0]
    _id[0] += 1
    msg_id = _id[0]
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        raw = ws.recv()
        data = json.loads(raw)
        if data.get("id") == msg_id:
            if "error" in data:
                return {"error": data["error"]}
            return data.get("result", {})


def pull_all_cookies() -> dict:
    """从所有可调试的 target 拉 cookie，合并去重，返回 storage_state 格式。"""
    targets = list_targets()
    all_cookies = []
    seen = set()  # (name, domain, path) 去重
    errors = []

    for t in targets:
        if t.get("type") != "page":
            continue
        ws_url = t.get("webSocketDebuggerUrl")
        if not ws_url:
            continue
        url = t.get("url", "")
        try:
            ws = websocket.create_connection(ws_url, timeout=10)
        except Exception as e:
            errors.append(f"{url}: WebSocket 连接失败: {e}")
            continue
        try:
            res = _cdp_call(ws, "Network.getAllCookies", _id=[100])
            if "error" in res:
                errors.append(f"{url}: CDP 错误: {res['error']}")
                continue
            for c in res.get("cookies", []):
                key = (c.get("name"), c.get("domain"), c.get("path"))
                if key in seen:
                    continue
                seen.add(key)
                # 转成 Playwright storage_state 格式
                all_cookies.append({
                    "name": c.get("name"),
                    "value": c.get("value"),
                    "domain": c.get("domain"),
                    "path": c.get("path", "/"),
                    "expires": c.get("expires", -1),
                    "httpOnly": c.get("httpOnly", False),
                    "secure": c.get("secure", False),
                    "sameSite": c.get("sameSite", "Lax"),
                })
        except Exception as e:
            errors.append(f"{url}: {e}")
        finally:
            try:
                ws.close()
            except Exception:
                pass

    return {
        "cookies": all_cookies,
        "origins": [],
        "errors": errors,
        "target_count": len([t for t in targets if t.get("type") == "page"]),
    }


def stop_session() -> dict:
    """关闭独立 Chrome 进程。"""
    global _chrome_proc, _session_started_at
    if _chrome_proc and _chrome_proc.poll() is None:
        try:
            _chrome_proc.terminate()
            _chrome_proc.wait(timeout=5)
        except Exception:
            try:
                _chrome_proc.kill()
            except Exception:
                pass
    _kill_stale_chrome()
    _chrome_proc = None
    _session_started_at = None
    return {"status": "stopped"}


def session_status() -> dict:
    return {
        "running": _chrome_proc is not None and _chrome_proc.poll() is None,
        "port_open": _is_debug_port_open(),
    }
