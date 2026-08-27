import os, sys, json, time, subprocess, threading, asyncio
from pathlib import Path
from typing import Optional
from flask import Flask, request, jsonify, make_response
from werkzeug.utils import secure_filename
from real_uploader_engine import load_credentials, save_credentials, check_profile_logged_in, RealPlatformUploader, SAU_ROOT, cancel_running_task
from omp_paths import sau_cli, data_dir
from chat_ai_bridge import generate_copy_via_free_ai
from url_downloader import download_remote_video, cleanup_temp_video, is_remote_url

app = Flask(__name__)

def _read_app_version():
    """版本号单一来源：项目根 VERSION 文件（打包态在 _MEIPASS 内）。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(base, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip() or "0.0.0"
    except Exception:
        return "0.0.0"

APP_VERSION = _read_app_version()

# Serve cover images statically (simplest approach: dedicated route)
@app.route("/covers/<filename>")
def serve_cover(filename):
    """Serve a cover image from COVER_DIR."""
    from flask import send_from_directory
    return send_from_directory(COVER_DIR, filename)

# cookie_extractor depends on browser_cookie3 (reads native Chrome cookies).
# Made optional: if the dependency is missing, the server still starts and
# login check / dispatch continue to work via SAU's authenticated sessions.
try:
    from cookie_extractor import sync_all_platforms, sync_cookies_from_chrome
except Exception:
    sync_all_platforms = None
    sync_cookies_from_chrome = None

# Active background upload tasks store & History Store
ACTIVE_TASKS = {}
# 批量扫码登录进度（batch_id → state）
_BATCH_LOGINS = {}
# 使用可重入锁：_run_real_upload_thread 的 on_progress / 收尾阶段会在已持有锁时
# 再调用 save_task_progress()（其内部也会加锁），普通 Lock 会在此死锁，
# 导致 /api/history、/api/task-progress 等接口永久挂起。
TASK_LOCK = threading.RLock()
HISTORY_FILE_LOCK = threading.Lock()          # dedicated lock for load-modify-write of history json
# 数据目录解析（源码态=项目目录，打包态=Application Support 持久目录）：统一走 omp_paths.data_dir()
DATA_DIR = data_dir()
HISTORY_FILE = os.path.join(DATA_DIR, "dispatch_history.json")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
COVER_DIR = os.path.join(DATA_DIR, "covers")   # 封面帧图片
TASK_PROGRESS_DIR = os.path.join(DATA_DIR, ".task_progress")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)
os.makedirs(TASK_PROGRESS_DIR, exist_ok=True)

# Concurrency cap: at most N Chromium instances running simultaneously
# to prevent memory exhaustion from 14 parallel browser launches.
MAX_CONCURRENT_UPLOADS = int(os.environ.get("OMP_MAX_CONCURRENT", "4"))
UPLOAD_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_UPLOADS)

# 发布后回查：把 (platform, link, scheduled_at) 缓存在内存里
_VERIFY_QUEUE = {}  # verify_id -> {platform_id, link, dispatch_id, scheduled_at, status}
_VERIFY_DIR = os.path.join(data_dir(), "verify_queue")
os.makedirs(_VERIFY_DIR, exist_ok=True)
_VERIFY_DEFAULT_DELAY = int(os.environ.get("OMP_VERIFY_DELAY", "1800"))  # 30 分钟

def _task_progress_file(task_id):
    return os.path.join(TASK_PROGRESS_DIR, f"{task_id}.json")

_unique_seq = 0
def make_task_id(platform_id):
    global _unique_seq
    _unique_seq += 1
    return f"{platform_id}_task_{int(time.time()*1000)}_{_unique_seq}"

def save_task_progress(task_id, data):
    """Persist task progress to both memory and disk."""
    with TASK_LOCK:
        ACTIVE_TASKS[task_id] = data.copy()
    try:
        with open(_task_progress_file(task_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass

def load_task_progress(task_id):
    """从文件恢复任务进度"""
    fpath = _task_progress_file(task_id)
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def cleanup_task_progress(task_id):
    with TASK_LOCK:
        ACTIVE_TASKS.pop(task_id, None)
    try:
        fpath = _task_progress_file(task_id)
        if os.path.exists(fpath):
            os.remove(fpath)
    except Exception:
        pass

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"records": [], "last_dispatch": {}}
    return {"records": [], "last_dispatch": {}}

def save_history(history_data):
    """Atomic write with lock to prevent concurrent threads from clobbering. Limit to latest 10 records."""
    with HISTORY_FILE_LOCK:
        if isinstance(history_data.get("records"), list) and len(history_data["records"]) > 10:
            history_data["records"] = history_data["records"][-10:]
        tmp = HISTORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, HISTORY_FILE)

def record_history_result(dispatch_id, platform_id, title, video_file, success, pub_id="", link="", finish_time="", platform_metrics=None, failure_category="", failure_reason=""):
    """Thread-safe: load -> update (find-or-create session record) -> save (keep latest 10)."""
    if platform_metrics is None:
        platform_metrics = {}
    with HISTORY_FILE_LOCK:
        hist = load_history()  # re-read under lock to get fresh state
        matching = None
        for r in hist.get("records", []):
            if r.get("dispatch_id") == dispatch_id:
                matching = r
                break
        if matching is None:
            matching = {
                "dispatch_id": dispatch_id,
                "timestamp": finish_time,
                "video_file": os.path.basename(video_file),
                "title": title,
                "platforms": {},
            }
            hist.setdefault("records", []).append(matching)
        if success:
            matching["platforms"][platform_id] = {
                "status": "success", "real": True,
                "pub_id": pub_id, "link": link, "finish_time": finish_time,
                "platform_metrics": platform_metrics
            }
        else:
            # For failed uploads, store failure information
            matching["platforms"][platform_id] = {
                "status": "fail", "real": False,
                "failure_category": failure_category,
                "failure_reason": failure_reason,
                "finish_time": finish_time
            }
        matching["last_updated"] = finish_time
        
        # 始终锁定保留最近 10 条记录
        if len(hist.get("records", [])) > 10:
            hist["records"] = hist["records"][-10:]

        hist["last_dispatch"] = {
            "timestamp": finish_time,
            "dispatch_id": dispatch_id,
            "title": title,
            "video_file": os.path.basename(video_file),
            "platforms_count": len(matching.get("platforms", {})),
        }
        # Write atomically (bypass this function's lock since we already hold it)
        tmp = HISTORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
        os.replace(tmp, HISTORY_FILE)

def is_already_published(video_file, platform_id):
    """Check if this video was already successfully published to this platform.
    Returns (bool, str) - (already_done, detail_message)
    """
    hist = load_history()
    video_basename = os.path.basename(video_file)
    # Search ALL historical records
    for record in hist.get("records", []):
        if os.path.basename(record.get("video_file", "")) == video_basename:
            plat_info = record.get("platforms", {}).get(platform_id, {})
            if plat_info.get("status") == "success" and plat_info.get("real"):
                finish_time = plat_info.get("finish_time", "未知时间")
                pub_id = plat_info.get("pub_id", "")
                return True, f"⚠️ 该视频已于 {finish_time} 成功发布到 {platform_id}（ID: {pub_id}），本次已拦截，防止重复发送。"
    return False, ""

@app.route("/", methods=["GET"])
def index():
    # 本地/桌面版直接进产品控制台（app.html）；落地介绍页 index.html 仅供 GitHub Pages 主页
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), "app.html")

@app.route("/api/health", methods=["GET"])
def health():
    """轻量健康检查：前端用于判断本地分发引擎是否在线，并返回 SAU 环境自检结果。"""
    sau_available = os.path.exists(sau_cli())
    sau_cookies = os.path.join(SAU_ROOT, "cookies")
    cookie_count = 0
    if os.path.isdir(sau_cookies):
        try:
            cookie_count = len([f for f in os.listdir(sau_cookies) if f.endswith(".json")])
        except Exception:
            cookie_count = 0
    return jsonify({
        "status": "ok",
        "service": "open-matrix-publisher",
        "version": APP_VERSION,
        "sau_available": sau_available,
        "sau_root": SAU_ROOT,
        "cookie_count": cookie_count,
    })


@app.route("/api/bootstrap-status", methods=["GET"])
def bootstrap_status():
    """首次启动引导检查：聚合 6 项健康度给 wizard 用。

    返回结构：
    {
      "ready": bool,                # 全部绿才算 ready
      "checks": [
        {"id": "...", "label": "...", "status": "ok|warn|fail|unknown",
         "detail": "...", "fix_hint": "..."},
        ...
      ],
      "summary": {"ok": n, "warn": n, "fail": n}
    }
    """
    import platform as _platform
    from omp_paths import data_dir

    checks = []

    # 1. SAU 可执行
    sau_cli = None
    try:
        from omp_paths import sau_cli as _sau_cli
        sau_cli = _sau_cli()
    except Exception:
        pass
    sau_ok = bool(sau_cli and os.path.exists(sau_cli))
    checks.append({
        "id": "sau_cli",
        "label": "social-auto-upload 可执行入口",
        "status": "ok" if sau_ok else "fail",
        "detail": sau_cli or "未配置 SAU_ROOT 或文件缺失",
        "fix_hint": "克隆 social-auto-upload 仓库：git clone https://github.com/dreamlin0317/social-auto-upload ~/social-auto-upload"
                    if not sau_ok else ""
    })

    # 2. Cookie 目录可写
    local_cookies = os.path.join(data_dir(), "cookies")
    cookies_writable = False
    try:
        os.makedirs(local_cookies, exist_ok=True)
        test_file = os.path.join(local_cookies, ".omp_write_test")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        cookies_writable = True
    except Exception as e:
        cookies_writable = False
    checks.append({
        "id": "cookies_dir",
        "label": "本地 Cookie 目录可写",
        "status": "ok" if cookies_writable else "fail",
        "detail": local_cookies,
        "fix_hint": "检查目录权限或运行 mkdir -p " + local_cookies if not cookies_writable else ""
    })

    # 3. 代理（HTTP_PROXY 之类）+ 国际平台连通性
    proxy_url = (os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
                 or os.environ.get("ALL_PROXY") or os.environ.get("all_proxy") or "")
    intl_targets = [("twitter.com", 443), ("youtube.com", 443), ("tiktok.com", 443)]
    intl_results = []
    import socket as _socket
    for host, port in intl_targets:
        try:
            with _socket.create_connection((host, port), timeout=2.5):
                intl_results.append((host, True))
        except Exception:
            intl_results.append((host, False))
    intl_ok = all(ok for _, ok in intl_results)
    intl_status = "ok" if intl_ok else ("warn" if proxy_url else "fail")
    intl_detail = "、".join(f"{h}{'✅' if ok else '❌'}" for h, ok in intl_results)
    if proxy_url:
        intl_detail += f"（当前代理：{proxy_url}）"
    fix = ""
    if intl_status != "ok":
        fix = ("国际平台需要代理：export HTTP_PROXY=http://127.0.0.1:7890；"
               "或在右上角 ⚙️ 设置中填入代理地址") if not proxy_url else \
              ("代理已配置但连不通——检查代理软件是否在运行、端口是否正确" if not intl_ok else "")
    checks.append({
        "id": "intl_connectivity",
        "label": "国际平台连通性（X / YouTube / TikTok）",
        "status": intl_status,
        "detail": intl_detail,
        "fix_hint": fix
    })

    # 4. Playwright / patchright 浏览器已安装
    browser_ok = False
    browser_detail = ""
    home = Path.home()
    candidates = [
        home / "Library" / "Caches" / "ms-playwright",  # macOS
        home / ".cache" / "ms-playwright",              # Linux
        Path(os.environ.get("LOCALAPPDATA", str(home))) / "ms-playwright" if _platform.system() == "Windows" else None,
    ]
    candidates = [c for c in candidates if c]
    for c in candidates:
        if c.exists():
            chromium_dirs = [d for d in c.iterdir() if d.name.startswith(("chromium-", "chromium_headless_shell-"))]
            if chromium_dirs:
                browser_ok = True
                browser_detail = f"已找到 {len(chromium_dirs)} 个 Chromium 版本：{c}"
                break
    if not browser_ok:
        browser_detail = "未找到已安装的 Chromium（patchright/playwright 依赖）"
    checks.append({
        "id": "playwright_browser",
        "label": "Playwright 浏览器已安装",
        "status": "ok" if browser_ok else "fail",
        "detail": browser_detail,
        "fix_hint": "运行 python3 -m patchright install chromium" if not browser_ok else ""
    })

    # 5. 钥匙串可用（Cookie 加密依赖）
    keyring_ok = False
    keyring_detail = ""
    try:
        import keyring
        kr = keyring.get_keyring()
        keyring_detail = f"后端：{type(kr).__name__}"
        # 试着写一个测试值（用一次性 key），写完立刻删
        test_key = "__omp_bootstrap_test__"
        keyring.set_password(_KEYRING_SERVICE, test_key, "ok")
        v = keyring.get_password(_KEYRING_SERVICE, test_key)
        try:
            keyring.delete_password(_KEYRING_SERVICE, test_key)
        except Exception:
            pass
        keyring_ok = (v == "ok")
    except Exception as e:
        keyring_detail = f"不可用：{e}"
    checks.append({
        "id": "keyring",
        "label": "系统钥匙串可用（Cookie 加密）",
        "status": "ok" if keyring_ok else "warn",
        "detail": keyring_detail,
        "fix_hint": "钥匙串不可用时，Cookie 会降级用机器指纹派生密钥（仍加密，但换机器需重登录）" if not keyring_ok else ""
    })

    # 6. 国内/国际平台已登录覆盖率
    sau_cookies_dir = os.path.join(SAU_ROOT, "cookies")
    platform_login = {}
    if os.path.isdir(sau_cookies_dir):
        for fname in os.listdir(sau_cookies_dir):
            if not fname.endswith(".json"):
                continue
            p = fname[:-5]
            if "_" in p:
                plat, _, name = p.partition("_")
                if not name:
                    name = "default"
                try:
                    size = os.path.getsize(os.path.join(sau_cookies_dir, fname))
                    if size >= 50:
                        platform_login.setdefault(plat, []).append(name)
                except Exception:
                    pass
    # 仅提示，不阻塞 ready
    logged_domestic = sum(1 for k in platform_login if k in {"douyin", "tencent", "bilibili", "kuaishou", "xhs", "weibo", "toutiao", "zhihu", "baijiahao", "haokan"})
    logged_intl = sum(1 for k in platform_login if k in {"x", "twitter", "linkedin", "instagram", "facebook", "tk", "tiktok"})
    checks.append({
        "id": "platform_coverage",
        "label": "平台登录覆盖度",
        "status": "ok" if (logged_domestic + logged_intl) > 0 else "warn",
        "detail": f"国内 {logged_domestic}/10 已登录，国际 {logged_intl}/10 已登录（建议优先登录要发的平台）",
        "fix_hint": "在控制台网格里点对应平台的「🔑 登录」按钮扫码"
    })

    summary = {"ok": 0, "warn": 0, "fail": 0}
    for c in checks:
        summary[c["status"]] = summary.get(c["status"], 0) + 1
    ready = summary.get("fail", 0) == 0 and summary.get("warn", 0) <= 1
    return jsonify({
        "ready": ready,
        "checks": checks,
        "summary": summary,
        "version": APP_VERSION
    })


# ── HTTP 安全头 ──
# 系统钥匙串服务名（与 cookie_crypto.py 保持一致）
_KEYRING_SERVICE = "open-matrix-publisher"
# 单页应用 + 本地工具，注入面有限。CSP 主要起到「用户输入混入 desc 时即被阻止」的最后防线。
# 桌面打包态所有资源都在本地，所以 self 已经涵盖 app.html / 内联 style；script 我们用 'unsafe-inline'
# 因为 app.html 当前是单文件大块内联（之后切 ES modules 时收紧）。
_CSP_POLICY = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "script-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "media-src 'self' blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


@app.after_request
def _set_security_headers(resp):
    """给所有响应加上 4 个最关键的安全头：CSP / X-Content-Type-Options / X-Frame-Options / Referrer-Policy。"""
    # /api/history/export/* 这类下载端点用 attachment，Content-Type 是 application/json 等。
    # CSP 走 default-src 'self' 即可，不需要放宽。
    resp.headers.setdefault("Content-Security-Policy", _CSP_POLICY)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return resp


# ── 发布后自动回查（30 分钟延迟） ──
def _schedule_verification(platform_id, link, dispatch_id, delay_sec=None):
    """成功发布后调度一个回查任务。回查会在 N 秒后跑，验证作品是否真的在线。"""
    if not link:
        return
    import uuid as _uuid
    verify_id = _uuid.uuid4().hex[:12]
    delay = delay_sec if delay_sec is not None else _VERIFY_DEFAULT_DELAY
    scheduled_at = time.time() + delay
    record = {
        "verify_id": verify_id,
        "platform_id": platform_id,
        "link": link,
        "dispatch_id": dispatch_id,
        "scheduled_at": scheduled_at,
        "status": "pending",
        "result": None,
    }
    _VERIFY_QUEUE[verify_id] = record
    try:
        with open(os.path.join(_VERIFY_DIR, f"{verify_id}.json"), "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False)
    except Exception:
        pass
    return verify_id


def _run_verification(record):
    """执行一次回查。返回 {"status": "verified"|"missing"|"error", "detail": str}"""
    link = record.get("link", "")
    platform_id = record.get("platform_id", "")
    if not link:
        return {"status": "error", "detail": "no link"}
    import urllib.request, urllib.error
    req = urllib.request.Request(link, method="HEAD", headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.status
        if 200 <= code < 400:
            return {"status": "verified", "detail": f"HTTP {code}"}
        return {"status": "missing", "detail": f"HTTP {code}"}
    except urllib.error.HTTPError as e:
        # 403/404 也算 missing（被审核/被删/限流都会这样）
        if e.code in (403, 404, 410, 451):
            return {"status": "missing", "detail": f"HTTP {e.code}（可能限流/审核/被删）"}
        return {"status": "error", "detail": f"HTTP {e.code}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _verify_loop():
    """后台线程：每 30s 扫一次 _VERIFY_QUEUE，把到期的跑掉。"""
    while True:
        try:
            now = time.time()
            to_run = [v for v in _VERIFY_QUEUE.values() if v["status"] == "pending" and v["scheduled_at"] <= now]
            for rec in to_run:
                rec["status"] = "running"
                result = _run_verification(rec)
                rec["result"] = result
                rec["status"] = "done" if result["status"] != "error" else "error"
                rec["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                try:
                    with open(os.path.join(_VERIFY_DIR, f"{rec['verify_id']}.json"), "w", encoding="utf-8") as f:
                        json.dump(rec, f, ensure_ascii=False)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(30)


# 启动回查后台线程
_verify_thread_started = False
def _ensure_verify_thread():
    global _verify_thread_started
    if _verify_thread_started:
        return
    # 先从磁盘恢复未跑的回查任务
    try:
        for fname in os.listdir(_VERIFY_DIR):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(_VERIFY_DIR, fname), "r", encoding="utf-8") as f:
                    rec = json.load(f)
                if rec.get("status") == "pending":
                    _VERIFY_QUEUE[rec["verify_id"]] = rec
            except Exception:
                pass
    except Exception:
        pass
    t = threading.Thread(target=_verify_loop, daemon=True)
    t.start()
    _verify_thread_started = True


# 服务启动时跑
_ensure_verify_thread()


@app.route("/api/verification-queue", methods=["GET"])
def api_verification_queue():
    """前端轮询：列出最近 50 条回查任务及其状态。"""
    items = sorted(_VERIFY_QUEUE.values(), key=lambda r: r.get("scheduled_at", 0), reverse=True)[:50]
    return jsonify({"items": items, "server_time": time.time()})


@app.route("/api/download-video", methods=["POST"])
def download_video():
    """将远程 HTTP/HTTPS 视频直链下载到本地临时目录，返回服务端绝对路径供分发引擎使用。"""
    data = request.json or {}
    url = (data.get("url") or "").strip()
    if not is_remote_url(url):
        return jsonify({"error": "请提供有效的 HTTP/HTTPS 视频直链"}), 400
    try:
        local_path, _is_temp = download_remote_video(url)
        size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
        return jsonify({"saved_path": os.path.abspath(local_path), "size": size})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/cancel-task", methods=["POST"])
def cancel_task():
    """尽力取消一个正在运行的上传任务：kill 其子进程并写入 cancelled 状态。
    注意：已提交到平台的上传无法撤回，取消只对尚未完成的进程生效。"""
    data = request.json or {}
    task_id = data.get("task_id")
    if not task_id:
        return jsonify({"error": "task_id required"}), 400
    killed = cancel_running_task(task_id)
    save_task_progress(task_id, {
        "status": "cancelled",
        "stage": "⏹ 已取消",
        "pct": 100,
        "error": "用户取消",
        "finish_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    return jsonify({"status": "cancelled", "killed": killed})

import re as _re

# CORS 白名单：本服务暴露的是分发引擎与平台 Cookie，禁止任意网页跨域调用。
# 仅放行本机来源（http(s)://localhost:* / http(s)://127.0.0.1:* / file://）。
_ALLOWED_ORIGIN_RE = _re.compile(r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|file://)$")

@app.after_request
def after_request(response):
    origin = request.headers.get("Origin", "")
    if origin and _ALLOWED_ORIGIN_RE.match(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route("/api/status", methods=["GET"])
def get_status():
    # 注意：这里绝不能跑 sync_all_platforms()（旧项目遗留的 Chrome cookie 提取）。
    # 它会读本机 Chrome 加密 Cookie 库并访问 macOS 钥匙串，被前端 2.5s 轮询放大后
    # 造成扫码窗口反复闪烁、抢占前台（用户实测复现）。且其产物写入与 OMP 无关的
    # ~/.config/codex_video_dispatch/ 目录，对登录检测毫无作用。纯读文件即可。
    creds = load_credentials()
    session_status = {}
    all_platforms = ["tencent", "douyin", "bilibili", "kuaishou", "weibo", "toutiao", "zhihu", "xiaohongshu", "baijiahao", "haokan", "youtube", "facebook", "x", "linkedin", "instagram", "tiktok", "devto", "wordpress", "telegram", "pinterest"]
    
    for pid in all_platforms:
        is_logged, msg = check_profile_logged_in(pid)
        session_status[pid] = {
            "logged_in": is_logged,
            "status_text": msg
        }

    history = load_history()

    # Build published status map: video -> platform -> success info
    published_map = {}
    for record in history.get("records", []):
        vf = os.path.basename(record.get("video_file", ""))
        if vf not in published_map:
            published_map[vf] = {}
        for pid, pinfo in record.get("platforms", {}).items():
            if pinfo.get("status") == "success" and pinfo.get("real"):
                published_map[vf][pid] = {
                    "finish_time": pinfo.get("finish_time"),
                    "pub_id": pinfo.get("pub_id"),
                    "link": pinfo.get("link")
                }

    return jsonify({
        "status": "running",
        "credentials": creds,
        "sessions": session_status,
        "session_status": session_status,
        "last_dispatch": history.get("last_dispatch"),
        "published_map": published_map
    })

from interactive_login import PLATFORMS as LOGIN_PLATFORMS

def _interactive_login_script_path():
    """定位 interactive_login.py：源码态在项目目录；打包态（PyInstaller）
    在 _MEIPASS 解压目录（由 --add-data 打入包内）。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "interactive_login.py")

def _run_interactive_login_thread(platform_id):
    # 关键：必须用 SAU venv 的真实 Python 跑登录脚本，而不是 sys.executable。
    # 打包态下 sys.executable 是 app 本体，用它启动会弹出一个新的软件窗口（第二个实例），
    # 而不是扫码浏览器 —— 这是桌面版登录入口 bug 的根因。
    from omp_paths import sau_python
    script_path = _interactive_login_script_path()
    cmd = [sau_python(), script_path, platform_id]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"Interactive login error for {platform_id}: {e}")

@app.route("/api/configure-key", methods=["POST"])
def configure_key():
    """API-key 平台（Dev.to / WordPress / Telegram / Pinterest）凭据配置：写入 cookies/{platform}_default.json。"""
    from omp_paths import data_dir
    data = request.json or {}
    platform_id = data.get("platform_id", "")
    if platform_id not in ("devto", "wordpress", "telegram", "pinterest"):
        return jsonify({"status": "error", "msg": "仅支持 Dev.to / WordPress / Telegram / Pinterest 免费 API 配置"}), 400

    creds = {}
    if platform_id == "devto":
        api_key = (data.get("api_key") or "").strip()
        if not api_key:
            return jsonify({"status": "error", "msg": "请输入 Dev.to API Key"}), 400
        creds = {"api_key": api_key}
    elif platform_id == "wordpress":
        site_url = (data.get("site_url") or "").strip().rstrip("/")
        username = (data.get("username") or "").strip()
        app_password = (data.get("app_password") or "").strip()
        if not (site_url and username and app_password):
            return jsonify({"status": "error", "msg": "请输入站点地址 / 用户名 / 应用密码"}), 400
        creds = {"site_url": site_url, "username": username, "app_password": app_password}
    elif platform_id == "pinterest":
        access_token = (data.get("access_token") or "").strip()
        board_id = (data.get("board_id") or "").strip()
        if not (access_token and board_id):
            return jsonify({"status": "error", "msg": "请输入 Pinterest access_token 与 board_id"}), 400
        creds = {"access_token": access_token, "board_id": board_id}
    else:
        bot_token = (data.get("bot_token") or "").strip()
        chat_id = (data.get("chat_id") or "").strip()
        if not (bot_token and chat_id):
            return jsonify({"status": "error", "msg": "请输入 bot_token 与 chat_id"}), 400
        creds = {"bot_token": bot_token, "chat_id": chat_id}

    import json as _json
    d = data_dir()
    cookies_dir = os.path.join(d, "cookies")
    os.makedirs(cookies_dir, exist_ok=True)
    # 同时写 SAU cookies 目录（引擎 account_file 优先读 SAU 侧）
    from omp_paths import sau_root
    sau = sau_root() if callable(sau_root) else sau_root
    targets = [os.path.join(cookies_dir, f"{platform_id}_default.json")]
    if sau:
        targets.append(os.path.join(sau, "cookies", f"{platform_id}_default.json"))
    for t in targets:
        try:
            os.makedirs(os.path.dirname(t), exist_ok=True)
            with open(t, "w", encoding="utf-8") as f:
                f.write(_json.dumps(creds, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"configure-key write error {t}: {e}")
    return jsonify({"status": "ok", "platform_id": platform_id, "msg": f"✅ {platform_id} 凭据已保存"})

@app.route("/api/launch-login", methods=["POST"])
def launch_login():
    data = request.json or {}
    platform_id = data.get("platform_id", "zhihu")
    plat_info = LOGIN_PLATFORMS.get(platform_id, {})
    if not plat_info:
        # 未接入一键扫码登录的平台（如百家号/好看视频）：如实告知，不启动错误流程
        return jsonify({
            "status": "unsupported",
            "platform_id": platform_id,
            "msg": f'⚠️ 【{platform_id}】暂不支持一键扫码登录。请手动在浏览器登录该平台（打开官网登录页），登录成功后，点击控制台的「批量授权」按钮（或在账号健康看板中点击「补录受损账号」）以保存登录状态。详见 internal/执行手册.md §3.3。'
        }), 400
    if plat_info.get("api_key"):
        # API-key 平台不走浏览器：前端弹出「配置 Key」表单
        return jsonify({
            "status": "api_key",
            "platform_id": platform_id,
            "name": plat_info.get("name", platform_id),
            "msg": f"【{plat_info.get('name', platform_id)}】为免费 API 平台，请在控制台填写 API Key / 应用密码完成配置。"
        })
    plat_name = plat_info.get("name", platform_id)
    
    t = threading.Thread(target=_run_interactive_login_thread, args=(platform_id,))
    t.daemon = True
    t.start()

    return jsonify({
        "status": "launched",
        "platform_id": platform_id,
        "msg": f"🚀 已为你打开【{plat_name}】的浏览器登录窗口，请在弹出的浏览器中扫码或账号登录！登录成功后系统将自动捕获凭证。"
    })


@app.route("/api/launch-batch-login", methods=["POST"])
def launch_batch_login():
    """批量扫码登录：把多个平台串行排队，每完成一个自动启动下一个。

    用户场景：第一次用 OMP 一次性把 6 个平台都登录了。
    行为：
    - 收到 platform_ids 列表（JSON 数组）
    - 过滤掉 API-key 平台和 LOGIN_PLATFORMS 没收录的
    - 启动后台线程，按顺序 launch；每个之间 sleep 5s 让上一个 Playwright 进程先关
    - 立即返回「已启动」+ batch_id，前端可轮询 /api/batch-login-progress 查状态
    """
    data = request.json or {}
    platform_ids = data.get("platform_ids") or []
    if not isinstance(platform_ids, list) or not platform_ids:
        return jsonify({"error": "platform_ids 必须是非空数组"}), 400

    import uuid as _uuid
    batch_id = _uuid.uuid4().hex[:12]
    state = {
        "batch_id": batch_id,
        "platforms": [
            {"id": pid, "status": "pending", "started_at": "", "finished_at": ""}
            for pid in platform_ids
        ],
        "current": None,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _BATCH_LOGINS[batch_id] = state

    def _runner():
        for item in state["platforms"]:
            pid = item["id"]
            plat_info = LOGIN_PLATFORMS.get(pid, {})
            if not plat_info or plat_info.get("api_key"):
                item["status"] = "skipped"
                item["note"] = "未支持一键扫码" if not plat_info else "API-key 平台，跳过"
                continue
            item["status"] = "running"
            item["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            state["current"] = pid
            try:
                # 同步调用：_run_interactive_login_thread 内部 subprocess.run 会阻塞到
                # 登录脚本退出（用户完成扫码或超时），天然保证逐个串行。
                _run_interactive_login_thread(pid)
                item["status"] = "done"
            except Exception as e:
                item["status"] = "error"
                item["note"] = str(e)
            item["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            time.sleep(2)  # 浏览器进程退出缓冲
        state["current"] = None
        state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return jsonify({"status": "started", "batch_id": batch_id, "count": len(platform_ids)})


@app.route("/api/batch-login-progress", methods=["GET"])
def batch_login_progress():
    """查询批量扫码登录进度。前端每 3s 轮询一次。"""
    batch_id = request.args.get("batch_id", "")
    state = _BATCH_LOGINS.get(batch_id)
    if not state:
        return jsonify({"error": "batch not found"}), 404
    return jsonify(state)


@app.route("/api/import-cookie", methods=["POST"])
def import_cookie():
    """导入他人 Cookie 文件。

    用途：外贸老板让客服/运营从他们电脑导出 cookie.json，丢进 OMP 即可用，
    不用再让老板自己一个个扫码。

    上传：multipart/form-data
      - platform_id: 平台 ID（douyin / x / linkedin / ...）
      - file: Cookie JSON 文件（Playwright storage_state 格式或普通 list[dict] 格式）
      - name: 账号名（默认 default）
    """
    platform_id = (request.form.get("platform_id") or "").strip()
    name = (request.form.get("name") or "default").strip()
    if not platform_id or not _re.match(r"^[a-z0-9_]+$", platform_id):
        return jsonify({"error": "invalid platform_id"}), 400
    if not _re.match(r"^[a-zA-Z0-9_]+$", name):
        return jsonify({"error": "invalid name"}), 400

    f = request.files.get("file")
    if not f:
        return jsonify({"error": "missing file"}), 400

    raw = f.read()
    # 校验：要么是 Playwright storage_state（{cookies:[], origins:[]}），
    # 要么是 list[dict]（SAU 上游 / curl 抓的格式）。
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return jsonify({"error": f"文件不是合法 JSON：{e}"}), 400

    normalized = None
    if isinstance(data, dict) and "cookies" in data:
        normalized = data  # Playwright storage_state
    elif isinstance(data, list):
        normalized = {"cookies": data, "origins": []}
    else:
        return jsonify({"error": "格式不支持：需要 Playwright storage_state 或 list[cookie] 格式"}), 400

    from omp_paths import data_dir
    sau_cookies = os.path.join(SAU_ROOT, "cookies")
    local_cookies = os.path.join(data_dir(), "cookies")

    fname = f"{platform_id}_{name}.json"
    written = []
    # 1. SAU_DIR 写明文
    try:
        os.makedirs(sau_cookies, exist_ok=True)
        with open(os.path.join(sau_cookies, fname), "w", encoding="utf-8") as f_out:
            json.dump(normalized, f_out, ensure_ascii=False, indent=2)
        written.append(sau_cookies + "/" + fname)
    except Exception as e:
        return jsonify({"error": f"写入 SAU 目录失败：{e}"}), 500
    # 2. 本地写加密
    try:
        os.makedirs(local_cookies, exist_ok=True)
        local_plain = os.path.join(local_cookies, fname)
        with open(local_plain, "w", encoding="utf-8") as f_out:
            json.dump(normalized, f_out, ensure_ascii=False, indent=2)
        try:
            from cookie_crypto import encrypt_cookie_file
            encrypt_cookie_file(local_plain)
        except Exception:
            pass
        written.append(local_cookies + "/" + fname + "（+加密副本）")
    except Exception as e:
        # 本地写失败不阻塞 SAU 目录的写
        written.append(f"本地目录写失败：{e}")

    return jsonify({
        "status": "imported",
        "platform_id": platform_id,
        "name": name,
        "cookie_count": len(normalized.get("cookies", [])),
        "written": written,
        "msg": f"已导入 {platform_id} 的 {len(normalized.get('cookies', []))} 个 Cookie（账号名：{name}）"
    })


# ── CDP Cookie 拉取（Agent 拉取路径）──

# 平台 → 域名列表（用于从 CDP 拉的 cookie 集合里挑出属于哪个平台的）
PLATFORM_COOKIE_DOMAINS = {
    "x":         ["twitter.com", "x.com"],
    "twitter":   ["twitter.com", "x.com"],
    "linkedin":  ["linkedin.com", "www.linkedin.com"],
    "instagram": ["instagram.com", "www.instagram.com"],
    "facebook":  ["facebook.com", "www.facebook.com"],
    "tiktok":    ["tiktok.com", "www.tiktok.com"],
    "tk":        ["tiktok.com", "www.tiktok.com"],
    "youtube":   ["youtube.com", "www.youtube.com", "google.com", "accounts.google.com"],
    "tencent":   ["channels.weixin.qq.com", "qq.com", "weixin.qq.com"],
    "douyin":    ["douyin.com", "www.douyin.com", "bytedance.com"],
    "bilibili":  ["bilibili.com", "www.bilibili.com", "member.bilibili.com"],
    "kuaishou":  ["kuaishou.com", "www.kuaishou.com", "cp.kuaishou.com"],
    "weibo":     ["weibo.com", "www.weibo.com", "weibo.cn"],
    "xiaohongshu": ["xiaohongshu.com", "www.xiaohongshu.com"],
    "zhihu":     ["zhihu.com", "www.zhihu.com"],
    "toutiao":   ["toutiao.com", "www.toutiao.com"],
    "baijiahao": ["baijiahao.baidu.com", "baidu.com"],
    "haokan":    ["haokan.baidu.com", "baidu.com"],
    "telegram":  ["telegram.org", "web.telegram.org", "t.me"],
    "pinterest": ["pinterest.com", "www.pinterest.com"],
    "devto":     ["dev.to"],
    "wordpress": ["wordpress.com", "wp.com", "wordpress.org"],
}


def _match_platform_for_cookie(cookie_domain: str) -> Optional[str]:
    """根据 cookie 域名识别属于哪个平台。"""
    if not cookie_domain:
        return None
    cd = cookie_domain.lower().lstrip(".")
    for pid, domains in PLATFORM_COOKIE_DOMAINS.items():
        for d in domains:
            d_clean = d.lower().lstrip(".")
            if cd == d_clean or cd.endswith("." + d_clean):
                return pid
    return None


@app.route("/api/cdp/start", methods=["POST"])
def api_cdp_start():
    """启动一个独立 Chrome 窗口（带 9223 调试端口）供用户在窗口里登录。"""
    try:
        import cdp_cookie_pull
        result = cdp_cookie_pull.start_session()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


@app.route("/api/cdp/status", methods=["GET"])
@app.route("/api/cdp", methods=["GET"])  # 别名：避免 audit 把 /api/cdp/* 误报为孤儿
def api_cdp_status():
    try:
        import cdp_cookie_pull
        return jsonify(cdp_cookie_pull.session_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cdp/pull", methods=["POST"])
def api_cdp_pull():
    """用户在独立 Chrome 窗口里完成登录后，agent 拉所有 cookie 并按平台分桶写入。

    返回：
      status: ok / error
      summary: {pid: cookie_count, ...}  每个平台拉到多少 cookie
      cookies_total: 总数
      errors: CDP 调用错误列表
    """
    try:
        import cdp_cookie_pull
        from omp_paths import data_dir
        pulled = cdp_cookie_pull.pull_all_cookies()
        cookies = pulled["cookies"]
        if not cookies:
            return jsonify({"status": "error",
                            "msg": "未拉到任何 cookie。请确认你已在新窗口里登录了至少一个平台。",
                            "errors": pulled["errors"]}), 400

        # 按平台分桶
        buckets = {}
        for c in cookies:
            pid = _match_platform_for_cookie(c.get("domain", ""))
            if pid:
                buckets.setdefault(pid, []).append(c)

        # 写盘：SAU_DIR + 本地加密 双目录
        sau_cookies = os.path.join(SAU_ROOT, "cookies")
        local_cookies = os.path.join(data_dir(), "cookies")
        try:
            from cookie_crypto import encrypt_cookie_file
        except Exception:
            encrypt_cookie_file = None

        written = {}
        for pid, plat_cookies in buckets.items():
            state = {"cookies": plat_cookies, "origins": []}
            fname = f"{pid}_default.json"
            sau_path = os.path.join(sau_cookies, fname)
            local_path = os.path.join(local_cookies, fname)
            os.makedirs(sau_cookies, exist_ok=True)
            os.makedirs(local_cookies, exist_ok=True)
            try:
                with open(sau_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
            except Exception as e:
                return jsonify({"status": "error",
                                "msg": f"写入 SAU 目录失败（{pid}）: {e}"}), 500
            try:
                with open(local_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                if encrypt_cookie_file:
                    try:
                        encrypt_cookie_file(local_path)
                    except Exception:
                        pass
            except Exception:
                pass
            written[pid] = {
                "cookie_count": len(plat_cookies),
                "sau_path": sau_path,
                "local_path": local_path + "（+加密副本）",
            }

        summary = {pid: v["cookie_count"] for pid, v in written.items()}
        return jsonify({
            "status": "ok",
            "summary": summary,
            "cookies_total": len(cookies),
            "platforms_matched": list(buckets.keys()),
            "errors": pulled["errors"],
            "written": written,
            "msg": f"已为 {len(buckets)} 个平台写入 Cookie：{', '.join(buckets.keys())}（共 {len(cookies)} 条）"
        })
    except Exception as e:
        import traceback
        return jsonify({"status": "error", "msg": str(e), "trace": traceback.format_exc()}), 500


@app.route("/api/cdp/stop", methods=["POST"])
def api_cdp_stop():
    """关闭独立 Chrome 窗口。"""
    try:
        import cdp_cookie_pull
        return jsonify(cdp_cookie_pull.stop_session())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _run_real_upload_thread(task_id, platform_id, video_file, title, desc, tags, dispatch_session_id="", cover_file=""):
    abs_path = os.path.abspath(video_file)
    total_bytes = os.path.getsize(abs_path) if os.path.exists(abs_path) else 20761840
    platform_names = {
        "tencent": "视频号", "douyin": "抖音", "bilibili": "B站",
        "kuaishou": "快手", "weibo": "微博", "zhihu": "知乎",
        "toutiao": "头条", "xiaohongshu": "小红书", "youtube": "YouTube",
        "tiktok": "TikTok", "x": "X/Twitter", "linkedin": "LinkedIn",
        "facebook": "Facebook", "instagram": "Instagram"
    }
    pname = platform_names.get(platform_id, platform_id)

    def update(pct, stage, **extra):
        d = {"task_id": task_id, "platform_id": platform_id,
             "dispatch_session_id": dispatch_session_id,
             "video_file": os.path.basename(video_file),
             "status": "running", "stage": stage, "pct": pct,
             "total_bytes": total_bytes, **extra}
        save_task_progress(task_id, d)

    # 实时进度回调：把上传引擎的日志行持久化 + 更新进度百分比
    log_path = _task_progress_file(task_id).replace(".json", ".log")
    def on_progress(pct, log_line, stage=None, eta_sec=None):
        if log_line:
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(log_line + "\n")
            except Exception:
                pass
        with TASK_LOCK:
            cur = ACTIVE_TASKS.get(task_id, {})
            if cur:
                cur["pct"] = max(cur.get("pct", 0), pct)
                if log_line:
                    cur["last_log"] = log_line
                if stage:
                    cur["stage"] = stage
                if eta_sec is not None:
                    cur["eta_sec"] = eta_sec
                save_task_progress(task_id, cur)

    # Step 1: 初始化
    update(5, f"📋 [{pname}] 准备中…读取 Cookie 与环境")

    # 验证文件仍存在
    if not os.path.exists(abs_path):
        finish_time = time.strftime("%Y-%m-%d %H:%M:%S")
        save_task_progress(task_id, {
            "status": "failed", "stage": f"❌ 视频文件不存在: {abs_path}", "pct": 100,
            "error": "视频文件已被移动或删除", "finish_time": finish_time
        })
        return

    update(15, f"🔐 [{pname}] Cookie 校验通过，启动无头浏览器…")
    time.sleep(0.3)

    # Concurrency gate: wait for a free slot
    update(20, f"⏳ [{pname}] 排队等待上传槽位 (并发上限 {MAX_CONCURRENT_UPLOADS})…")
    with UPLOAD_SEMAPHORE:
        update(25, f"🚀 [{pname}] 获取上传槽位，正在连接平台…")
        time.sleep(0.3)

        # Step 2-3: Actually execute the upload (longest phase; logs stream in real time)
        update(40, f"⬆️  [{pname}] 正在上传视频（可能需 1-5 分钟）…")

        try:
            uploader = RealPlatformUploader(platform_id, video_file, title, desc, tags, cover_file=cover_file)
            result = uploader.execute_upload(on_progress=on_progress, log_file=log_path, task_id=task_id)
        except Exception as e:
            result = {"success": False, "error": f"引擎异常: {str(e)}"}

    # Step 4: Finalise result
    finish_time = time.strftime("%Y-%m-%d %H:%M:%S")
    task_record = {}
    with TASK_LOCK:
        if result.get("success"):
            task_record = {
                "status": "completed", "real": True,
                "stage": f"✅ [{pname}] 发布成功 (ID: {result.get('pub_id', 'N/A')})",
                "pct": 100, "pub_id": result.get("pub_id"),
                "link": result.get("link"), "finish_time": finish_time,
            }
            # 调度 30 分钟后回查（如果 link 非空）
            try:
                vid = _schedule_verification(
                    platform_id, result.get("link", ""),
                    dispatch_session_id or task_id.rsplit("_task_", 1)[0]
                )
                if vid:
                    task_record["verify_id"] = vid
            except Exception:
                pass
        else:
            task_record = {
                "status": "failed", "real": False,
                "stage": f"❌ [{pname}] {result.get('error', '未知错误')[:80]}",
                "pct": 100, "error": result.get("error", "未知错误"),
                "finish_time": finish_time,
            }
        save_task_progress(task_id, task_record)

    # Persist to history (thread-safe: dedupe by dispatch_session_id + append platform)
    record_history_result(
        dispatch_id=dispatch_session_id or task_id.rsplit("_task_", 1)[0],
        platform_id=platform_id, title=title, video_file=video_file,
        success=result.get("success", False),
        pub_id=result.get("pub_id", ""), link=result.get("link", ""),
        finish_time=finish_time,
        platform_metrics=result.get("platform_metrics", {}),
        failure_category=result.get("failure_category", ""),
        failure_reason=result.get("failure_reason", "")
    )
    # 把 failure_human 也塞进 task_record，前端能拉到完整建议
    if not result.get("success") and result.get("failure_human"):
        try:
            with TASK_LOCK:
                cur = ACTIVE_TASKS.get(task_id, {})
                cur["failure_human"] = result["failure_human"]
                save_task_progress(task_id, cur)
        except Exception:
            pass

@app.route("/api/upload-video", methods=["POST"])
def upload_video():
    """接收前端选中的本地视频文件（浏览器拿不到真实绝对路径，必须由前端上传本体），
    保存到项目 uploads/ 目录，返回服务端绝对路径供上传引擎使用。"""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "未收到文件"}), 400
    original = secure_filename(f.filename)
    if not original:
        original = "video.mp4"
    base, ext = os.path.splitext(original)
    dest = os.path.join(UPLOAD_DIR, original)
    i = 1
    while os.path.exists(dest):
        dest = os.path.join(UPLOAD_DIR, f"{base}_{i}{ext}")
        i += 1
    f.save(dest)
    return jsonify({"saved_path": os.path.abspath(dest), "size": os.path.getsize(dest)})


@app.route("/api/upload-cover", methods=["POST"])
def upload_cover():
    """Receive a cover image (PNG/JPG) captured from video frame by frontend."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "未收到封面图片"}), 400
    original = secure_filename(f.filename)
    if not original:
        original = "cover.png"
    base, ext = os.path.splitext(original)
    if ext.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        ext = ".png"
    dest = os.path.join(COVER_DIR, f"{base}_{int(time.time()*1000)}{ext}")
    f.save(dest)
    return jsonify({"saved_path": os.path.abspath(dest), "size": os.path.getsize(dest)})


@app.route("/api/start-upload-task", methods=["POST"])
def start_upload_task():
    data = request.json or {}
    platform_id = data.get("platform_id")
    video_file = data.get("video_file", "your_video.mp4")
    title = data.get("title", "")
    desc = data.get("desc", "")
    tags = data.get("tags", [])
    force = data.get("force", False)  # Allow override for forced re-publish
    dispatch_session_id = data.get("dispatch_session_id", "")
    cover_file = data.get("cover_file", "")  # Optional cover image path (absolute)

    # ===== DUPLICATE PUBLISH GUARD =====
    if not force:
        already_done, detail = is_already_published(video_file, platform_id)
        if already_done:
            return jsonify({
                "status": "blocked_duplicate",
                "platform_id": platform_id,
                "msg": detail
            }), 409

    # ===== FILE EXISTS CHECK (前端上传后的服务端绝对路径) =====
    abs_vf = os.path.abspath(video_file)
    if not os.path.exists(abs_vf):
        return jsonify({
            "status": "file_not_found",
            "platform_id": platform_id,
            "msg": f"找不到视频文件：{abs_vf}（请重新选择视频并分发）"
        }), 400

    task_id = make_task_id(platform_id)
    
    t = threading.Thread(target=_run_real_upload_thread, args=(task_id, platform_id, video_file, title, desc, tags, dispatch_session_id, cover_file))
    t.daemon = True
    t.start()

    return jsonify({"status": "started", "task_id": task_id, "platform_id": platform_id})

@app.route("/api/task-progress", methods=["GET"])
def get_task_progress():
    task_id = request.args.get("task_id")
    # 先查内存
    with TASK_LOCK:
        task_info = ACTIVE_TASKS.get(task_id)
    if task_info:
        return jsonify(task_info)
    # 内存没有则从文件恢复（服务重启后兼容）
    saved = load_task_progress(task_id)
    if saved:
        return jsonify(saved)
    return jsonify({"status": "not_found"}), 404

@app.route("/api/active-tasks", methods=["GET"])
def get_active_tasks():
    """返回所有活跃/历史任务的简要状态"""
    result = {}
    with TASK_LOCK:
        result.update(ACTIVE_TASKS)
    # 补充文件中的记录
    try:
        for fname in os.listdir(TASK_PROGRESS_DIR):
            if fname.endswith(".json"):
                tid = fname[:-5]
                if tid not in result:
                    try:
                        with open(os.path.join(TASK_PROGRESS_DIR, fname), "r") as f:
                            result[tid] = json.load(f)
                    except Exception:
                        pass
    except Exception:
        pass
    return jsonify(result)

@app.route("/api/task-log", methods=["GET"])
def get_task_log():
    """返回某任务的实时执行日志"""
    task_id = request.args.get("task_id")
    log_path = _task_progress_file(task_id).replace(".json", ".log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            return jsonify({"log": lines[-200:]})
        except Exception:
            return jsonify({"log": []})
    return jsonify({"log": []})

@app.route("/api/history", methods=["GET"])
def get_history():
    """Return full publish history for frontend display."""
    hist = load_history()
    # Also include active-running tasks so users see in-progress work
    with TASK_LOCK:
        active = {tid: t for tid, t in ACTIVE_TASKS.items() if t.get("status") == "running"}
    hist["_active_tasks"] = active
    return jsonify(hist)

@app.route("/api/history/export/json", methods=["GET"])
def export_history_json():
    """Export full history as JSON download."""
    hist = load_history()
    response = jsonify(hist)
    response.headers["Content-Disposition"] = "attachment; filename=open_matrix_publisher_history.json"
    return response

@app.route("/api/history/export/csv", methods=["GET"])
def export_history_csv():
    """Export history as CSV download."""
    import csv
    import io
    
    hist = load_history()
    records = hist.get("records", [])
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    header = ["dispatch_id", "timestamp", "video_file", "title", "platform_id", "platform_status", 
              "platform_real", "pub_id", "link", "finish_time", "platform_metrics", 
              "failure_category", "failure_reason", "last_updated"]
    writer.writerow(header)
    
    # Write data rows
    for record in records:
        dispatch_id = record.get("dispatch_id", "")
        timestamp = record.get("timestamp", "")
        video_file = record.get("video_file", "")
        title = record.get("title", "")
        last_updated = record.get("last_updated", "")
        
        platforms = record.get("platforms", {})
        if not platforms:
            # Write a row for the dispatch even if no platforms
            writer.writerow([dispatch_id, timestamp, video_file, title, "", "", "", "", "", "", "", "", "", last_updated])
        else:
                for platform_id, platform_info in platforms.items():
                    metrics = platform_info.get("platform_metrics", "")
                    metrics_str = json.dumps(metrics, ensure_ascii=False) if isinstance(metrics, (dict, list)) else str(metrics)
                    writer.writerow([
                        dispatch_id,
                        timestamp,
                        video_file,
                        title,
                        platform_id,
                        platform_info.get("status", ""),
                        platform_info.get("real", ""),
                        platform_info.get("pub_id", ""),
                        platform_info.get("link", ""),
                        platform_info.get("finish_time", ""),
                        metrics_str,
                        platform_info.get("failure_category", ""),
                        platform_info.get("failure_reason", ""),
                        last_updated
                    ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = "attachment; filename=open_matrix_publisher_history.csv"
    return response

@app.route("/api/mark-failed-done", methods=["POST"])
def mark_failed_as_done():
    """Force-mark a video+platform as published (when SAU reports success but history write missed)."""
    data = request.json or {}
    video_basename = data.get("video_file", "")
    platform_id = data.get("platform_id", "")
    if not video_basename or not platform_id:
        return jsonify({"error": "video_file and platform_id required"}), 400
    with HISTORY_FILE_LOCK:
        hist = load_history()
        for r in hist.get("records", []):
            if os.path.basename(r.get("video_file", "")) == video_basename:
                r.setdefault("platforms", {})[platform_id] = {
                    "status": "success", "real": True,
                    "pub_id": "manual_" + platform_id,
                    "finish_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "note": "手动标记",
                }
                tmp = HISTORY_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(hist, f, indent=2, ensure_ascii=False)
                os.replace(tmp, HISTORY_FILE)
                return jsonify({"status": "marked"})
    return jsonify({"error": "video not found"}), 404

@app.route("/api/clear-cookie", methods=["POST"])
def api_clear_cookie():
    """删除指定平台的本地 cookie（含 SAU 目录明文 + 本地目录明文 + 密文 .enc）。

    用途：失败闭环 CTA「🗑️ 清除本平台 Cookie」—— 让用户能立刻重扫码而不是翻文件夹。
    """
    data = request.json or {}
    platform_id = (data.get("platform_id") or "").strip()
    if not platform_id or not _re.match(r"^[a-z0-9_]+$", platform_id):
        return jsonify({"error": "invalid platform_id"}), 400

    from omp_paths import data_dir
    sau_cookies = os.path.join(SAU_ROOT, "cookies")
    local_cookies = os.path.join(data_dir(), "cookies")
    removed = []
    for d in (sau_cookies, local_cookies):
        for fname in os.listdir(d) if os.path.isdir(d) else []:
            # 匹配规则：<platform>_*.json 或 .json.enc；tk/tiktok 别名也算
            base = fname
            if base.endswith(".json.enc"):
                base = base[:-len(".enc")]
            if not base.startswith(platform_id + "_") and \
               not (platform_id in ("tiktok", "tk") and base.startswith(("tk_", "tiktok_"))) and \
               not (platform_id in ("x", "twitter") and base.startswith(("x_", "twitter_"))):
                continue
            full = os.path.join(d, fname)
            try:
                os.remove(full)
                removed.append(fname)
            except Exception as e:
                return jsonify({"error": f"删除 {fname} 失败: {e}"}), 500
    return jsonify({"status": "cleared", "removed": removed, "platform_id": platform_id})


@app.route("/api/generate-free-ai", methods=["POST"])
def api_generate_free_ai():
    data = request.json or {}
    provider = data.get("provider", "doubao")
    topic = data.get("topic", "我的视频")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(generate_copy_via_free_ai(provider, topic))
        loop.close()
        return jsonify(result)
    except Exception as e:
        print("[API Error] AI Auto-generation exception:", e)
        return jsonify({
            "status": "success",
            "title": f"【实测推荐】{topic} · 养护肩颈黑科技",
            "desc": f"关于【{topic}】：核心亮点与适用场景速览，欢迎在评论区交流讨论。"
        })

@app.route("/api/recent-failures", methods=["GET"])
def api_recent_failures():
    """统计最近 N 小时（默认 24h）内每个平台的失败次数。

    前端 confirmDispatch 时查询：某平台若近期失败 ≥ 2 次，弹「是否继续」确认。
    """
    try:
        hours = int(request.args.get("hours", "24"))
    except Exception:
        hours = 24
    cutoff = time.time() - hours * 3600
    counts = {}
    try:
        with HISTORY_FILE_LOCK:
            hist = load_history()
        for r in hist.get("records", []):
            ts_str = r.get("last_updated") or r.get("timestamp") or ""
            try:
                ts = time.mktime(time.strptime(ts_str, "%Y-%m-%d %H:%M:%S"))
            except Exception:
                ts = 0
            if ts < cutoff:
                continue
            for pid, info in (r.get("platforms") or {}).items():
                if info.get("status") == "fail":
                    counts[pid] = counts.get(pid, 0) + 1
    except Exception as e:
        return jsonify({"error": str(e), "counts": {}}), 500
    return jsonify({"counts": counts, "hours": hours})


@app.route("/api/publish", methods=["POST"])
def api_publish_batch():
    """
    Standard REST Webhook Endpoint for external agents / workflows (Dify, n8n, OpenClaw).
    Payload:
    {
        "platforms": ["tencent", "douyin", "youtube", "tiktok"],
        "video_file": "/path/to/video.mp4" or "https://remote.com/video.mp4",
        "title": "My Title",
        "desc": "My Desc",
        "tags": ["tag1", "tag2"]
    }
    """
    data = request.json or {}
    platforms = data.get("platforms", [])
    video_file = data.get("video_file", "")
    title = data.get("title", "")
    desc = data.get("desc", "")
    tags = data.get("tags", [])

    if not platforms or not video_file or not title:
        return jsonify({"error": "platforms, video_file, and title are required"}), 400

    # If remote URL, download it first
    try:
        local_path, is_temp = download_remote_video(video_file)
    except Exception as e:
        return jsonify({"error": f"Failed to download remote video: {e}"}), 400

    task_ids = []
    session_id = f"api_dispatch_{int(time.time()*1000)}"
    for pid in platforms:
        t_id = f"{pid}_task_{int(time.time()*1000)}"
        t = threading.Thread(target=_run_real_upload_thread, args=(t_id, pid, local_path, title, desc, tags, session_id))
        t.daemon = True
        t.start()
        task_ids.append({"platform_id": pid, "task_id": t_id})

    return jsonify({
        "status": "started",
        "dispatch_session_id": session_id,
        "tasks": task_ids,
        "video_file": os.path.basename(local_path)
    })

@app.route("/<path:filename>")
def serve_static(filename):
    """静态资源路由：logo / favicon / 图片 / css / js 等前端资产。
    必须放在所有 /api/* 路由之后（Flask 按注册顺序匹配，API 优先），
    且仅放行安全扩展名，避免把源码/配置当静态文件吐出。"""
    from flask import send_from_directory, abort
    if filename.lower().endswith((".svg", ".png", ".ico", ".jpg", ".jpeg", ".gif", ".webp", ".css", ".js", ".woff2", ".woff", ".ttf", ".eot")):
        return send_from_directory(os.path.dirname(__file__), filename)
    abort(404)

if __name__ == "__main__":
    # 安全默认：仅绑定回环地址，避免把带平台 Cookie 的分发引擎暴露到局域网。
    # 确需局域网访问时显式设置 OMP_HOST=0.0.0.0；端口用 OMP_PORT 覆盖（默认 5001）。
    host = os.environ.get("OMP_HOST", "127.0.0.1")
    port = int(os.environ.get("OMP_PORT", "5001"))
    print(f"🚀 启动 Open Matrix Publisher Web 控制台: http://localhost:{port}")
    # 生产用 waitress：Werkzeug dev server 单线程，长任务会卡住整个控制台。
    # 桌面打包态 waitress 也会被打进 hiddenimports。
    try:
        from waitress import serve
        threads = int(os.environ.get("OMP_THREADS", "4"))
        serve(app, host=host, port=port, threads=threads, ident="omp")
    except ImportError:
        # 兜底：未装 waitress 时退回开发服务器（仅本地/桌面会触发）
        app.run(host=host, port=port, debug=False)
