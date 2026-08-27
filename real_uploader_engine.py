import os, sys, json, time, subprocess, glob
from datetime import datetime

# SAU (social-auto-upload) 安装路径：优先读环境变量 SAU_ROOT，
# 默认 ~/social-auto-upload（自动展开用户主目录），任意机器/用户均可开箱即用。
# 跨平台路径（Windows 的 .venv/Scripts vs POSIX 的 .venv/bin）统一由 omp_paths 解析。
from omp_paths import sau_root, sau_cli, sau_python, data_dir  # noqa: E402

SAU_ROOT = sau_root()
SAU_CLI = sau_cli()
SAU_PYTHON = sau_python()

# 正在运行的子进程注册表：供 /api/cancel-task 取消上传使用
_RUNNING_PROCS = {}

def cancel_running_task(task_id):
    """尽力终止指定任务正在运行的子进程，返回是否真的 kill 成功。"""
    proc = _RUNNING_PROCS.get(task_id)
    if proc and proc.poll() is None:
        try:
            proc.kill()
            return True
        except Exception:
            return False
    return False

def _run_with_progress(cmd, env, cwd, timeout, on_progress=None, task_id=None, current_stage="上传中"):
    """运行子进程并实时回传进度与日志行。

    on_progress(pct, log_line, stage, eta_sec)：
        - pct: 推断进度 (0-90)
        - log_line: 最新一行日志（可为 None）
        - stage: 当前阶段（"登录中" / "打开创作中心" / "上传视频" / "填文案" / "点发布"）
        - eta_sec: 预计剩余秒数（None 表示暂无足够数据）

    返回 (returncode, combined_output)。
    Windows 兼容：使用 universal_newlines=True (text=True) 统一换行符处理。
    task_id: 传入后会把子进程注册到 _RUNNING_PROCS，供取消接口 kill。
    """
    import subprocess as sp, time, sys
    try:
        proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, text=True,
                        env=env, cwd=cwd, bufsize=1,
                        # Windows 兼容性: 不显示黑框控制台窗口
                        **({"creationflags": sp.CREATE_NO_WINDOW} if sys.platform == "win32" else {}))
    except Exception as e:
        return -1, f"启动进程失败: {e}"
    if task_id:
        _RUNNING_PROCS[task_id] = proc
    logs = []
    pct = 40
    last_tick = time.time()
    last_output_time = time.time()
    start_time = time.time()
    # ETA: 用近 30s 内的速率推算 (pct_delta / time_delta)
    eta_sec = None
    last_pct_for_eta = pct
    last_time_for_eta = start_time
    detected_stage = current_stage
    while True:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line and proc.poll() is not None:
            break
        if line:
            last_output_time = time.time()  # 有新输出，重置计时
            line = line.strip()
            if line:
                logs.append(line)
                low = line.lower()
                # 阶段识别
                if any(k in low for k in ["login", "登录", "扫码", "二维码"]):
                    detected_stage = "登录中"
                    pct = max(pct, 50)
                elif any(k in low for k in ["open ", "navigate", "打开", "进入", "goto"]):
                    detected_stage = "打开创作中心"
                    pct = max(pct, 60)
                elif "upload" in low or "上传" in line:
                    detected_stage = "上传视频"
                    pct = max(pct, 70)
                elif "progress" in low or "进度" in line or "%" in line:
                    detected_stage = "上传视频（实时进度）"
                    pct = max(pct, 78)
                elif any(k in low for k in ["title", "tag", "desc", "标题", "标签", "描述"]):
                    detected_stage = "填文案/标签"
                    pct = max(pct, 85)
                elif "publish" in low or "发布" in line or "成功" in line:
                    detected_stage = "点发布"
                    pct = max(pct, 92)
                # ETA 计算
                now = time.time()
                if pct > last_pct_for_eta and (now - last_time_for_eta) > 1:
                    dpct = pct - last_pct_for_eta
                    dt = now - last_time_for_eta
                    rate = dpct / dt if dt > 0 else 0
                    if rate > 0 and pct < 95:
                        eta_sec = int((95 - pct) / rate)
                    last_pct_for_eta = pct
                    last_time_for_eta = now
                if on_progress:
                    try: on_progress(pct, line, detected_stage, eta_sec)
                    except Exception: pass
        now = time.time()
        if now - last_tick > 4:
            pct = min(pct + 2, 90)
            last_tick = now
            if on_progress:
                try: on_progress(pct, None, detected_stage, eta_sec)
                except Exception: pass
        # 超过 timeout 秒无输出 → 进程可能卡死，主动 kill
        if timeout and (now - last_output_time) > timeout:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
            _RUNNING_PROCS.pop(task_id, None)
            logs.append(f"[BRIDGE TIMEOUT] 进程 {timeout}s 后被终止")
            return -1, "\n".join(logs[-800:])
    rc = proc.wait()
    _RUNNING_PROCS.pop(task_id, None)
    if on_progress and rc == 0:
        try: on_progress(100, "完成", "发布完成", 0)
        except Exception: pass
    return rc, "\n".join(logs[-800:])

# 凭证文件：打包态下 __file__ 指向临时解压目录会丢数据，统一走 data_dir() 持久目录
CREDENTIALS_FILE = os.path.join(data_dir(), "platform_credentials.json")

def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_credentials(data):
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def check_profile_logged_in(platform_id):
    sau_cookies_dir = f"{SAU_ROOT}/cookies"
    local_cookies_dir = os.path.join(data_dir(), "cookies")

    possible_files = [f"{platform_id}_default.json"]
    if platform_id in ["tiktok", "tk"]:
        possible_files = ["tk_default.json", "tiktok_default.json"]
    elif platform_id in ["x", "twitter"]:
        possible_files = ["x_default.json", "twitter_default.json"]

    # API-key 平台凭据文件很小（几十字节），放宽大小阈值
    min_size = 10 if platform_id in ("devto", "wordpress", "telegram", "pinterest") else 50
    found_file = None
    for d in [sau_cookies_dir, local_cookies_dir]:
        for pf in possible_files:
            target = os.path.join(d, pf)
            if os.path.exists(target) and os.path.getsize(target) >= min_size:
                found_file = target
                break
        if found_file:
            break

    if not found_file:
        if platform_id in ("devto", "wordpress", "telegram", "pinterest"):
            return False, "🔑 需配置 API Key"
        return False, "🔑 需扫码登录"

    # API-key 平台（Dev.to / WordPress / Telegram / Pinterest）：凭据文件含对应字段即已配置
    if platform_id in ("devto", "wordpress", "telegram", "pinterest"):
        try:
            with open(found_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if platform_id == "devto" and data.get("api_key"):
                return True, "✅ 已配置"
            if platform_id == "wordpress" and data.get("app_password"):
                return True, "✅ 已配置"
            if platform_id == "telegram" and data.get("bot_token") and data.get("chat_id"):
                return True, "✅ 已配置"
            if platform_id == "pinterest" and data.get("access_token") and data.get("board_id"):
                return True, "✅ 已配置"
            return False, "🔑 需配置 API Key"
        except Exception:
            return False, "🔑 需配置 API Key"

    # 深度 Cookie Token 完整性与过期与否全面排查（实事求是，绝不假冒已登录）
    try:
        with open(found_file, "r", encoding="utf-8") as f:
            content = json.load(f)
        cookies = content.get("cookies", []) if isinstance(content, dict) else []
        if not cookies:
            return False, "🔑 需扫码登录"
            
        now = time.time()
        # 过滤已过期的 Cookie (expires <= 0 视为 session cookie，或未过期)
        valid_cookies = [c for c in cookies if c.get("expires", 0) <= 0 or c.get("expires", 0) > now]
        cookie_map = {c.get("name"): c.get("value") for c in valid_cookies if c.get("name")}
        
        if platform_id == "tencent":
            has_token = any(k in cookie_map and len(str(cookie_map[k])) > 5 for k in ["sessionid", "pass_ticket", "wxuin", "session_key"])
            if not has_token:
                return False, "🔑 Cookie 已失效 (需扫码)"
                
        elif platform_id == "douyin":
            has_token = any(k in cookie_map and len(str(cookie_map[k])) > 5 for k in ["sessionid_ss", "sessionid"])
            if not has_token:
                return False, "🔑 Cookie 已失效 (需扫码)"
                
        elif platform_id == "kuaishou":
            if "kuaishou.server.web_st" not in cookie_map:
                return False, "🔑 Cookie 已失效 (需扫码)"
                
        elif platform_id == "xiaohongshu":
            if "web_session" not in cookie_map:
                return False, "🔑 Cookie 已失效 (需扫码)"
                
        elif platform_id == "bilibili":
            if "SESSDATA" not in cookie_map:
                return False, "🔑 Cookie 已失效 (需扫码)"
                
        elif platform_id == "weibo":
            if "SUB" not in cookie_map:
                return False, "🔑 Cookie 已失效 (需扫码)"
                
        elif platform_id == "zhihu":
            if "z_c0" not in cookie_map:
                return False, "🔑 Cookie 已失效 (需扫码)"
    except Exception:
        return False, "🔑 凭证读取失败"

    return True, "✅ 已登录"

def _clean_error_text(output, rc):
    import re
    if not output:
        return f"引擎返回异常 (code {rc})"
    cleaned = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output)
    cleaned = re.sub(r'[\|\\/\-\<\>3]+', ' ', cleaned)
    cleaned = re.sub(r'Playwright Team.*', '', cleaned)
    
    if "cookie 已失效" in cleaned or "重新登录" in cleaned or "login" in cleaned.lower() or "passport" in cleaned.lower():
        return "Cookie 已失效，需扫码刷新"
    if "timeout" in cleaned.lower() or "超时" in cleaned:
        return "页面响应超时，请重试"
    
    lines = [l.strip() for l in cleaned.split('\n') if l.strip() and not l.strip().startswith('sau')]
    if lines:
        return lines[-1][:100]
    return f"引擎错误 ({rc})"

def _classify_failure(output, rc):
    """Classify failure into categories for better error handling."""
    import re
    if not output:
        return "unknown"

    cleaned = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output)
    cleaned = re.sub(r'[\|\\/\-\<\>3]+', ' ', cleaned)
    cleaned = re.sub(r'Playwright Team.*', '', cleaned)
    cleaned_lower = cleaned.lower()

    # Login/authentication failures
    if any(keyword in cleaned_lower for keyword in ["cookie 已失效", "重新登录", "login", "passport", "auth", "signin", "未登录", "session expired", "token invalid", "401", "403"]):
        return "login_failed"

    # Video format/codec issues
    if any(keyword in cleaned_lower for keyword in ["format", "codec", "分辨率", "视频格式", "不支持", "invalid format", "unsupported format", "h264", "h.264", "aac"]):
        return "video_format_unsupported"

    # Network/timeout issues
    if any(keyword in cleaned_lower for keyword in ["timeout", "超时", "network", "连接", "connection", "timed out", "net::err", "proxy", "err_proxy", "err_tunnel", "err_internet_disconnected", "err_connection", "err_name_not_resolved"]):
        return "network_timeout"

    # Platform-specific restrictions/limits
    if any(keyword in cleaned_lower for keyword in ["限制", "限额", "配额", "quota", "limit", "频繁", "太快", "过于频繁", "rate limit", "too many", "风控", "verify", "验证码", "captcha"]):
        return "platform_error"

    # File/access issues
    if any(keyword in cleaned_lower for keyword in ["文件不存在", "file not found", "无法访问", "access denied", "permission", "no such file", "eacces", "eperm"]):
        return "file_error"

    # Browser/automation 错误
    if any(keyword in cleaned_lower for keyword in ["browser", "chromium", "playwright", "patchright", "executable", "launch"]):
        return "platform_error"

    # Default to unknown
    return "unknown"


# 把分类 + 原始输出翻译成「用户能看懂的语言 + 三个可能原因 + 三个操作」
_FAILURE_HUMAN = {
    "login_failed": {
        "label": "登录已失效",
        "blame": "你的平台账号登录状态过期了",
        "reasons": [
            "上次登录过了太久（多数平台 7-30 天会过期）",
            "账号在别的设备上修改了密码",
            "平台风控系统认为当前 Cookie 有风险"
        ],
        "actions": [
            "点 🗑️ 清 Cookie 重扫，用账号重新扫码登录",
            "用 📥 导入 Cookie 让客服/运营给你导一份新的",
            "看右上 🎯 环境检测，确认代理和 Playwright 都没问题"
        ]
    },
    "video_format_unsupported": {
        "label": "视频格式不被支持",
        "blame": "平台不接受这个视频文件的编码或封装",
        "reasons": [
            "视频用了 H.265/HEVC（部分平台只支持 H.264）",
            "封装是 MKV/MOV/AVI 而不是 MP4",
            "音频编码是 AC3/DTS 而不是 AAC"
        ],
        "actions": [
            "用 HandBrake（免费）转码：H.264 + AAC + MP4 容器",
            "把分辨率压到 1080p 以内（部分平台限 4K）",
            "文件大小压到 800MB 以下（YouTube 限速更友好）"
        ]
    },
    "network_timeout": {
        "label": "网络连接超时",
        "blame": "OMP 没能成功连上平台服务器或中途断了",
        "reasons": [
            "你的代理软件（Clash/V2Ray 等）没开或端口不对",
            "视频文件太大（>500MB）上传中途被限速",
            "平台服务器在维护或你所在地区网络不稳"
        ],
        "actions": [
            "看右上 🎯 环境检测，X / YouTube / TikTok 三个域名都通才能发国际",
            "换更稳定的代理节点（美国/日本/新加坡优先）",
            "把视频压到 200MB 以下再发"
        ]
    },
    "platform_error": {
        "label": "平台侧错误",
        "blame": "平台拒绝了你的请求或触发了它的风控",
        "reasons": [
            "近期发布太频繁被限流（每个平台每天有上限）",
            "平台要求短信/邮箱二次验证",
            "视频内容触发了审核（标题/标签敏感词）"
        ],
        "actions": [
            "等 1-2 小时再发（多数限流会自动解除）",
            "改标题和标签，避免营销词（'最''第一''限时'）",
            "去平台 App 手动发一次，验证账号状态"
        ]
    },
    "file_error": {
        "label": "文件读取失败",
        "blame": "OMP 找不到你的视频文件或没权限读",
        "reasons": [
            "视频文件被移动、删除或重命名了",
            "文件权限不足（macOS 隔离子系统）",
            "文件路径含特殊字符（空格、中文）"
        ],
        "actions": [
            "重新上传视频文件到 OMP",
            "把视频放在 ~/Movies 或 ~/Downloads 等无空格路径",
            "看终端是否弹『无法访问』的 macOS 权限请求"
        ]
    },
    "unknown": {
        "label": "未分类错误",
        "blame": "遇到了一个不常见的失败原因",
        "reasons": [
            "可能是 SAU 上游变更了上传逻辑",
            "可能是平台上线了新反爬虫机制",
            "可能是网络抖动导致的中途异常"
        ],
        "actions": [
            "点 📋 复制日志，把失败摘要发到 GitHub issue",
            "等几分钟后点 🔁 重试一次",
            "看右上 🎯 环境检测，排除基础设施问题"
        ]
    }
}


def _humanize_failure(category, output=None):
    """返回 {"label", "blame", "reasons": [...], "actions": [...]}。"""
    cat = category or "unknown"
    info = _FAILURE_HUMAN.get(cat, _FAILURE_HUMAN["unknown"])
    out = dict(info)
    # 从原始输出里抓「最关键一句」给 blame 兜底
    if output:
        import re
        cleaned = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output)
        cleaned = re.sub(r'[\|\\/\-\<\>3]+', ' ', cleaned)
        lines = [l.strip() for l in cleaned.splitlines() if l.strip() and 'Playwright' not in l]
        if lines:
            # 找最长的「有意义的」一行作为摘录
            longest = max(lines, key=len)[:200]
            out["excerpt"] = longest
    return out

class RealPlatformUploader:
    def __init__(self, platform_id, video_path, title, desc, tags=None, cover_file=None):
        self.platform_id = platform_id
        self.video_path = os.path.abspath(video_path)
        self.title = title
        self.desc = desc
        self.cover_file = os.path.abspath(cover_file) if cover_file else None
        # 默认标签留空：本工具是通用的，文案/标签应由 campaign.json 或 Web 控制台提供。
        # 不再写入任何具体产品/品牌词，避免污染通用工具。
        self.tags = tags or []

    def execute_upload(self, on_progress=None, log_file=None, task_id=None):
        """执行上传。on_progress(pct, log_line, stage, eta_sec) 用于实时进度回传；
        log_file 若提供，引擎每一步的关键事件也会写入该文件以便排错。
        task_id 传入后，引擎会把正在运行的子进程注册到取消注册表。
        返回 dict：成功 {"success": True, ...}，失败 {"success": False, "error": ..., "failure_category": ..., "failure_human": {...}}。
        """
        try:
            r = self._execute_upload_impl(on_progress, log_file, task_id)
        except Exception as e:
            r = {"success": False, "error": f"引擎未捕获异常: {e}"}
        # 自动 enrich 失败分类和人类语言建议
        return _enrich_failure(r)

    def _execute_upload_impl(self, on_progress, log_file, task_id):
        def log(msg):
            line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
            print(line)  # 仍输出到控制台
            if log_file:
                try:
                    with open(log_file, "a", encoding="utf-8") as lf:
                        lf.write(line + "\n")
                except Exception:
                    pass

        log_time = datetime.now().strftime('%H:%M:%S')
        log(f"启动上传引擎: {self.platform_id}")

        sau_platforms = ["douyin", "kuaishou", "xiaohongshu", "tencent", "bilibili", "youtube"]
        custom_platforms = ["x", "linkedin", "facebook", "tiktok", "instagram",
                            "weibo", "zhihu", "toutiao", "baijiahao", "fanqie",
                            "devto", "wordpress", "telegram", "pinterest"]

        # Creator dashboard links per platform
        creator_links = {
            "douyin": "https://creator.douyin.com/content/upload",
            "kuaishou": "https://cp.kuaishou.com/article/publish/video",
            "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish",
            "tencent": "https://channels.weixin.qq.com/platform/post/create",
            "bilibili": "https://member.bilibili.com/platform/upload/video/frame",
            "youtube": "https://studio.youtube.com/",
        }

        if self.platform_id in sau_platforms:
            tags_str = ",".join(self.tags)
            cmd = [
                SAU_CLI, self.platform_id, "upload-video",
                "--account", "default",
                "--file", self.video_path,
                "--title", self.title,
                "--desc", self.desc,
                "--tags", tags_str
            ]

            env = os.environ.copy()
            env["PYTHONPATH"] = SAU_ROOT

            # Add --thumbnail if a cover image was provided (SAU platforms like
            # douyin/tencent/kuaishou/xiaohongshu/bilibili/youtube all support it).
            if self.cover_file and os.path.exists(self.cover_file):
                cmd += ["--thumbnail", self.cover_file]
                log(f"附带封面: {self.cover_file}")

            if self.platform_id == "bilibili":
                cmd += ["--tid", "188"]
                sys = __import__("sys")
                if sys.platform == "win32":
                    # Windows: 无 script 命令，直接运行
                    log("执行 B站 (Windows 直连模式)")
                    try:
                        rc, output = _run_with_progress(cmd, env, SAU_ROOT, 600, on_progress, task_id=task_id)
                    except Exception as e:
                        return {"success": False, "error": f"B站 执行异常: {str(e)}"}
                else:
                    # macOS / Linux: 用 script 伪终端
                    inner_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
                    script_cmd = ["script", "-q", "/dev/null", "/bin/bash", "-c",
                                  f"export PYTHONPATH={SAU_ROOT}; {inner_cmd}"]
                    log("执行 B站 (pseudo-TTY) 指令")
                    try:
                        rc, output = _run_with_progress(script_cmd, env, SAU_ROOT, 600, on_progress, task_id=task_id)
                    except Exception as e:
                        return {"success": False, "error": f"B站 pseudo-TTY 异常: {str(e)}"}
                tail = output[-400:]
                log(f"sau bilibili 输出: {tail}")
                ok = rc == 0 or "成功" in output or "upload" in output.lower()
                if ok:
                    return {"success": True, "pub_id": f"sau_bilibili_{int(time.time())}",
                            "link": creator_links["bilibili"], "msg": "✅ B站发布成功"}
                else:
                    return {"success": False, "error": f"B站 ({rc}): {tail[-200:]}"}

            elif self.platform_id == "tencent":
                # 视频号：严格 --headless 纯无头静默发布，禁止工作期间桌面弹窗打扰用户
                cmd_try = cmd + ["--headless"]
                log("执行 视频号 (--headless 纯无头) 指令")
                try:
                    rc, output = _run_with_progress(cmd_try, env, SAU_ROOT, 600, on_progress, task_id=task_id)
                    tail = output[-400:]
                    log(f"sau tencent (--headless) 输出: {tail[-200:]}")
                    cookie_expired = "cookie 已失效" in output or "重新登录" in output or "login" in output.lower()
                    ok = rc == 0 or ("成功" in output and not cookie_expired)
                    if ok:
                        return {"success": True, "pub_id": f"sau_tencent_{int(time.time())}",
                                "link": creator_links["tencent"], "msg": "✅ 视频号发布成功"}
                    else:
                        return {"success": False, "error": "视频号 Cookie 已过期，请在开始前补录扫码"}
                except Exception as e:
                    return {"success": False, "error": f"视频号异常: {str(e)}"}

            else:
                # 其余平台 (douyin/kuaishou/xiaohongshu/youtube) 走 --headless
                cmd += ["--headless"]
                log(f"执行 sau {self.platform_id} (headless)")
                try:
                    rc, output = _run_with_progress(cmd, env, SAU_ROOT, 600, on_progress, task_id=task_id)
                    tail = output[-400:]
                    log(f"sau {self.platform_id} 输出: {tail}")
                    if rc == 0:
                        return {
                            "success": True,
                            "pub_id": f"sau_{self.platform_id}_{int(time.time())}",
                            "link": creator_links.get(self.platform_id, "#"),
                            "msg": f"✅ 成功通过 sau 引擎静默发布到 {self.platform_id}！"
                        }
                    else:
                        clean_msg = _clean_error_text(output, rc)
                        return {
                            "success": False,
                            "error": f"发布失败 ({clean_msg})"
                        }
                except Exception as e:
                    return {"success": False, "error": f"sau 执行异常: {str(e)}"}

        elif self.platform_id in custom_platforms:
            # weibo/zhihu/toutiao 走各自自定义上传器
            module_map = {
                "x":         "x_uploader",
                "linkedin":  "linkedin_uploader",
                "instagram": "instagram_uploader",
                "facebook":  "facebook_uploader",
                "tiktok":    "tiktok_uploader",
                "tk":        "tiktok_uploader",
                "weibo":     "weibo_uploader",
                "zhihu":     "zhihu_uploader",
                "toutiao":   "toutiao_uploader",
                "baijiahao": "baijiahao_uploader",
                "fanqie":    "fanqie_uploader",
                "devto":     "devto_uploader",
                "wordpress": "wordpress_uploader",
                "telegram":  "telegram_uploader",
                "pinterest": "pinterest_uploader",
            }
            custom_links = {
                "weibo":   "https://weibo.com/u/",
                "zhihu":   "https://www.zhihu.com/creator/",
                "toutiao": "https://mp.toutiao.com/profile_v4/",
                "baijiahao": "https://baijiahao.baidu.com/",
                "fanqie":  "https://pugc.yueduwuxian.com/fqvideo/home/publish-video",
                "x":       "https://twitter.com/",
                "linkedin":"https://www.linkedin.com/feed/",
                "facebook":"https://www.facebook.com/",
                "tiktok":  "https://www.tiktok.com/",
                "devto":   "https://dev.to/dashboard",
                "wordpress": "{site}/wp-admin/edit.php",
                "telegram": "https://t.me/",
                "pinterest": "https://www.pinterest.com/",
            }
            module_name = module_map.get(self.platform_id)
            if not module_name:
                return {"success": False, "error": f"未找到 {self.platform_id} 的自定义上传器模块"}
            # 通过环境变量传递参数，避免把 desc 直接拼进执行代码（注入/语法风险）
            args_payload = json.dumps({
                "video": self.video_path,
                "title": self.title,
                "tags": self.tags,
                "desc": self.desc,
            }, ensure_ascii=False)
            code = (
                "import sys, os, json\n"
                f"sys.path.insert(0, {SAU_ROOT!r})\n"
                f"sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__))!r})\n"
                "payload = json.loads(os.environ['OMP_PUBLISH_ARGS'])\n"
                f"import custom_uploaders.{module_name} as uploader\n"
                "res = uploader.publish(payload['video'], payload['title'], payload['tags'], payload['desc'])\n"
                "print('CUSTOM_RESULT:', res)\n"
            )
            cmd = [SAU_PYTHON, "-c", code]
            log(f"执行 custom_uploader: {self.platform_id}")
            env = os.environ.copy()
            env["PYTHONPATH"] = SAU_ROOT
            env["OMP_PUBLISH_ARGS"] = args_payload

            try:
                rc, output = _run_with_progress(cmd, env, SAU_ROOT, 600, on_progress, task_id=task_id)
                log(f"custom {self.platform_id} 输出: {output[-300:]}")

                if "CUSTOM_RESULT: True" in output:
                    return {
                        "success": True,
                        "pub_id": f"custom_{self.platform_id}_{int(time.time())}",
                        "link": custom_links.get(self.platform_id, "#"),
                        "msg": f"✅ 成功发布到 {self.platform_id}！"
                    }
                else:
                    return {"success": False, "error": f"发布未成功: {output[-200:]}"}
            except Exception as e:
                return {"success": False, "error": f"自定义上传器异常: {str(e)}"}

        return {"success": False, "error": f"未知平台: {self.platform_id}"}

    # ↑ 这里是原 execute_upload 主体结束。所有失败 result 走 _enrich_failure 自动补分类和人类语言。


def _enrich_failure(result):
    """给失败的 result dict 补上 failure_category / failure_human / failure_excerpt。"""
    if result.get("success"):
        return result
    err = result.get("error", "") or ""
    cat = _classify_failure(err, result.get("rc", -1))
    human = _humanize_failure(cat, err)
    result["failure_category"] = cat
    result["failure_human"] = human
    return result
