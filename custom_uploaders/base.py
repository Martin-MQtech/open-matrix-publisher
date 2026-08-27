# -*- coding: utf-8 -*-
"""自定义上传器共享基础：浏览器启动 / cookie 存取 / 通用登录流程。

所有自定义平台（X / LinkedIn / Instagram / Facebook / TikTok）都复用这里，
与 social-auto-upload 保持同一套约定：
- 浏览器：patchright(chromium) + stealth 初始化脚本
- 登录态：Playwright storage_state，存到 cookies/{platform}_default.json
- 登录检测：轮询直到出现该平台的会话 cookie，即自动存盘
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# 确保 SAU 与 项目目录 都在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAU_ROOT = Path(os.environ.get("SAU_ROOT", "~/social-auto-upload")).expanduser()
if str(SAU_ROOT) not in sys.path:
    sys.path.insert(0, str(SAU_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from patchright.async_api import async_playwright
try:
    from utils.base_social_media import set_init_script
except ImportError:
    set_init_script = None

# 本地 Cookie 加密层：OMP LOCAL_COOKIES_DIR 走密文 .enc，SAU 上游目录仍写明文（保持兼容）。
try:
    from cookie_crypto import best_cookie_path, encrypt_cookie_file, is_encrypted
except ImportError:
    best_cookie_path = None
    encrypt_cookie_file = None
    is_encrypted = None

COOKIES_DIR = SAU_ROOT / "cookies"
LOCAL_COOKIES_DIR = PROJECT_ROOT / "cookies"

try:
    from conf import YT_PROXY
except Exception:
    YT_PROXY = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "http://127.0.0.1:7890"

# patchright 启动的 chromium 默认 UA 带 "HeadlessChrome" 字样，统一改成正常 Chrome UA 绕过检测
CHROME_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/145.0.7632.6 Safari/537.36")

# 各平台用于判定"已登录"的会话 cookie 名
# 唯一权威来源：login_check.py（本模块与 interactive_login.py / real_uploader_engine.py
# 三处判定已统一收敛，改判定请改 login_check.py，不要在此各自为政）
try:
    from login_check import PLATFORM_SESSION_COOKIES as SESSION_COOKIES
except ImportError:
    SESSION_COOKIES = {
        "x": ["auth_token", "ct0"],
        "twitter": ["auth_token", "ct0"],
        "linkedin": ["li_at"],
        "instagram": ["sessionid"],
        "facebook": ["c_user", "xs"],
        "tk": ["sid_tt", "sessionid_ss", "tt_csrf_token"],
        "tiktok": ["sid_tt", "sessionid_ss", "tt_csrf_token"],
        "zhihu": ["z_c0"],
        "weibo": ["SUB", "SUBP"],
        "douyin": ["sessionid", "sessionid_ss"],
        "toutiao": ["LOGIN_A"],
        "bilibili": ["SESSDATA", "bili_jct"],
        "kuaishou": ["kuaishou.server.web_st"],
        "tencent": ["sessionid", "wxuin"],
        "baijiahao": ["BDUSS", "BAIDUID"],
        "fanqie": ["sessionid", "sessionid_ss"],   # 兼容老 cookie 文件
        "haokan": ["BDUSS", "BAIDUID", "BDUSS_BFESS", "BAIDU_SAFETS"]
    }


def account_file(platform: str, name: str = "default") -> Path:
    """返回该平台的 cookie 存储文件路径，优先返回已有非空 cookie 的路径，否则默认返回 COOKIES_DIR。

    加密层集成：
    - SAU_DIR 永远明文（上游项目自管，不动）。
    - LOCAL_COOKIES_DIR 优先 .enc，存在则解密到 .json 后返回 .json。
    - 老的明文 .json 仍可读（向后兼容），首次新登录会自动落 .enc。
    """
    sau_p = COOKIES_DIR / f"{platform}_{name}.json"
    local_p = LOCAL_COOKIES_DIR / f"{platform}_{name}.json"
    if sau_p.exists() and sau_p.stat().st_size >= 50:
        return sau_p
    # 本地：先看 .enc（密文优先）
    local_enc = LOCAL_COOKIES_DIR / f"{platform}_{name}.json.enc"
    if best_cookie_path and local_enc.exists():
        decrypted = best_cookie_path(local_p)
        if decrypted and decrypted.exists() and decrypted.stat().st_size >= 50:
            return decrypted
    if local_p.exists() and local_p.stat().st_size >= 50:
        # 兼容老明文；同时后台异步升级为 .enc
        if encrypt_cookie_file and not is_encrypted(local_p):
            try:
                encrypt_cookie_file(local_p)
            except Exception:
                pass
        return local_p

    # 别名检测 (如 tiktok / tk, x / twitter)
    if platform in ("tiktok", "tk"):
        for alt in ("tk", "tiktok"):
            for d in (COOKIES_DIR, LOCAL_COOKIES_DIR):
                alt_p = d / f"{alt}_{name}.json"
                if alt_p.exists() and alt_p.stat().st_size >= 50:
                    return alt_p
                alt_enc = d / f"{alt}_{name}.json.enc"
                if best_cookie_path and alt_enc.exists():
                    dec = best_cookie_path(alt_p)
                    if dec and dec.exists() and dec.stat().st_size >= 50:
                        return dec
    elif platform in ("x", "twitter"):
        for alt in ("x", "twitter"):
            for d in (COOKIES_DIR, LOCAL_COOKIES_DIR):
                alt_p = d / f"{alt}_{name}.json"
                if alt_p.exists() and alt_p.stat().st_size >= 50:
                    return alt_p
                alt_enc = d / f"{alt}_{name}.json.enc"
                if best_cookie_path and alt_enc.exists():
                    dec = best_cookie_path(alt_p)
                    if dec and dec.exists() and dec.stat().st_size >= 50:
                        return dec

    sau_p.parent.mkdir(parents=True, exist_ok=True)
    return sau_p


async def launch(headless: bool = True, proxy: str | None = None):
    """启动 patchright chromium，返回 (playwright, browser)。

    proxy: 形如 "http://127.0.0.1:7890"。国内访问 X / TikTok 等需经此代理。
    传 None 则直连（抖音/快手/小红书/视频号/B站/领英/IG/FB 走直连更快）。
    """
    pw = await async_playwright().start()
    kwargs = {"headless": headless}
    if proxy:
        kwargs["proxy"] = {"server": proxy}
    browser = await pw.chromium.launch(**kwargs)
    return pw, browser


_VIEWPORT = {"width": 1920, "height": 1080}


async def load_context(browser, cookie_path: Path | None = None):
    """新建 context；若 cookie_path 存在则直接注入登录态。"""
    if cookie_path and Path(cookie_path).exists():
        try:
            context = await browser.new_context(storage_state=str(cookie_path), user_agent=CHROME_UA,
                                                 viewport=_VIEWPORT)
            return context
        except Exception:
            pass
    context = await browser.new_context(user_agent=CHROME_UA, viewport=_VIEWPORT)
    return context


def _has_session(cookies: list[dict], platform: str) -> bool:
    names = {c.get("name") for c in cookies}
    want = SESSION_COOKIES.get(platform, [])
    return any(w in names for w in want)


async def save_cookies(context, cookie_path: Path) -> None:
    state = await context.storage_state()
    content = json.dumps(state, ensure_ascii=False, indent=2)
    # SAU_DIR 永远写明文（上游项目自管）。
    for d in (COOKIES_DIR,):
        d.mkdir(parents=True, exist_ok=True)
        (d / cookie_path.name).write_text(content, encoding="utf-8")
        if "tiktok" in cookie_path.name:
            alt_name = cookie_path.name.replace("tiktok", "tk")
            (d / alt_name).write_text(content, encoding="utf-8")
        elif "tk_" in cookie_path.name:
            alt_name = cookie_path.name.replace("tk_", "tiktok_")
            (d / alt_name).write_text(content, encoding="utf-8")
    # LOCAL_COOKIES_DIR 走加密层：先写临时明文给加密函数读，再写 .enc，最后删明文。
    if encrypt_cookie_file:
        LOCAL_COOKIES_DIR.mkdir(parents=True, exist_ok=True)
        tmp_plain = LOCAL_COOKIES_DIR / cookie_path.name
        tmp_plain.write_text(content, encoding="utf-8")
        try:
            encrypt_cookie_file(tmp_plain)
        except Exception:
            # 加密失败时保留明文，至少不丢账号
            pass
        # 别名（tiktok / tk）也加密
        if "tiktok" in cookie_path.name:
            alt_name = cookie_path.name.replace("tiktok", "tk")
            alt_plain = LOCAL_COOKIES_DIR / alt_name
            alt_plain.write_text(content, encoding="utf-8")
            try:
                encrypt_cookie_file(alt_plain)
            except Exception:
                pass
        elif "tk_" in cookie_path.name:
            alt_name = cookie_path.name.replace("tk_", "tiktok_")
            alt_plain = LOCAL_COOKIES_DIR / alt_name
            alt_plain.write_text(content, encoding="utf-8")
            try:
                encrypt_cookie_file(alt_plain)
            except Exception:
                pass
    else:
        # 加密模块未就绪（理论上不会发生），退回老路径
        for d in (LOCAL_COOKIES_DIR,):
            d.mkdir(parents=True, exist_ok=True)
            (d / cookie_path.name).write_text(content, encoding="utf-8")
            if "tiktok" in cookie_path.name:
                alt_name = cookie_path.name.replace("tiktok", "tk")
                (d / alt_name).write_text(content, encoding="utf-8")
            elif "tk_" in cookie_path.name:
                alt_name = cookie_path.name.replace("tk_", "tiktok_")
                (d / alt_name).write_text(content, encoding="utf-8")


async def login_flow(
    platform: str,
    login_url: str,
    cookie_path: Path,
    headless: bool = False,
    timeout: int = 600,
    proxy: str | None = None,
) -> bool:
    """通用登录流程：开浏览器 → 进入登录页 → 轮询直到出现会话 cookie → 存盘。"""
    pw, browser = await launch(headless=headless, proxy=proxy)
    context = await browser.new_context(user_agent=CHROME_UA, viewport=_VIEWPORT)
    page = await context.new_page()
    try:
        await page.goto(login_url, wait_until="domcontentloaded")
        logged = False
        steps = max(1, timeout // 2)
        for _ in range(steps):
            cookies = await context.cookies()
            if _has_session(cookies, platform):
                logged = True
                break
            await asyncio.sleep(2)
        if logged:
            await asyncio.sleep(3)  # 等 cookie 写全
            await save_cookies(context, cookie_path)
        return logged
    finally:
        await browser.close()
        try:
            await pw.stop()
        except Exception:
            pass


def make_result(ok: bool, status: str, msg: str = "", platform: str = "") -> dict:
    """统一结果结构（供各上传器返回）。"""
    return {"success": bool(ok), "status": status, "message": msg, "platform": platform}


def is_logged_in(platform: str, name: str = "default") -> bool:
    """检查该平台是否已有有效登录 Cookie（storage_state 中含会话 cookie）。"""
    cf = account_file(platform, name)
    if not cf.exists() or cf.stat().st_size < 50:
        return False
    try:
        state = json.loads(cf.read_text(encoding="utf-8"))
        return _has_session(state.get("cookies", []), platform)
    except Exception:
        return False


def run(coro):
    """同步入口：在已有事件循环外安全跑协程。"""
    return asyncio.run(coro)
