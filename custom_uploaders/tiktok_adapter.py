# -*- coding: utf-8 -*-
"""TikTok 适配器：复用 social-auto-upload 的 tk_uploader/main_chrome.py。

SAU 原登录用 page.pause()（调试器暂停，需手动点继续），这里改成统一无头检测存登录态。
- login(): 弹窗登录 → 自动存 cookies/tk_default.json（会话 cookie = sid_tt/sessionid_ss）。
- publish(): 直接调用 SAU 的 TiktokVideo（内部读取同一 cookie 路径）。
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, "/Users/martin/social-auto-upload")

from custom_uploaders.base import account_file, login_flow  # noqa: E402
from uploader.tk_uploader.main_chrome import TiktokVideo  # noqa: E402

PLATFORM = "tk"
LOGIN_URL = "https://www.tiktok.com/login?lang=en"


def login(headless: bool = False, timeout: int = 600) -> bool:
    return asyncio.run(login_flow(PLATFORM, LOGIN_URL, account_file(PLATFORM), headless, timeout))


def publish(video_path: str, title: str, tags: list[str] | None = None,
            schedule_hour: int = 16) -> bool:
    """调用 SAU 的 TiktokVideo 上传（当天 schedule_hour 点发布）。"""
    cookie_path = str(account_file(PLATFORM))
    # 默认排到下一个 schedule_hour 点（与 SAU 习惯一致；传 0 表示立即）
    publish_date = datetime.now() + timedelta(days=1)
    hour_val = int(schedule_hour) if str(schedule_hour).isdigit() else 16
    publish_date = publish_date.replace(hour=hour_val, minute=0, second=0, microsecond=0)
    app = TiktokVideo(
        title=title,
        file_path=video_path,
        tags=tags or [],
        publish_date=publish_date,
        account_file=cookie_path,
    )
    try:
        asyncio.run(app.main())
        return True
    except Exception as e:
        print("TikTok publish error:", e)
        return False
