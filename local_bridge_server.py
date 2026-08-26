import os, sys, json, time, subprocess, threading, asyncio
from flask import Flask, request, jsonify
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

def record_history_result(dispatch_id, platform_id, title, video_file, success, pub_id="", link="", finish_time=""):
    """Thread-safe: load -> update (find-or-create session record) -> save (keep latest 10)."""
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
    try:
        if sync_all_platforms:
            sync_all_platforms()
    except Exception as e:
        print("Syncing cookies warning:", e)

    creds = load_credentials()
    session_status = {}
    all_platforms = ["tencent", "douyin", "bilibili", "kuaishou", "weibo", "toutiao", "zhihu", "xiaohongshu", "baijiahao", "fanqie", "youtube", "facebook", "x", "linkedin", "instagram", "tiktok", "devto", "wordpress", "telegram", "pinterest"]
    
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
        # 未接入一键扫码登录的平台（如百家号/番茄）：如实告知，不启动错误流程
        return jsonify({
            "status": "unsupported",
            "platform_id": platform_id,
            "msg": f"⚠️ 【{platform_id}】暂不支持一键扫码登录。请在官网浏览器登录后，把 Cookie 文件放入 cookies/ 目录（参考执行手册 §3.3）。"
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
    def on_progress(pct, log_line):
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
    )

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
    app.run(host=host, port=port, debug=False)
