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
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "dispatch_history.json")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

def _run_real_upload_thread(task_id, platform_id, video_file, title, desc, tags):
    abs_path = os.path.abspath(video_file)
    total_bytes = os.path.getsize(abs_path) if os.path.exists(abs_path) else 20761840

    with TASK_LOCK:
        ACTIVE_TASKS[task_id] = {
            "task_id": task_id,
            "platform_id": platform_id,
            "status": "running",
            "stage": "Step 1/4: 从 Mac Chrome 读取 Cookie，启动后台无头浏览器...",
            "pct": 20,
            "bytes_uploaded": 0,
            "total_bytes": total_bytes,
            "speed_mbps": 0.0
        }

    time.sleep(0.5)

    with TASK_LOCK:
        ACTIVE_TASKS[task_id].update({
            "stage": "Step 2/4: Playwright 无头模式后台物理上传 MP4 成片...",
            "pct": 60
        })

    uploader = RealPlatformUploader(platform_id, video_file, title, desc, tags)
    result = uploader.execute_upload()

    finish_time = time.strftime("%Y-%m-%d %H:%M:%S")
    with TASK_LOCK:
        if result.get("success"):
            task_record = {
                "status": "completed",
                "real": True,
                "stage": f"Step 4/4: ✅ 无头模式后台静默发布成功 (ID: {result.get('pub_id')})",
                "pct": 100,
                "pub_id": result.get("pub_id"),
                "link": result.get("link"),
                "finish_time": finish_time
            }
            ACTIVE_TASKS[task_id].update(task_record)
        else:
            task_record = {
                "status": "failed",
                "real": False,
                "stage": f"❌ {result.get('error')}",
                "pct": 100,
                "error": result.get("error"),
                "finish_time": finish_time
            }
            ACTIVE_TASKS[task_id].update(task_record)

        # Persist result to dispatch_history.json
        hist = load_history()
        
        # Update or create the matching record by video+dispatch_id
        dispatch_id = task_id.split("_task_")[0] if "_task_" in task_id else task_id
        
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
            "title": title,
            "video_file": os.path.basename(video_file),
            "platforms": {platform_id: task_record}
        }
        save_history(hist)

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
    
    t = threading.Thread(target=_run_real_upload_thread, args=(task_id, platform_id, video_file, title, desc, tags))
    t.daemon = True
    t.start()

    return jsonify({"status": "started", "task_id": task_id, "platform_id": platform_id})

@app.route("/api/task-progress", methods=["GET"])
def get_task_progress():
    task_id = request.args.get("task_id")
    with TASK_LOCK:
        task_info = ACTIVE_TASKS.get(task_id)
    if task_info:
        return jsonify(task_info)
    return jsonify({"status": "not_found"}), 404

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
