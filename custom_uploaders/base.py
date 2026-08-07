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
import sys
from pathlib import Path

from patchright.async_api import async_playwright
from utils.base_social_media import set_init_script

SAU_ROOT = Path(__file__).resolve().parent.parent
COOKIES_DIR = SAU_ROOT / "cookies"

# patchright 启动的 chromium 默认 UA 带 "HeadlessChrome" 字样，会被 YouTube Studio 等站点
# 判定为"不受支持的浏览器"而拒绝渲染（上传框打不开）。统一改成正常 Chrome UA 绕过检测。
# 版本号与已装 chromium 保持一致即可（YouTube 仅要求"足够新"）。
CHROME_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/145.0.7632.6 Safari/537.36")

# 各平台用于判定"已登录"的会话 cookie 名
SESSION_COOKIES: dict[str, list[str]] = {
    "x": ["auth_token", "ct0"],
    "linkedin": ["li_at"],
    "instagram": ["sessionid"],
    "facebook": ["c_user", "xs"],
    "tk": ["sid_tt", "sessionid_ss", "tt_csrf_token"],
}


def account_file(platform: str, name: str = "default") -> Path:
    """返回该平台的 cookie 存储文件路径，并确保父目录存在。"""
    p = COOKIES_DIR / f"{platform}_{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


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


# 统一视口大小。太小（如默认 1280x720）会导致 FB 首页"What's on your mind?"编辑器不渲染。
_VIEWPORT = {"width": 1920, "height": 1080}


async def load_context(browser, cookie_path: Path | None = None):
    """新建 context；若 cookie_path 存在则直接注入登录态。

    注意：不调用 set_init_script()。patchright 自带 stealth 能力已足够，
    而 set_init_script 会注入自定义 JS，导致 FB 首页"What's on your mind?"按钮不可见。
    """
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
    cookie_path = Path(cookie_path)
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    state = await context.storage_state()
    cookie_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


async def login_flow(
    platform: str,
    login_url: str,
    cookie_path: Path,
    headless: bool = False,
    timeout: int = 600,
    proxy: str | None = None,
) -> bool:
    """通用登录流程：开浏览器 → 进入登录页 → 轮询直到出现会话 cookie → 存盘。

    headless=False 时会弹出真实窗口，由用户手动完成扫码/输密登录。
    登录成功自动存 cookies/{platform}_default.json，返回 True。
    国内访问 X/领英/FB/IG 等需经 proxy（如 http://127.0.0.1:7890）。
    """
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


def run(coro):
    """同步入口：在已有事件循环外安全跑协程。"""
    return asyncio.run(coro)
