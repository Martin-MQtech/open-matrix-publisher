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
    """Instagram 上传：headless 下 IG 反自动化较严格，这里做一次真实尝试而非直接放弃。
    流程：首页 → 点击「新建」→ 选择文件 → 下一步 → 填写文案 → 分享。
    若任一关键步骤被拦截/未渲染，返回 False 并打印诊断；成功跳转到帖子页才算发布成功。
    """
    cookie_path = account_file(PLATFORM)
    pw, browser = await launch(headless=headless, proxy=YT_PROXY)
    context = await load_context(browser, cookie_path)
    page = await context.new_page()
    try:
        # 1. 进入首页并点击左侧「新建」按钮（aria-label 可能随语言变化）
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        await _dismiss_overlays(page)
        await page.wait_for_timeout(3000)

        new_post_clicked = await _click_visible(page, [
            '[aria-label="新建"]', '[aria-label="New post"]', '[aria-label="新建帖子"]',
            'a[href="/create/"]', 'svg[aria-label="新建"]',
        ])
        if not new_post_clicked:
            print("[Instagram] 未能点击「新建」按钮，可能未登录或页面改版")
            return False

        # 2. 等待文件选择框并写入视频
        file_input = page.locator('input[type="file"]').first
        try:
            await file_input.wait_for(state="attached", timeout=15000)
        except Exception:
            print("[Instagram] 未出现文件选择框（可能被反自动化拦截）")
            return False
        await file_input.set_input_files(video_path)
        print("[Instagram] 已选择视频文件，等待上传处理...")
        await page.wait_for_timeout(8000)

        # 3. 点击「下一步 / Next」（可能出现两次：裁剪、封面）
        for _ in range(2):
            clicked = await _click_visible(page, [
                'button:has-text("下一步")', 'button:has-text("Next")',
                '[role="button"]:has-text("下一步")', '[role="button"]:has-text("Next")',
            ])
            if clicked:
                await page.wait_for_timeout(3000)

        # 4. 填写文案（标题 + 标签）
        caption = f"{title or ''}"
        if desc:
            caption = f"{caption}\n{desc}"
        if tags:
            caption += "\n" + " ".join(f"#{t}" for t in tags[:10])
        try:
            editor = page.locator('textarea, div[contenteditable="true"]').first
            if await editor.count():
                await editor.click()
                await editor.fill(caption)
        except Exception:
            pass

        # 5. 点击「分享 / Share」
        shared = await _click_visible(page, [
            'button:has-text("分享")', 'button:has-text("Share")',
            '[role="button"]:has-text("分享")', '[role="button"]:has-text("Share")',
        ])
        if not shared:
            print("[Instagram] 未找到「分享」按钮，可能未到最终发布页")
            return False

        # 6. 验证：URL 跳转到 /p/ 或页面出现成功提示
        try:
            await page.wait_for_url("**/p/**", timeout=20000)
            print("[Instagram] ✅ 视频已发布（跳转到帖子页）")
            return True
        except Exception:
            page_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
            if "已发布" in page_text or "Your post" in page_text or "shared" in page_text.lower():
                print("[Instagram] ✅ 视频已发布（检测到成功提示）")
                return True
            print("[Instagram] 分享后未确认成功（IG 反自动化可能拦截）")
            return False
    except Exception as e:
        print(f"[Instagram] upload error: {repr(e)[:200]}")
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