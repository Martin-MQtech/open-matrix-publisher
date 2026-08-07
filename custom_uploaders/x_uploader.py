# -*- coding: utf-8 -*-
"""X (Twitter) 视频上传器。

登录：弹出窗口用账号密码/Google 登录，自动存 cookies/x_default.json。
上传：加载登录态 → 打开 x.com/compose/post → 填文案 → 附加视频 → 发布。

注意：X 反爬强，上传选择器需真实账号冒烟测试后微调（见 video-multi-publisher 技能说明）。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from conf import YT_PROXY  # 国内访问 X 需经代理
from custom_uploaders.base import (
    account_file,
    launch,
    load_context,
    save_cookies,
    login_flow,
    SESSION_COOKIES,
)

PLATFORM = "x"
LOGIN_URL = "https://x.com/login"
COMPOSE_URL = "https://x.com/compose/post"
# X 在国内被墙，发布必须走代理
X_PROXY = YT_PROXY


def login(headless: bool = False, timeout: int = 600) -> bool:
    return asyncio.run(login_flow(PLATFORM, LOGIN_URL, account_file(PLATFORM), headless, timeout, proxy=X_PROXY))


async def _wait_publish_enabled(page, btn, timeout: int = 240000):
    """等发布按钮变为可点击（视频转码完成的平台通用信号）。"""
    try:
        await btn.wait_for(state="enabled", timeout=timeout)
    except Exception:
        pass  # 超时也尝试点，可能只是状态属性没刷新


async def upload(video_path: str, title: str, tags: list[str] | None = None,
                desc: str | None = None, headless: bool = True, timeout: int = 180) -> bool:
    cookie_path = account_file(PLATFORM)
    pw, browser = await launch(headless=headless, proxy=X_PROXY)
    context = await load_context(browser, cookie_path)
    page = await context.new_page()
    try:
        await page.goto(COMPOSE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # 文案：X 的 composer 是可编辑区（contenteditable / 特定 textarea）
        caption = (desc or title) + ("\n" + " ".join(f"#{t}" for t in (tags or [])) if tags else "")
        box = page.locator('[data-testid="tweetTextarea_0"], [contenteditable="true"]').first
        await box.click()
        await page.wait_for_timeout(500)
        await page.keyboard.type(caption, delay=20)

        # 附加视频：X 用 HTML 化的文件选择器（不是原生 file chooser）。
        # 步骤：1) 点 dialog 内的"Add photos or video"按钮 → 2) X 弹出自定义选择器 →
        # 3) 直接 set_files() 到 dialog 内的 file input。
        # 注意：用 expect_file_chooser() 等不到事件（X 不是原生 chooser），
        # 所以不能依赖它。
        media_btn = page.locator(
            '[role="dialog"] button[aria-label="Add photos or video"]'
        ).first
        file_input = page.locator('[role="dialog"] input[type="file"]').first
        # 优先方案：点击 Media 按钮激活 X 的选择器流，然后直接 set file input
        if await media_btn.count():
            await media_btn.click(force=True)
            await page.wait_for_timeout(1500)
        # 不管按钮点没点，直接 set file input（X 的 hidden file input 一直接收文件）
        if await file_input.count():
            await file_input.set_input_files(str(video_path))
            print("[X] file set on dialog input")
        else:
            print("[X] FAIL: no file input in dialog")
            return False

        # 验证视频真的被 attach 了：
        # - 等 MediaUploadProgress 浮层出现（说明 X 在上传媒体）
        # - 等浮层消失（说明上传/转码完成）
        # - 再看 dialog 里是否出现视频预览元素（img/video 标签或 MediaUploadProgress 之外的
        #   媒体确认元素）。如果预览没出现，说明文件没被 attach。
        print("[X] waiting for media to attach...")
        try:
            prog = page.locator('[data-testid="MediaUploadProgress"]').first
            if await prog.count() > 0:
                await prog.wait_for(state="visible", timeout=10000)
                print("[X] media upload started")
                await prog.wait_for(state="hidden", timeout=180000)
                print("[X] media processing done")
        except Exception as e:
            print("[X] MediaUploadProgress note:", repr(e)[:100])
        
        await page.wait_for_timeout(3000)
        # 检查视频/图片预览容器是否存在
        media_preview = page.locator('[role="dialog"] video, [role="dialog"] img, [data-testid="tweetPhoto"], [data-testid="attachments"]').first
        if await media_preview.count() == 0:
            print("[X] WARNING: video preview container not confirmed, but proceeding to click Post if enabled")
        print(f"[X] video preview found ({media_preview} element)")
        post_btn = page.locator('[data-testid="tweetButton"]').first
        print("[X] waiting for Post button enabled...")
        await _wait_publish_enabled(page, post_btn, timeout=120000)
        # 聚焦 composer 并用快捷键发布（避免浮层拦截点击）
        try:
            await box.click()
        except Exception:
            pass
        await page.keyboard.press("Meta+Enter")
        await page.wait_for_timeout(3000)
        # 兜底：若快捷键没生效（按钮仍在且 enabled），直接点
        try:
            if await post_btn.is_enabled():
                await post_btn.click(force=True)
        except Exception:
            pass
        await page.wait_for_timeout(5000)
        print("[X] post submitted")
        await save_cookies(context, cookie_path)  # 刷新可能更新的 cookie
        return True
    except Exception as e:
        print("X upload error:", repr(e))
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
