# -*- coding: utf-8 -*-
"""TikTok 适配器：复用 social-auto-upload 的 tk_uploader/main_chrome.py。

SAU 原登录用 page.pause()（调试器暂停，需手动点继续），这里改成统一无头检测存登录态。
- login(): 弹窗登录 → 自动存 cookies/tk_default.json（会话 cookie = sid_tt/sessionid_ss）。
- publish(): 直接调用 SAU 的 TiktokVideo（内部读取同一 cookie 路径）。
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser(os.environ.get("SAU_ROOT", "~/social-auto-upload")))

from custom_uploaders.base import account_file, login_flow  # noqa: E402
from uploader.tk_uploader.main_chrome import TiktokVideo  # noqa: E402

PLATFORM = "tk"
LOGIN_URL = "https://www.tiktok.com/login?lang=en"


def login(headless: bool = False, timeout: int = 600) -> bool:
    return asyncio.run(login_flow(PLATFORM, LOGIN_URL, account_file(PLATFORM), headless, timeout))


def publish(video_path: str, title: str, tags: list[str] | None = None,
            desc=None) -> bool:
    """调用 SAU 的 TiktokVideo 上传并立即发布（publish_date=0 表示不排期、直接发）。

    注意：引擎以 publish(video, title, tags, desc) 四参调用，desc 在 TikTok 无对应字段，
    此处接收并忽略，保证参数顺序一致、不被误当作排期小时数。
    """
    cookie_path = str(account_file(PLATFORM))
    app = TiktokVideo(
        title=title,
        file_path=video_path,
        tags=tags or [],
        publish_date=0,  # 0 = 立即发布，不排期
        account_file=cookie_path,
    )
    try:
        asyncio.run(app.main())
        return True
    except Exception as e:
        print("TikTok publish error:", e)
        return False
