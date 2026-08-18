# -*- coding: utf-8 -*-
"""TikTok 自定义上传器（替代 SAU TiktokVideo 的 load 超时坑）。

SAU 的 TiktokVideo 在 change_language() 里 goto 首页等 `load` 事件——
TikTok 首页有长连接，`load` 永不触发，30 秒必超时。这里改为：
直接导航 tiktokstudio/upload（domcontentloaded）→ 等 SPA 渲染 →
选文件 → 填标题 → 等 Post 可用 → 发布。

注意：TikTok 2025+ 的 tiktokstudio 页面已无 iframe[data-tt] 和
upload-container 容器，上传按钮直接在主文档内（实测 20s 渲染）。

登录态复用 cookies/tiktok_default.json（可从真实 Chrome 提取）。
"""
from __future__ import annotations

import asyncio

from custom_uploaders.base import (
    account_file,
    launch,
    load_context,
    save_cookies,
)

PLATFORM = "tiktok"
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"


async def upload(video_path: str, title: str, tags: list[str] | None = None,
                 desc: str | None = None, headless: bool = True,
                 timeout: int = 240) -> bool:
    cookie_path = account_file(PLATFORM)
    pw, browser = await launch(headless=headless)
    context = await load_context(browser, cookie_path)
    page = await context.new_page()
    try:
        # 直接进上传页，不等 load（domcontentloaded 即可）
        await page.goto(UPLOAD_URL, wait_until="domcontentloaded")
        # 上传区是 SPA 懒加载，等 20s+ 渲染（TikTok 2025+ 页面已无 iframe/upload-container）
        await page.wait_for_timeout(20000)

        # 等 Select video 按钮可见（主文档内）
        upload_btn = page.locator('button:has-text("Select video"):visible').first
        try:
            await upload_btn.wait_for(state="visible", timeout=60000)
        except Exception:
            print("[TikTok] FAIL: Select video button not visible")
            print("[TikTok] current URL:", page.url)
            return False

        # 选文件（原生 file chooser）
        async with page.expect_file_chooser(timeout=15000) as fc_info:
            await upload_btn.click()
        fc = await fc_info.value
        await fc.set_files(video_path)
        print("[TikTok] file set")

        # 等上传完成（Post 按钮可用，主文档内）
        # 注意：button:has-text("Post") 会误匹配侧边栏 "Posts" 导航，
        # 必须限定在 button-group 内（发布按钮的父容器）。
        post_btn = page.locator('div.button-group button.Button__root--type-primary').first
        try:
            await post_btn.wait_for(state="visible", timeout=120000)
            # 轮询等 disabled 消失（转码结束）
            for _ in range(int(timeout * 10)):
                if await post_btn.is_enabled():
                    break
                await page.wait_for_timeout(500)
        except Exception as e:
            print("[TikTok] Post button issue:", repr(e)[:120])

        # 填标题（DraftEditor，主文档内；等渲染完再点，失败不阻塞发布）
        try:
            editor = page.locator('div.public-DraftEditor-content').first
            await editor.wait_for(state="visible", timeout=30000)
            await editor.click(force=True)
            await page.wait_for_timeout(500)
            await page.keyboard.press("Meta+A")
            await page.keyboard.press("Delete")
            await page.keyboard.insert_text(title)
            await page.wait_for_timeout(500)
            # 标签
            for tag in (tags or []):
                await page.keyboard.press("End")
                await page.keyboard.insert_text(f"#{tag} ")
                await page.keyboard.press("Space")
                await page.wait_for_timeout(300)
            print("[TikTok] title+tags set")
        except Exception as e:
            print("[TikTok] title set issue (non-blocking):", repr(e)[:120])

        # 移除可能的引导浮层
        try:
            await page.evaluate("""() => {
                const o = document.querySelector('.react-joyride__overlay, #react-joyride-portal');
                if (o) o.remove();
            }""")
        except Exception:
            pass
        # 移除 cookie 横幅（TIKTOK-COOKIE-BANNER 会遮挡 Post 按钮，点击全被拦截）
        try:
            banner = page.locator('tiktok-cookie-banner')
            if await banner.count():
                decline = banner.locator('button:has-text("Decline optional cookies"), button:has-text("Decline")').first
                if await decline.count():
                    await decline.click(timeout=5000)
                    print("[TikTok] cookie banner dismissed")
                    await page.wait_for_timeout(1000)
        except Exception as e:
            print("[TikTok] cookie banner issue (non-blocking):", repr(e)[:100])
        # 发布按钮初始在视口外（y≈1360），滚动到可见再点
        try:
            await post_btn.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
            await post_btn.click()
            print("[TikTok] Post clicked")
        except Exception as e:
            print("[TikTok] Post click issue:", repr(e)[:120])

        # TikTok 有二次确认弹窗：等 dialog 出现后点 "Post now"
        try:
            confirm = page.locator('[role=dialog] button:has-text("Post now"), button:has-text("Post now"):visible').first
            await confirm.wait_for(state="visible", timeout=15000)
            await confirm.click()
            print("[TikTok] confirmed Post now")
        except Exception as e:
            print("[TikTok] confirm dialog issue (non-blocking):", repr(e)[:100])

        # 等跳转到 content 页 = 发布成功
        try:
            await page.wait_for_url("**/tiktokstudio/content*", timeout=45000)
            print("[TikTok] published OK")
            await save_cookies(context, cookie_path)
            return True
        except Exception:
            print("[TikTok] WARN: did not navigate to content page; checking URL")
            print("[TikTok] current URL:", page.url)
            if "content" in page.url:
                await save_cookies(context, cookie_path)
                return True
            return False
    except Exception as e:
        print("TikTok upload error:", repr(e))
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