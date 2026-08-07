# -*- coding: utf-8 -*-
"""LinkedIn 视频上传器。

登录：弹出窗口登录，自动存 cookies/linkedin_default.json（会话 cookie = li_at）。
上传：打开发帖页 → 附加视频 → 填文案 → 发布。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from custom_uploaders.base import (
    account_file, launch, load_context, save_cookies, login_flow,
)
from conf import YT_PROXY


async def _wait_publish_enabled(page, btn, timeout: int = 240000):
    try:
        await btn.wait_for(state="enabled", timeout=timeout)
    except Exception:
        pass

PLATFORM = "linkedin"
LOGIN_URL = "https://www.linkedin.com/login"
# LinkedIn 改版后 /post/new/ 变成「文章编辑器」，没有视频按钮。
# 正确入口是 feed 页发帖框旁的「Video」按钮。
COMPOSE_URL = "https://www.linkedin.com/feed/"


def login(headless: bool = False, timeout: int = 600) -> bool:
    return asyncio.run(login_flow(PLATFORM, LOGIN_URL, account_file(PLATFORM), headless, timeout, proxy=YT_PROXY))


async def upload(video_path: str, title: str, tags: list[str] | None = None,
                desc: str | None = None, headless: bool = True, timeout: int = 180) -> bool:
    cookie_path = account_file(PLATFORM)
    pw, browser = await launch(headless=headless, proxy=YT_PROXY)
    context = await load_context(browser, cookie_path)
    page = await context.new_page()
    try:
        await page.goto(COMPOSE_URL, wait_until="domcontentloaded")
        # feed 页发帖框旁的「Video」图标（英文界面 name=Video；中文 name=视频）。
        # 注意：不能用 button:has-text("Video") —— 它会误匹配整个发帖框大容器
        # （bbox 524x300，文本含 "Video Photo Write article"），点了只是聚焦发帖框。
        # 必须用精确 accessible name 匹配小图标。点 Video 会触发浏览器原生文件
        # 选择对话框，headless 下用 expect_file_chooser 捕获后 set_files。
        video_btn = page.get_by_role("button", name="Video", exact=True).or_(
            page.get_by_role("button", name="视频", exact=True)
        ).first
        async with page.expect_file_chooser(timeout=20000) as fc_info:
            await video_btn.click()
        fc = await fc_info.value
        await fc.set_files(str(video_path))
        # LinkedIn 视频上传后先弹出「Editor」预览模态框（视频+缩略图），
        # 需点击「Next」进入文案编辑步骤，才出现 [contenteditable] 文本框。
        await page.wait_for_timeout(5000)
        # 点 Next 进入文案编辑页
        next_btn = page.get_by_role("button", name="Next", exact=True).or_(
            page.get_by_role("button", name="下一步", exact=True)
        ).first
        await next_btn.click()
        await page.wait_for_timeout(3000)

        # 文案编辑器（此时已在 compose 步骤）
        editor = page.locator('[contenteditable="true"], div[role="textbox"]').first
        caption = (desc or title) + ("\n" + " ".join(f"#{t}" for t in (tags or [])) if tags else "")
        await editor.click()
        await page.keyboard.type(caption, delay=20)

        # 关键修复：LinkedIn 视频转码完成前 Post 按钮 disabled，必须等 enabled
        post_btn = page.locator('button:has-text("发布"), button:has-text("Post")').first
        print("[LinkedIn] waiting for video processing (Post enabled)...")
        await _wait_publish_enabled(page, post_btn, timeout=240000)
        await post_btn.click()
        await page.wait_for_timeout(6000)
        await save_cookies(context, cookie_path)
        return True
    except Exception as e:
        print("LinkedIn upload error:", e)
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
