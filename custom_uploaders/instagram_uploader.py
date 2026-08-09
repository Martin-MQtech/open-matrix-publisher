# -*- coding: utf-8 -*-
"""Instagram 视频上传器（桌面/移动网页端）。

⚠️ 状态：Instagram 网页端的创建上传对话框在 headless 浏览器中**无法正常渲染**。
多种诊断结果一致：
1. 桌面端 /create/select/ 和 /create/reel/ 都不渲染 create 对话框（页面 fallback 到 profile）；
2. 移动端模拟（iPhone UA）能渲染 create 页，但 /create/select/ 报错 "Only images can be posted"，
   /create/reel/ 也被重定向到随机用户主页；
3. 主页 "New post" SVG 点击不触发 file chooser（patchright + IG 反自动化协同拦截）；
4. 直接 set_input_files() 到隐藏 input 没有触发 IG 的上传管道。

结论：Instagram 网页端视频上传需在真实 Chrome 浏览器手动操作，或用 Instagram 移动 app。
本文件保留登录/cookie 维护能力，但 upload() 立即返回 False 并打印明确诊断信息。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from custom_uploaders.base import (
    account_file, launch, load_context, save_cookies, login_flow, YT_PROXY,
)


async def _wait_publish_enabled(page, btn, timeout: int = 240000):
    try:
        await btn.wait_for(state="enabled", timeout=timeout)
    except Exception:
        pass


PLATFORM = "instagram"
LOGIN_URL = "https://www.instagram.com/accounts/login/"
CREATE_URL = "https://www.instagram.com/"


def login(headless: bool = False, timeout: int = 600) -> bool:
    return asyncio.run(login_flow(PLATFORM, LOGIN_URL, account_file(PLATFORM), headless, timeout, proxy=YT_PROXY))


async def _dismiss_overlays(page):
    for sel in ['button:has-text("Not Now")', 'button[aria-label="Close"]',
                'button:has-text("Cancel")', '[role="button"]:has-text("OK")',
                '[role="button"]:has-text("Got it")', '[role="button"]:has-text("Not now")']:
        for attempt in range(3):
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible(timeout=2000):
                    await btn.click(force=True)
                    await page.wait_for_timeout(800)
            except Exception:
                break


async def _click_visible(page, selectors: list[str], force: bool = False):
    for sel in selectors:
        try:
            candidates = await page.locator(sel).all()
            for c in candidates:
                if await c.is_visible():
                    await c.click(force=force)
                    return True
        except Exception:
            continue
    return False


async def upload(video_path: str, title: str, tags: list[str] | None = None,
                desc: str | None = None, headless: bool = True, timeout: int = 180) -> bool:
    """Instagram headless 上传已确认被反自动化拦截（详见模块文档）。
    本函数快速诊断一次后立即返回 False，避免长时间空转。"""
    cookie_path = account_file(PLATFORM)
    pw, browser = await launch(headless=headless, proxy=YT_PROXY)
    context = await load_context(browser, cookie_path)
    page = await context.new_page()
    try:
        await page.goto("https://www.instagram.com/create/reel/", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        # 检测 1：URL 是否被重定向到 profile（无 create 弹窗 → 直接放弃）
        if "/create/" not in page.url or page.url.endswith("/create/reel/") is False and "/create/reel" not in page.url:
            print("[Instagram] ABORT: /create/reel/ didn't load — likely headless anti-automation")
            return False
        # 检测 2：页面是否出现 create 对话框（不是 profile 内容）
        btns = page.locator('[role="button"]')
        cnt = await btns.count()
        has_reel_dialog = False
        for i in range(min(cnt, 10)):
            try:
                text = await btns.nth(i).text_content(timeout=300)
                if text.strip() in ("Next", "下一步", "Share", "分享"):
                    has_reel_dialog = True
                    break
            except: pass
        if not has_reel_dialog:
            print("[Instagram] ABORT: create dialog not rendered (page shows profile feed instead)")
            return False
        # 即使到了这里，IG 的上传管道在 headless 仍可能失败；
        # 跑完整流程成本高但 99% 会失败，直接放弃以避免长时间空转。
        print("[Instagram] ABORT: IG headless create flow is unstable. Manual upload recommended.")
        return False
    except Exception as e:
        print(f"[Instagram] ABORT: {repr(e)[:200]}")
        return False
    finally:
        await browser.close()
        try:
            await pw.stop()
        except Exception:
            pass


def publish(video_path: str, title: str, tags: list[str] | None = None,
            desc: str | None = None) -> bool:
    return asyncio.run(upload(video_path, title, tags, desc))