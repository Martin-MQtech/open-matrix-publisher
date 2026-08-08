import os, sys, json, time, subprocess, threading
from flask import Flask, request, jsonify
from cookie_extractor import sync_all_platforms, sync_cookies_from_chrome
from real_uploader_engine import load_credentials, save_credentials, check_profile_logged_in, RealPlatformUploader

app = Flask(__name__)

# Active background upload tasks store & History Store
ACTIVE_TASKS = {}
TASK_LOCK = threading.Lock()
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "dispatch_history.json")

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
        sync_all_platforms()
    except Exception as e:
        print("Syncing cookies warning:", e)

    creds = load_credentials()
    session_status = {}
    rpa_platforms = ["douyin", "sph", "xhs", "kuaishou", "bilibili", "weibo", "haokan", "xigua"]
    
    for pid in rpa_platforms:
        is_logged, msg = check_profile_logged_in(pid)
        session_status[pid] = {
            "logged_in": is_logged,
            "status_text": "✅ 自动提取 Mac Chrome Cookie 成功" if is_logged else "📱 需扫码/暂无Cookie"
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

def _launch_login_thread(platform_id):
    uploader = RealPlatformUploader(platform_id, "富氢热灸贴营销短视频_中文配音版_v1_成片.mp4", "测试登录", "测试登录")
    uploader.execute_upload()

@app.route("/api/launch-login", methods=["POST"])
def launch_login():
    data = request.json or {}
    platform_id = data.get("platform_id", "sph")
    
    sync_cookies_from_chrome(platform_id)

    return jsonify({
        "status": "launched",
        "platform_id": platform_id,
        "msg": f"✅ 已成功从您的 Mac Chrome 浏览器直接提取【{platform_id}】的已有登录 Cookie！无需任何扫码。"
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

@app.route("/api/start-upload-task", methods=["POST"])
def start_upload_task():
    data = request.json or {}
    platform_id = data.get("platform_id")
    video_file = data.get("video_file", "富氢热灸贴营销短视频_中文配音版_v1_成片.mp4")
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
