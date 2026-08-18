# -*- coding: utf-8 -*-
"""Telegram 发布器（免费官方 Bot API，bot token 认证，无需浏览器）。

凭据：cookies/telegram_default.json = {"bot_token": "...", "chat_id": "..."}
获取 token：https://t.me/BotFather → /newbot → 复制 token
chat_id：把 bot 拉进目标群/频道后，@userinfobot 或 getUpdates 查询。

API：POST https://api.telegram.org/bot<TOKEN>/sendVideo
- 支持真实视频文件上传（multipart/form-data），非仅文章。
- 免费、无配额限制，官方通道合规。
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import urllib.request
import urllib.error

from .base import account_file, make_result

PLATFORM = "telegram"
API_BASE = "https://api.telegram.org"


def _load_creds() -> dict | None:
    cf = account_file(PLATFORM)
    if not cf.exists():
        return None
    try:
        data = json.loads(cf.read_text(encoding="utf-8"))
        if data.get("bot_token") and data.get("chat_id"):
            return data
    except Exception:
        pass
    return None


def is_configured() -> bool:
    return bool(_load_creds())


def _multipart(fields: list[tuple[str, str]], file_field: str, file_path: str) -> tuple[bytes, str]:
    """构造 multipart/form-data 请求体（urllib 手写，避免额外依赖）。"""
    boundary = "----OMPBoundary" + os.urandom(8).hex()
    parts = []
    for name, value in fields:
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    fname = os.path.basename(file_path)
    ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{fname}\"\r\n"
        f"Content-Type: {ctype}\r\n\r\n".encode("utf-8")
    )
    with open(file_path, "rb") as f:
        parts.append(f.read())
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def publish(video_path: str, title: str, tags: list[str] | None = None,
            desc: str | None = None) -> bool:
    """引擎入口：把视频真实上传到 Telegram 群/频道（附标题/描述）。"""
    creds = _load_creds()
    if not creds:
        print("[Telegram] 未配置 bot_token/chat_id，请先在控制台配置")
        return False

    token = creds["bot_token"]
    chat_id = creds["chat_id"]

    caption = (desc or title)[:1024]
    if tags:
        suffix = " " + " ".join(f"#{t}" for t in tags[:6])
        room = 1024 - len(caption)
        caption = (caption + suffix)[:1024]

    try:
        if video_path and os.path.exists(video_path):
            fields = [("chat_id", chat_id), ("caption", caption)]
            body, ctype = _multipart(fields, "video", video_path)
            url = f"{API_BASE}/bot{token}/sendVideo"
        else:
            # 无视频文件时退化为纯文本消息
            fields = [("chat_id", chat_id), ("text", caption)]
            body, ctype = _multipart(fields, "document", video_path or "")
            url = f"{API_BASE}/bot{token}/sendMessage"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("ok"):
            mid = (result.get("result") or {}).get("message_id")
            print(f"[Telegram] ✅ 发布成功 (message_id={mid})")
            return True
        print(f"[Telegram] API 返回失败: {result.get('description', result)}")
        return False
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200]
        print(f"[Telegram] HTTP {e.code}: {detail}")
        return False
    except Exception as e:
        print(f"[Telegram] 发布异常: {e}")
        return False
