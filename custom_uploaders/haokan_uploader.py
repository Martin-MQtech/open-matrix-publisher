# -*- coding: utf-8 -*-
"""好看视频 (Haokan Video, 百度旗下) 视频自动上传器

发布入口：https://haokan.baidu.com/ 创作中心上传页
登录入口：https://haokan.baidu.com/（百度账号体系，右上角登录）
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

try:
    from patchright.async_api import async_playwright
except ImportError:
    from playwright.async_api import async_playwright

from .base import (
    account_file,
    is_logged_in,
    make_result,
)

PLATFORM = "haokan"
UPLOAD_URL = "https://haokan.baidu.com/author/home"
LOGIN_URL = "https://haokan.baidu.com/"

def publish(video_path: str, title: str, tags: list[str] | None = None,
            desc: str | None = None) -> bool:
    """引擎入口：返回 bool（True=发布成功）。"""
    uploader = HaokanUploader()
    res = asyncio.run(uploader.upload(video_path, title, desc or "", tags))
    return bool(res.get("success"))


class HaokanUploader:
    def __init__(self, account_name: str = "default", headless: bool = True):
        self.account_name = account_name
        self.headless = headless
        self.cookie_file = account_file(PLATFORM, account_name)

    async def upload(self, video_file: str, title: str, desc: str = "", tags: list[str] | None = None) -> dict:
        tags = tags or []
        v_path = Path(video_file).resolve()
        if not v_path.exists():
            return make_result(False, "error", f"视频文件不存在: {v_path}", platform=PLATFORM)

        if not is_logged_in(PLATFORM, self.account_name):
            return make_result(False, "not_logged_in", "好看视频未登录，请先扫码登录", platform=PLATFORM)

        print(f"[Haokan] 开始自动化分发: {v_path.name} | 标题: {title}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = await browser.new_context(
                storage_state=str(self.cookie_file),
                viewport={"width": 1440, "height": 900}
            )
            page = await context.new_page()

            try:
                # 创作中心首页 → 找「上传/发布」入口（页面结构可能变化，多选择器兜底）
                await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(4)

                # 若被重定向到登录页，说明 Cookie 失效
                if "login" in page.url.lower() or "passport" in page.url.lower():
                    await browser.close()
                    return make_result(False, "not_logged_in", "好看视频登录已失效，请重新扫码", platform=PLATFORM)

                # 尝试点击「发布视频/上传」入口进入编辑器
                for sel in ["text=发布视频", "text=上传视频", "text=发布", "a:has-text('上传')"]:
                    try:
                        btn = await page.query_selector(sel)
                        if btn:
                            await btn.click()
                            await asyncio.sleep(3)
                            break
                    except Exception:
                        continue

                # 上传文件
                file_input = await page.wait_for_selector("input[type=file]", timeout=20000)
                if not file_input:
                    await browser.close()
                    return make_result(False, "selector_error", "未找到好看视频上传入口", platform=PLATFORM)

                await file_input.set_input_files(str(v_path))
                print("[Haokan] 视频文件已注入，等待上传解析...")
                await asyncio.sleep(8)

                # 填充标题
                title_input = await page.wait_for_selector(
                    "input[placeholder*='标题'], textarea[placeholder*='标题'], input[placeholder*='标题']",
                    timeout=15000)
                if title_input:
                    await title_input.fill(title[:30])

                # 填充描述
                desc_input = await page.query_selector(
                    "textarea[placeholder*='简介'], textarea[placeholder*='描述'], div[contenteditable='true']")
                if desc_input and desc:
                    try:
                        await desc_input.fill(desc)
                    except Exception:
                        pass

                # 等待并点击发布按钮
                publish_btn = await page.wait_for_selector(
                    "button:has-text('发布'), button:has-text('确认发布'), button:has-text('确定')",
                    timeout=30000)
                if publish_btn:
                    await publish_btn.click()
                    await asyncio.sleep(5)
                    print("[Haokan] 点击发布完成！")

                await browser.close()
                return make_result(True, "published", f"好看视频发布成功: {title}", platform=PLATFORM)
            except Exception as e:
                await browser.close()
                return make_result(False, "upload_failed", f"好看视频发布异常: {e}", platform=PLATFORM)
