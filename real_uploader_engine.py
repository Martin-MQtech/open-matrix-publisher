import os, sys, json, time, subprocess, glob
from datetime import datetime

SAU_ROOT = "/Users/martin/social-auto-upload"
SAU_VENV_BIN = f"{SAU_ROOT}/.venv/bin"
SAU_CLI = f"{SAU_VENV_BIN}/sau"
SAU_PYTHON = f"{SAU_VENV_BIN}/python"

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
    cookie_file = os.path.join(sau_cookies_dir, f"{platform_id}_default.json")
    if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 10:
        return True, f"✅ 已载入 Workbuddy {platform_id} 登录凭证"
    
    # Fallback to local profile check
    profile_dir = os.path.expanduser(f"~/.config/codex_video_dispatch/chromium_profiles/{platform_id}")
    state_json = os.path.join(profile_dir, "state.json")
    if os.path.exists(state_json) and os.path.getsize(state_json) > 10:
        return True, "✅ 账号凭证已就绪"
        
    return False, "📱 需登录/凭证初始化"

class RealPlatformUploader:
    def __init__(self, platform_id, video_path, title, desc, tags=None):
        self.platform_id = platform_id
        self.video_path = os.path.abspath(video_path)
        self.title = title
        self.desc = desc
        self.tags = tags or ["富氢热灸贴", "木齐科技", "温氢双护"]

    def execute_upload(self):
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
                    proc = subprocess.run(script_cmd, capture_output=True, text=True, timeout=600, env=env, cwd=SAU_ROOT)
                    output = proc.stdout + "\n" + proc.stderr
                    tail = output[-400:]
                    print(f"sau bilibili 输出: {tail}")
                    ok = proc.returncode == 0 or "成功" in output or "upload" in output.lower()
                    if ok:
                        return {"success": True, "pub_id": f"sau_bilibili_{int(time.time())}",
                                "link": creator_links["bilibili"], "msg": "✅ B站发布成功"}
                    else:
                        return {"success": False, "error": f"B站 ({proc.returncode}): {tail[-200:]}"}
                except Exception as e:
                    return {"success": False, "error": f"B站 pseudo-TTY 异常: {str(e)}"}

            elif self.platform_id == "tencent":
                # 视频号：先试 headless（Cookie 有效时可行），失败再 headed
                for mode in ["--headless", "--headed"]:
                    cmd_try = cmd + [mode]
                    print(f"执行 视频号 ({mode}) 指令")
                    try:
                        proc = subprocess.run(cmd_try, capture_output=True, text=True, timeout=600, env=env, cwd=SAU_ROOT)
                        output = proc.stdout + "\n" + proc.stderr
                        tail = output[-400:]
                        print(f"sau tencent ({mode}) 输出: {tail[-200:]}")
                        cookie_expired = "cookie 已失效" in output or "重新登录" in output or "login" in output.lower()
                        if cookie_expired and mode == "--headless":
                            print("视频号 Cookie 过期，切换 headed 模式重试...")
                            continue
                        ok = proc.returncode == 0 or ("成功" in output and not cookie_expired)
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
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env, cwd=SAU_ROOT)
                    output = proc.stdout + "\n" + proc.stderr
                    tail = output[-400:]
                    print(f"sau {self.platform_id} 输出: {tail}")
                    if proc.returncode == 0:
                        return {
                            "success": True,
                            "pub_id": f"sau_{self.platform_id}_{int(time.time())}",
                            "link": creator_links.get(self.platform_id, "#"),
                            "msg": f"✅ 成功通过 sau 引擎静默发布到 {self.platform_id}！"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"sau 发布提示 ({proc.returncode}): {tail[-200:]}"
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
            code = f"""
import sys
sys.path.insert(0, '{SAU_ROOT}')
import custom_uploaders.{module_name} as uploader
res = uploader.publish('{self.video_path}', '{self.title}', {self.tags}, '''{self.desc}''')
print('CUSTOM_RESULT:', res)
"""
            cmd = [SAU_PYTHON, "-c", code]
            print(f"执行 custom_uploader: {self.platform_id}")
            env = os.environ.copy()
            env["PYTHONPATH"] = SAU_ROOT

            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env, cwd=SAU_ROOT)
                output = proc.stdout + "\n" + proc.stderr
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
