#!/usr/bin/env python3
"""
一次性扫码登录管理器
原理：用 sau <platform> login --headless 打开无头浏览器，截取登录二维码图片，
      通过 Flask SSE 推送给前端展示，用户手机扫码后 Cookie 自动保存。
      Cookie 有效后，所有上传任务完全无头后台运行。
"""
import os, sys, json, time, subprocess, threading, base64, asyncio, tempfile
from pathlib import Path

from omp_paths import sau_root, sau_cli, sau_python, venv_bin, biliup  # noqa: E402

SAU_ROOT = sau_root()
SAU_VENV_BIN = venv_bin()
SAU_CLI = sau_cli()
SAU_PYTHON = sau_python()
COOKIES_DIR = f"{SAU_ROOT}/cookies"

# 各平台 Cookie 文件
COOKIE_FILES = {
    "douyin":      f"{COOKIES_DIR}/douyin_default.json",
    "kuaishou":    f"{COOKIES_DIR}/kuaishou_default.json",
    "xiaohongshu": f"{COOKIES_DIR}/xiaohongshu_default.json",
    "tencent":     f"{COOKIES_DIR}/tencent_default.json",
    "bilibili":    f"{COOKIES_DIR}/bilibili_default.json",
    "weibo":       f"{COOKIES_DIR}/weibo_default.json",
    "zhihu":       f"{COOKIES_DIR}/zhihu_default.json",
    "toutiao":     f"{COOKIES_DIR}/toutiao_default.json",
}

# Cookie 有效期检查（文件存在且非空且不超过14天）
def is_cookie_valid(platform_id):
    cf = COOKIE_FILES.get(platform_id)
    if not cf or not os.path.exists(cf):
        return False
    if os.path.getsize(cf) < 50:
        return False
    mtime = os.path.getmtime(cf)
    age_days = (time.time() - mtime) / 86400
    if age_days > 14:
        return False
    # 快速验证：检查 JSON 里是否有有效 cookies
    try:
        with open(cf) as f:
            data = json.load(f)
        cookies = data.get("cookies", [])
        return len(cookies) > 0
    except Exception:
        return False

def get_all_cookie_status():
    """返回所有平台的 cookie 状态"""
    status = {}
    for pid in COOKIE_FILES:
        valid = is_cookie_valid(pid)
        cf = COOKIE_FILES[pid]
        mtime_str = ""
        if os.path.exists(cf):
            mtime = os.path.getmtime(cf)
            mtime_str = time.strftime("%m-%d %H:%M", time.localtime(mtime))
        status[pid] = {
            "valid": valid,
            "cookie_file": cf,
            "last_update": mtime_str,
            "status_text": f"✅ Cookie 有效（{mtime_str}）" if valid else "⚠️ Cookie 已过期，需扫码刷新"
        }
    return status


# ─────────────────────────────────────────────
# 无头扫码登录（核心）
# ─────────────────────────────────────────────
class HeadlessQRLogin:
    """
    用 sau login --headless 启动无头浏览器，监控截图目录，
    把二维码图片 base64 推送给前端，用户扫码后等待 Cookie 保存。
    """
    def __init__(self, platform_id, progress_callback=None):
        self.platform_id = platform_id
        self.progress_callback = progress_callback or (lambda msg, pct, img=None: None)
        self.qr_image_b64 = None
        self.success = False
        self.error = None

    def _emit(self, msg, pct, img_b64=None):
        self.progress_callback(msg, pct, img_b64)

    def run(self):
        pid = self.platform_id
        env = os.environ.copy()
        env["PYTHONPATH"] = SAU_ROOT

        # 临时截图目录
        qr_dir = tempfile.mkdtemp(prefix=f"qr_{pid}_")
        qr_path = os.path.join(qr_dir, "qr.png")

        self._emit(f"正在启动 {pid} 无头登录流程...", 10)

        # 特殊平台处理
        if pid == "bilibili":
            # B站用 biliup login，会输出二维码到终端（ASCII），我们截获
            self._emit("B站需要扫码登录，正在生成二维码...", 20)
            cmd = [biliup(), "login"]
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=env, cwd=SAU_ROOT
                )
                output_lines = []
                for line in proc.stdout:
                    output_lines.append(line.strip())
                    if "qrcode" in line.lower() or "二维码" in line or "scan" in line.lower():
                        self._emit(f"B站二维码已生成，请用手机扫码", 50)
                    if "success" in line.lower() or "成功" in line:
                        self._emit("✅ B站登录成功！Cookie 已保存", 100)
                        self.success = True
                        break
                proc.wait(timeout=120)
                if not self.success:
                    output = "\n".join(output_lines[-10:])
                    self._emit(f"B站登录输出: {output}", 80)
                    self.success = proc.returncode == 0
            except Exception as e:
                self.error = str(e)
                self._emit(f"B站登录异常: {e}", 100)
            return self.success

        # sau login --headless（抖音/快手/小红书/视频号）
        # 通过 Playwright 截图捕获二维码
        login_script = f"""
import asyncio, os, base64, time, sys
sys.path.insert(0, '{SAU_ROOT}')
from pathlib import Path

async def capture_qr():
    from patchright.async_api import async_playwright
    login_urls = {{
        'douyin': 'https://creator.douyin.com/creator-micro/home',
        'kuaishou': 'https://cp.kuaishou.com/article/publish/video',
        'xiaohongshu': 'https://creator.xiaohongshu.com/login',
        'tencent': 'https://channels.weixin.qq.com/login.html',
        'weibo': 'https://weibo.com/login.php',
        'zhihu': 'https://www.zhihu.com/signin',
        'toutiao': 'https://mp.toutiao.com/auth/page/login',
    }}
    cookie_files = {{
        'douyin': '{SAU_ROOT}/cookies/douyin_default.json',
        'kuaishou': '{SAU_ROOT}/cookies/kuaishou_default.json',
        'xiaohongshu': '{SAU_ROOT}/cookies/xiaohongshu_default.json',
        'tencent': '{SAU_ROOT}/cookies/tencent_default.json',
        'weibo': '{SAU_ROOT}/cookies/weibo_default.json',
        'zhihu': '{SAU_ROOT}/cookies/zhihu_default.json',
        'toutiao': '{SAU_ROOT}/cookies/toutiao_default.json',
    }}
    
    platform = '{pid}'
    url = login_urls[platform]
    cookie_file = cookie_files[platform]
    qr_path = '{qr_path}'
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={{"width": 1280, "height": 800}})
        page = await context.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30000)
        
        # 等待二维码出现并截图
        for _ in range(20):
            # 尝试找二维码元素
            qr_selectors = [
                'canvas[class*="qr"]', 'img[class*="qr"]', 
                '.qrcode', '.login-qrcode', '[class*="qrcode"]',
                'canvas', 'img[src*="qr"]', '.wx-qr', '.weixin-qr',
            ]
            for sel in qr_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible():
                        await el.screenshot(path=qr_path)
                        print(f"QR_CAPTURED:{qr_path}")
                        break
                except:
                    pass
            
            if os.path.exists(qr_path):
                break
                
            # 截取整页作为后备
            await page.screenshot(path=qr_path)
            print(f"PAGE_SCREENSHOT:{qr_path}")
            break
            
            await asyncio.sleep(2)
        
        # 等待登录成功（检测 URL 变化或成功标志）
        deadline = time.time() + 180  # 3分钟超时
        while time.time() < deadline:
            current_url = page.url
            # 检测是否跳出登录页
            if 'login' not in current_url.lower() and 'signin' not in current_url.lower():
                state = await context.storage_state()
                import json
                Path(cookie_file).parent.mkdir(parents=True, exist_ok=True)
                with open(cookie_file, 'w') as f:
                    json.dump(state, f, indent=2, ensure_ascii=False)
                print(f"LOGIN_SUCCESS:{cookie_file}")
                break
            await asyncio.sleep(2)
        else:
            print("LOGIN_TIMEOUT")
        
        await browser.close()

asyncio.run(capture_qr())
"""
        self._emit(f"正在打开 {pid} 登录页，等待二维码...", 20)

        proc = subprocess.Popen(
            [SAU_PYTHON, "-c", login_script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, cwd=SAU_ROOT
        )

        qr_sent = False
        start = time.time()
        while proc.poll() is None and (time.time() - start) < 200:
            line = proc.stdout.readline().strip()
            if not line:
                time.sleep(0.5)
                continue

            if "QR_CAPTURED" in line or "PAGE_SCREENSHOT" in line:
                if os.path.exists(qr_path) and not qr_sent:
                    with open(qr_path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode()
                    self.qr_image_b64 = img_b64
                    self._emit(f"📱 请用手机扫描下方二维码登录 {pid}", 50, img_b64)
                    qr_sent = True

            elif "LOGIN_SUCCESS" in line:
                self._emit(f"✅ {pid} 登录成功！Cookie 已保存，后续发布将完全后台静默", 100)
                self.success = True

            elif "LOGIN_TIMEOUT" in line:
                self._emit(f"⏰ {pid} 扫码超时（3分钟），请重试", 100)

        proc.terminate()
        return self.success


def run_qr_login(platform_id, progress_callback=None):
    """公开接口：启动无头扫码登录流程"""
    login = HeadlessQRLogin(platform_id, progress_callback)
    return login.run()
