# -*- coding: utf-8 -*-
"""Facebook Reel 视频上传器（桌面网页端，三步流程）。

流程：
1. Create post 弹窗 → 加视频 + 写文案 → 点 "Next"（等 enabled）
2. Edit reel 页 → 点 "Next"（等 enabled）
3. 最终确认页 → 点 "Post"
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from custom_uploaders.base import (
    account_file, launch, load_context, save_cookies, login_flow, YT_PROXY,
)


PLATFORM = "facebook"
LOGIN_URL = "https://www.facebook.com/"
COMPOSE_URL = "https://www.facebook.com/"


def login(headless: bool = False, timeout: int = 600) -> bool:
    return asyncio.run(login_flow(PLATFORM, LOGIN_URL, account_file(PLATFORM), headless, timeout, proxy=YT_PROXY))


async def _click_enabled_next(page, label: str, max_wait_s: int = 240) -> bool:
    """在弹窗中查找并点击 enabled 的 Next 按钮。"""
    for _ in range(max_wait_s):
        all_next = page.locator('div[role="dialog"] [role="button"]:has-text("Next")')
        cnt = await all_next.count()
        for i in range(cnt):
            btn = all_next.nth(i)
            try:
                if await btn.is_visible(timeout=500) and await btn.is_enabled(timeout=500):
                    await btn.click(force=True)
                    print(f"[Facebook] clicked Next ({label})")
                    return True
            except Exception:
                pass
        await page.wait_for_timeout(1000)
    return False


async def upload(video_path: str, title: str, tags: list[str] | None = None,
                desc: str | None = None, headless: bool = True, timeout: int = 180) -> bool:
    cookie_path = account_file(PLATFORM)
    pw, browser = await launch(headless=headless, proxy=YT_PROXY)
    context = await load_context(browser, cookie_path)
    page = await context.new_page()
    try:
        await page.goto(COMPOSE_URL, wait_until="domcontentloaded")
        # Facebook 页面长连接不断，networkidle 永不触发 → 固定等待让页面 JS 就绪
        await page.wait_for_timeout(12000)
        await page.wait_for_timeout(2000)
        # 先关可能的弹窗/遮罩
        for sel in ['button:has-text("允许")', 'button:has-text("Allow")',
                    'button:has-text("Not Now")', '[role="button"]:has-text("OK")',
                    'button[aria-label="Close"]']:
            try:
                b = page.locator(sel).first
                if await b.count() and await b.is_visible(timeout=1500):
                    await b.click(force=True)
                    await page.wait_for_timeout(800)
            except Exception:
                pass

        # Step 1: 打开 composer 弹窗
        await page.wait_for_timeout(3000)
        wom_clicked = False
        for sel in ['[role="button"]:has-text("mind")',
                     'span:has-text("What")',
                     'div[role="button"]:has-text("What")']:
            try:
                wom = page.locator(sel).first
                if await wom.count():
                    await wom.wait_for(state="visible", timeout=10000)
                    await wom.click(force=True)
                    print("[Facebook] opened composer (What's on your mind)")
                    wom_clicked = True
                    await page.wait_for_timeout(3000)
                    break
            except Exception:
                continue
        if not wom_clicked:
            print("[Facebook] WARNING: What's on your mind not found, trying direct Photo/video")

        # Step 1: 点 Photo/video 并选文件
        # 大视频（>300MB）走 file chooser 会导致 patchright Node.js pipe 字符串溢出。
        # 策略：先尝试找隐藏的 input[type="file"] 直接 set_input_files（只传路径不走 IPC），
        # 如果找不到再用 file chooser 兜底（适合小文件）。
        clicked = False
        fi = page.locator('input[type="file"]').first
        if await fi.count():
            await fi.set_input_files(str(video_path))
            clicked = True
            print("[Facebook] video file set via hidden input")
        if not clicked:
            photo_selectors = [
                'div[role="dialog"] [role="button"]:has-text("Photo/video")',
                'div[role="dialog"] [role="button"]:has-text("照片/视频")',
                '[role="button"]:has-text("Photo/video")',
                '[role="button"]:has-text("照片/视频")',
            ]
            for sel in photo_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() and await btn.is_visible(timeout=3000):
                        async with page.expect_file_chooser(timeout=20000) as fc_info:
                            await btn.click(force=True)
                        await (await fc_info.value).set_files(str(video_path))
                        clicked = True
                        break
                except Exception:
                    continue
        if not clicked:
            raise Exception("Facebook: 未能触发视频文件选择")
        print("[Facebook] video file selected")
        await page.wait_for_timeout(2000)

        # Step 1: 填写文案（弹窗内的可编辑区域）
        caption = (desc or title) + ("\n" + " ".join(f"#{t}" for t in (tags or [])) if tags else "")
        editor = None
        try:
            editor = page.locator(
                'div[role="dialog"] [contenteditable="true"], '
                'div[role="dialog"] div[role="textbox"]'
            ).first
            await editor.wait_for(state="visible", timeout=300000)
        except Exception:
            try:
                editor = page.locator('[contenteditable="true"]').first
                await editor.wait_for(state="visible", timeout=10000)
            except Exception:
                editor = None
        if editor is None:
            raise Exception("Facebook: 文案框未出现")
        print("[Facebook] caption box ready")
        await editor.click(force=True)
        await page.keyboard.type(caption, delay=20)

        # Step 1 → Step 2: 点击 Next（等视频处理完变 enabled）
        ok = await _click_enabled_next(page, "step 1→2", max_wait_s=480)
        if not ok:
            raise Exception("Facebook: Step 1 Next 按钮未变为 enabled")
        await page.wait_for_timeout(5000)

        # Step 2: Edit reel 页 → 点击第二个 Next
        ok = await _click_enabled_next(page, "step 2→3", max_wait_s=120)
        if not ok:
            raise Exception("Facebook: Step 2 Next 按钮未变为 enabled")
        await page.wait_for_timeout(5000)

        # Step 3: 最终确认页 → 点击 Post
        post_btn = page.locator('div[role="dialog"] [role="button"][aria-label="Post"]').first
        try:
            await post_btn.wait_for(state="visible", timeout=30000)
            await post_btn.click(force=True)
            print("[Facebook] Post clicked")
        except Exception:
            # 兜底：尝试任意可见的 Post 按钮
            all_post = page.locator('[role="button"]').filter(has_text="Post")
            pc = await all_post.count()
            clicked_post = False
            for i in range(pc):
                btn = all_post.nth(i)
                try:
                    if await btn.is_visible(timeout=500) and await btn.is_enabled(timeout=500):
                        text = await btn.text_content(timeout=1000)
                        if text.strip() == "Post":
                            await btn.click(force=True)
                            clicked_post = True
                            print(f"[Facebook] Post clicked (fallback #{i})")
                            break
                except Exception:
                    pass
            if not clicked_post:
                raise Exception("Facebook: 最终确认页未找到 Post 按钮")

        await page.wait_for_timeout(6000)
        await save_cookies(context, cookie_path)
        return True
    except Exception as e:
        print("Facebook upload error:", e)
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
