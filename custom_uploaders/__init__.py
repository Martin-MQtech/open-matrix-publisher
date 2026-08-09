# -*- coding: utf-8 -*-
"""自定义多平台视频上传器（X / LinkedIn / Instagram / Facebook / TikTok）。

模式与 social-auto-upload 完全一致：patchright(chromium) + stealth 初始化 +
登录态存 cookies/{platform}_default.json（Playwright storage_state 格式）。
各平台 uploader 复用本模块的 launch / save_cookies / login_flow。
"""
import sys
from pathlib import Path

# 让本包能直接 import sau 的 conf / utils
import os
SAU_ROOT = Path(os.environ.get("SAU_ROOT", "/Users/martin/social-auto-upload"))
if str(SAU_ROOT) not in sys.path:
    sys.path.insert(0, str(SAU_ROOT))

from custom_uploaders.base import (  # noqa: E402
    account_file,
    launch,
    load_context,
    save_cookies,
    login_flow,
    SESSION_COOKIES,
)

__all__ = [
    "account_file",
    "launch",
    "load_context",
    "save_cookies",
    "login_flow",
    "SESSION_COOKIES",
]
