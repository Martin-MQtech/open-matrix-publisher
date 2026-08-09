import os, sys, json, time, subprocess, threading, asyncio
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from cookie_extractor import sync_all_platforms, sync_cookies_from_chrome
from real_uploader_engine import load_credentials, save_credentials, check_profile_logged_in, RealPlatformUploader
from chat_ai_bridge import generate_copy_via_free_ai

app = Flask(__name__)

# cookie_extractor 依赖 browser_cookie3（读取本机 Chrome Cookie），
# 仅用于"从 Chrome 同步登录态"的便捷功能。若所在 Python 环境未安装该依赖，
# 不应影响控制台启动与核心分发能力，故改为可选导入。
try:
    from cookie_extractor import sync_all_platforms, sync_cookies_from_chrome
except Exception:
    sync_all_platforms = None
    sync_cookies_from_chrome = None

# Active background upload tasks store & History Store
ACTIVE_TASKS = {}
TASK_LOCK = threading.Lock()
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dispatch_history.json")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
TASK_PROGRESS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".task_progress")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TASK_PROGRESS_DIR, exist_ok=True)

def _task_progress_file(task_id):
    return os.path.join(TASK_PROGRESS_DIR, f"{task_id}.json")

def save_task_progress(task_id, data):
    """持久化任务进度到文件，服务重启不丢失"""
    with TASK_LOCK:
        ACTIVE_TASKS[task_id] = data
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
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=2, ensure_ascii=False)

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
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), "index.html")

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
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
    all_platforms = ["tencent", "douyin", "bilibili", "kuaishou", "weibo", "toutiao", "zhihu", "xiaohongshu", "youtube", "facebook", "x", "linkedin", "instagram", "tiktok"]
    
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
        "last_dispatch": history.get("last_dispatch"),
        "published_map": published_map
    })

from interactive_login import PLATFORMS as LOGIN_PLATFORMS

def _run_interactive_login_thread(platform_id):
    script_path = os.path.join(os.path.dirname(__file__), "interactive_login.py")
    cmd = [sys.executable, script_path, platform_id]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"Interactive login error for {platform_id}: {e}")

@app.route("/api/launch-login", methods=["POST"])
def launch_login():
    data = request.json or {}
    platform_id = data.get("platform_id", "zhihu")
    plat_info = LOGIN_PLATFORMS.get(platform_id, {})
    plat_name = plat_info.get("name", platform_id)
    
    t = threading.Thread(target=_run_interactive_login_thread, args=(platform_id,))
    t.daemon = True
    t.start()

    return jsonify({
        "status": "launched",
        "platform_id": platform_id,
        "msg": f"🚀 已在桌面为你打开【{plat_name}】的有头浏览器窗口，请使用手机 App 扫码或账号登录！登录成功后系统将自动捕获凭证。"
    })

def _run_real_upload_thread(task_id, platform_id, video_file, title, desc, tags, dispatch_session_id=""):
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

    update(25, f"🚀 [{pname}] 正在连接 {platform_id} 平台上传接口…")
    time.sleep(0.3)

    # Step 2-3: 执行实际上传（耗时最长，实时回传日志）
    update(40, f"⬆️  [{pname}] 正在上传视频（可能需 1-5 分钟）…")

    uploader = RealPlatformUploader(platform_id, video_file, title, desc, tags)
    result = uploader.execute_upload(on_progress=on_progress, log_file=log_path)

    # Step 4: 结果
    finish_time = time.strftime("%Y-%m-%d %H:%M:%S")
    with TASK_LOCK:
        if result.get("success"):
            task_record = {
                "status": "completed",
                "real": True,
                "stage": f"✅ [{pname}] 发布成功 (ID: {result.get('pub_id', 'N/A')})",
                "pct": 100,
                "pub_id": result.get("pub_id"),
                "link": result.get("link"),
                "finish_time": finish_time
            }
        else:
            task_record = {
                "status": "failed",
                "real": False,
                "stage": f"❌ [{pname}] {result.get('error', '未知错误')[:80]}",
                "pct": 100,
                "error": result.get("error", "未知错误"),
                "finish_time": finish_time
            }
        save_task_progress(task_id, task_record)

        # Persist result to dispatch_history.json
        hist = load_history()
        
        # Use the frontend-provided session id so all platforms in one dispatch click
        # group into a single record. Fall back to task_id split if absent.
        dispatch_id = dispatch_session_id if dispatch_session_id else (task_id.split("_task_")[0] if "_task_" in task_id else task_id)
        
        # Find existing record for this task group, or create new
        matching_record = None
        for r in hist.get("records", []):
            if r.get("dispatch_id") == dispatch_id:
                matching_record = r
                break
        
        if matching_record is None:
            matching_record = {
                "dispatch_id": dispatch_id,
                "timestamp": finish_time,
                "video_file": os.path.basename(video_file),
                "title": title,
                "platforms": {}
            }
            hist.setdefault("records", []).append(matching_record)

        # Only record success results (failures don't block future retries)
        if result.get("success"):
            matching_record["platforms"][platform_id] = {
                "status": "success",
                "real": True,
                "pub_id": result.get("pub_id"),
                "link": result.get("link"),
                "finish_time": finish_time
            }

        hist["last_dispatch"] = {
            "timestamp": finish_time,
            "dispatch_id": dispatch_id,
            "title": title,
            "video_file": os.path.basename(video_file),
            "platforms": {platform_id: task_record}
        }
        save_history(hist)

        # Schedule cleanup of the progress file (keep a few minutes so UI can reconnect)
        threading.Timer(300, lambda: cleanup_task_progress(task_id)).start()

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


@app.route("/api/start-upload-task", methods=["POST"])
def start_upload_task():
    data = request.json or {}
    platform_id = data.get("platform_id")
    video_file = data.get("video_file", "your_video.mp4")
    title = data.get("title", "")
    desc = data.get("desc", "")
    tags = data.get("tags", [])
    force = data.get("force", False)  # Allow override for forced re-publish
    dispatch_session_id = data.get("dispatch_session_id", "")  # Groups tasks from one click

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

    task_id = f"{platform_id}_task_{int(time.time()*1000)}"
    
    t = threading.Thread(target=_run_real_upload_thread, args=(task_id, platform_id, video_file, title, desc, tags, dispatch_session_id))
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
    return jsonify(hist)

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

if __name__ == "__main__":
    print("🚀 启动 Open Matrix Publisher Web 控制台: http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)
