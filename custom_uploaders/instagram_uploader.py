# -*- coding: utf-8 -*-
"""Instagram 视频上传器（集成开源 instagrapi 移动 API 接口与 Patchright 兜底）。

开源反爬与隐身方案：
1. 首选方案：集成开源成熟库 `instagrapi`，使用官方 Mobile Private API 直接提取 SessionID 提交 Reels 视频。
   绕过了网页端（Web UI）在 headless 模式下的反自动化与创建弹窗压制问题；
2. 备选方案：保留基于 Patchright CDP 隐身浏览器模式的 Web 端自动化发布。
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from custom_uploaders.base import (
    account_file, launch, load_context, save_cookies, login_flow, YT_PROXY,
)


PLATFORM = "instagram"
LOGIN_URL = "https://www.instagram.com/accounts/login/"
CREATE_URL = "https://www.instagram.com/"


def login(headless: bool = False, timeout: int = 600) -> bool:
    return asyncio.run(login_flow(PLATFORM, LOGIN_URL, account_file(PLATFORM), headless, timeout, proxy=YT_PROXY))


def _try_upload_via_instagrapi(video_path: str, caption: str, cookie_path: str, proxy: str | None = None) -> bool:
    """快轨通道：使用开源 instagrapi (4.2k+ Stars) 移动 API 进行 Reels 极速静默上传。"""
    try:
        from instagrapi import Client
        cl = Client()
        if proxy:
            cl.set_proxy(proxy)

        if not os.path.exists(cookie_path):
            return False

        with open(cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        sessionid = None
        for c in cookies:
            if c.get("name") == "sessionid":
                sessionid = c.get("value")
                break

        if not sessionid:
            print("[Instagram instagrapi] 未在 saved cookies 中提取到 sessionid")
            return False

        print("[Instagram instagrapi] 正在连通 Instagram Mobile API...")
        cl.login_by_sessionid(sessionid)

        print("[Instagram instagrapi] 正在提交 Reels 视频...")
        media = cl.clip_upload(video_path, caption=caption)
        if media and getattr(media, "pk", None):
            print(f"[Instagram instagrapi] 🎉 Reels 视频通过 Mobile API 极速发布成功！Media PK: {media.pk}")
            return True
    except Exception as e:
        print(f"[Instagram instagrapi] 移动 API 通道重试回退 (切换至 Patchright Web 兜底): {e}")
    return False


async def _dismiss_overlays(page):
    for sel in ['button:has-text("Not Now")', 'button[aria-label="Close"]',
                'button:has-text("Cancel")', '[role="button"]:has-text("OK")',
                '[role="button"]:has-text("Got it")', '[role="button"]:has-text("Not now")']:
        for _ in range(2):
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible(timeout=1500):
                    await btn.click(force=True)
                    await page.wait_for_timeout(600)
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


async def upload_web_fallback(video_path: str, caption: str, headless: bool = True, timeout: int = 180) -> bool:
    """慢轨通道：基于 Patchright CDP 隐匿浏览器的 Web 端兜底上传。"""
    cookie_path = account_file(PLATFORM)
    pw, browser = await launch(headless=headless, proxy=YT_PROXY)
    context = await load_context(browser, cookie_path)
    page = await context.new_page()
    try:
        await page.goto("https://www.instagram.com/create/select/?media_type=1", wait_until="domcontentloaded")
        await _dismiss_overlays(page)
        await page.wait_for_timeout(3000)

        file_input = page.locator('input[type="file"]').first
        try:
            await file_input.wait_for(state="attached", timeout=12000)
        except Exception:
            print("[Instagram Web] 未出现文件选择框（可能被 Web 端反自动化压制）")
            return False
        await file_input.set_input_files(video_path)
        print("[Instagram Web] 已选择视频文件，等待处理...")
        await page.wait_for_timeout(10000)

        for _ in range(3):
            clicked = await _click_visible(page, [
                'button:has-text("下一步")', 'button:has-text("Next")',
                '[role="button"]:has-text("下一步")', '[role="button"]:has-text("Next")',
            ])
            if clicked:
                await page.wait_for_timeout(5000)

        try:
            editor = page.locator('textarea, div[contenteditable="true"]').first
            if await editor.count():
                await editor.click()
                await editor.fill(caption)
        except Exception:
            pass

        await page.wait_for_timeout(2000)
        shared = await _click_visible(page, [
            'button:has-text("分享")', 'button:has-text("Share")',
            '[role="button"]:has-text("分享")', '[role="button"]:has-text("Share")',
        ])
        if not shared:
            print("[Instagram Web] 未找到「分享」按钮")
            return False

        try:
            await page.wait_for_url("**/p/**", timeout=18000)
            print("[Instagram Web] ✅ 视频已发布")
            return True
        except Exception:
            page_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
            if "已发布" in page_text or "Your post" in page_text or "shared" in page_text.lower():
                print("[Instagram Web] ✅ 视频已发布")
                return True
            return False
    except Exception as e:
        print(f"[Instagram Web] upload error: {repr(e)[:200]}")
        return False
    finally:
        await browser.close()
        try:
            await pw.stop()
        except Exception:
            pass


async def upload(video_path: str, title: str, tags: list[str] | None = None,
                 desc: str | None = None, headless: bool = True, timeout: int = 180) -> bool:
    caption = f"{title or ''}"
    if desc:
        caption = f"{caption}\n{desc}"
    if tags:
        caption += "\n" + " ".join(f"#{t}" for t in tags[:10])

    cookie_path = account_file(PLATFORM)

    # 1. 优先调用开源 instagrapi 移动 API 极速发布
    if _try_upload_via_instagrapi(video_path, caption, cookie_path, YT_PROXY):
        return True

    # 2. 移动 API 失败或未连通时，回退到 Patchright Web 隐形浏览器发布
    print("[Instagram] 切换至 Patchright Web 隐匿浏览器尝试发布...")
    return await upload_web_fallback(video_path, caption, headless=headless, timeout=timeout)


def publish(video_path: str, title: str, tags: list[str] | None = None,
            desc: str | None = None) -> bool:
    return asyncio.run(upload(video_path, title, tags, desc))