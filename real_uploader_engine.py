import os, sys, json, time, subprocess, glob
from datetime import datetime

# SAU (social-auto-upload) 安装路径：优先读环境变量 SAU_ROOT，
# 回退到本机历史路径。这样工具在其它机器/用户环境下也能开箱即用，无需硬编码。
SAU_ROOT = os.environ.get("SAU_ROOT", "/Users/martin/social-auto-upload")
SAU_VENV_BIN = f"{SAU_ROOT}/.venv/bin"
SAU_CLI = f"{SAU_VENV_BIN}/sau"
SAU_PYTHON = f"{SAU_VENV_BIN}/python"

def _run_with_progress(cmd, env, cwd, timeout, on_progress=None):
    """运行子进程并实时回传进度与日志行。
    on_progress(pct, log_line) —— pct 为推断进度(0-90)，log_line 为最新一行日志(可为None)。
    返回 (returncode, combined_output)。"""
    import subprocess as sp, time
    try:
        proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, text=True,
                        env=env, cwd=cwd, bufsize=1)
    except Exception as e:
        return -1, f"启动进程失败: {e}"
    logs = []
    pct = 40
    last_tick = time.time()
    while True:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line and proc.poll() is not None:
            break
        if line:
            line = line.strip()
            if line:
                logs.append(line)
                low = line.lower()
                if "upload" in low or "上传" in line:
                    pct = max(pct, 55)
                elif "progress" in low or "进度" in line or "%" in line:
                    pct = max(pct, 70)
                elif "publish" in low or "发布" in line or "成功" in line:
                    pct = max(pct, 85)
                if on_progress:
                    try: on_progress(pct, line)
                    except Exception: pass
        now = time.time()
        if now - last_tick > 4:
            pct = min(pct + 2, 90)
            last_tick = now
            if on_progress:
                try: on_progress(pct, None)
                except Exception: pass
    rc = proc.wait()
    return rc, "\n".join(logs[-800:])

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "platform_credentials.json")

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
    local_cookies_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies")

    possible_files = [f"{platform_id}_default.json"]
    if platform_id in ["tiktok", "tk"]:
        possible_files = ["tk_default.json", "tiktok_default.json"]
    elif platform_id in ["x", "twitter"]:
        possible_files = ["x_default.json", "twitter_default.json"]

    found_file = None
    for d in [sau_cookies_dir, local_cookies_dir]:
        for pf in possible_files:
            target = os.path.join(d, pf)
            if os.path.exists(target) and os.path.getsize(target) >= 50:
                found_file = target
                break
        if found_file:
            break

    if not found_file:
        return False, "🔑 需扫码登录"

    # 特殊平台深度 Cookie Token 校验
    if platform_id == "zhihu":
        try:
            with open(found_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cookies = data.get("cookies", [])
            has_zc0 = any(c.get("name") == "z_c0" for c in cookies)
            if not has_zc0:
                return False, "🔑 需扫码登录 (缺少 z_c0 密钥)"
        except Exception:
            return False, "🔑 需扫码登录"

    return True, "✅ 已登录"

class RealPlatformUploader:
    def __init__(self, platform_id, video_path, title, desc, tags=None):
        self.platform_id = platform_id
        self.video_path = os.path.abspath(video_path)
        self.title = title
        self.desc = desc
        # 默认标签留空：本工具是通用的，文案/标签应由 campaign.json 或 Web 控制台提供。
        # 不再写入任何具体产品/品牌词，避免污染通用工具。
        self.tags = tags or []

    def execute_upload(self, on_progress=None):
        log_time = datetime.now().strftime('%H:%M:%S')
        print(f"[{log_time}] 启动 Workbuddy 融合自动化引擎: {self.platform_id}...")

        sau_platforms = ["douyin", "kuaishou", "xiaohongshu", "tencent", "bilibili", "youtube"]
        custom_platforms = ["x", "linkedin", "facebook", "tiktok", "instagram",
                            "weibo", "zhihu", "toutiao"]

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

            if self.platform_id == "bilibili":
                # B站必须用真实 TTY，用 script 伪终端包裹执行
                cmd += ["--tid", "188"]
                inner_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
                script_cmd = ["script", "-q", "/dev/null", "/bin/bash", "-c",
                              f"export PYTHONPATH={SAU_ROOT}; {inner_cmd}"]
                print(f"执行 B站 (pseudo-TTY) 指令")
                try:
                    rc, output = _run_with_progress(script_cmd, env, SAU_ROOT, 600, on_progress)
                    tail = output[-400:]
                    print(f"sau bilibili 输出: {tail}")
                    ok = rc == 0 or "成功" in output or "upload" in output.lower()
                    if ok:
                        return {"success": True, "pub_id": f"sau_bilibili_{int(time.time())}",
                                "link": creator_links["bilibili"], "msg": "✅ B站发布成功"}
                    else:
                        return {"success": False, "error": f"B站 ({rc}): {tail[-200:]}"}
                except Exception as e:
                    return {"success": False, "error": f"B站 pseudo-TTY 异常: {str(e)}"}

            elif self.platform_id == "tencent":
                # 视频号：先试 headless（Cookie 有效时可行），失败再 headed
                for mode in ["--headless", "--headed"]:
                    cmd_try = cmd + [mode]
                    print(f"执行 视频号 ({mode}) 指令")
                    try:
                        rc, output = _run_with_progress(cmd_try, env, SAU_ROOT, 600, on_progress)
                        tail = output[-400:]
                        print(f"sau tencent ({mode}) 输出: {tail[-200:]}")
                        cookie_expired = "cookie 已失效" in output or "重新登录" in output or "login" in output.lower()
                        if cookie_expired and mode == "--headless":
                            print("视频号 Cookie 过期，切换 headed 模式重试...")
                            continue
                        ok = rc == 0 or ("成功" in output and not cookie_expired)
                        if ok:
                            return {"success": True, "pub_id": f"sau_tencent_{int(time.time())}",
                                    "link": creator_links["tencent"], "msg": "✅ 视频号发布成功"}
                        else:
                            return {"success": False, "error": f"视频号 Cookie 已过期，请在控制台点击【刷新登录】扫码"}
                    except Exception as e:
                        return {"success": False, "error": f"视频号异常: {str(e)}"}

            else:
                # 其余平台 (douyin/kuaishou/xiaohongshu/youtube) 走 --headless
                cmd += ["--headless"]
                print(f"执行 sau CLI (headless) 指令: {' '.join(cmd)}")
                try:
                    rc, output = _run_with_progress(cmd, env, SAU_ROOT, 600, on_progress)
                    tail = output[-400:]
                    print(f"sau {self.platform_id} 输出: {tail}")
                    if rc == 0:
                        return {
                            "success": True,
                            "pub_id": f"sau_{self.platform_id}_{int(time.time())}",
                            "link": creator_links.get(self.platform_id, "#"),
                            "msg": f"✅ 成功通过 sau 引擎静默发布到 {self.platform_id}！"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"sau 发布提示 ({rc}): {tail[-200:]}"
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
                "tiktok":    "tiktok_adapter",
                "weibo":     "weibo_uploader",
                "zhihu":     "zhihu_uploader",
                "toutiao":   "toutiao_uploader",
            }
            module_name = module_map.get(self.platform_id, f"{self.platform_id}_uploader")
            custom_links = {
                "weibo":   "https://weibo.com/u/",
                "zhihu":   "https://www.zhihu.com/creator/",
                "toutiao": "https://mp.toutiao.com/profile_v4/",
                "x":       "https://twitter.com/",
                "linkedin":"https://www.linkedin.com/feed/",
                "facebook":"https://www.facebook.com/",
                "tiktok":  "https://www.tiktok.com/",
            }
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
            print(f"执行 custom_uploader: {self.platform_id}")
            env = os.environ.copy()
            env["PYTHONPATH"] = SAU_ROOT
            env["OMP_PUBLISH_ARGS"] = args_payload

            try:
                rc, output = _run_with_progress(cmd, env, SAU_ROOT, 600, on_progress)
                print(f"custom {self.platform_id} 输出: {output[-300:]}")

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
