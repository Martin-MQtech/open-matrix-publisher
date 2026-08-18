# -*- coding: utf-8 -*-
"""Dev.to 文章发布器（免费官方 API，API key 认证，无需浏览器）。

凭据：cookies/devto_default.json = {"api_key": "..."}
获取 key：https://dev.to/settings/account → API Keys → 创建。

API：POST https://dev.to/api/articles
- Header: api-key
- 免费、无配额限制（公开 API），合规（官方通道，无封号风险）。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

from .base import account_file, make_result

PLATFORM = "devto"
API_URL = "https://dev.to/api/articles"


def _load_api_key() -> str | None:
    cf = account_file(PLATFORM)
    if not cf.exists():
        return None
    try:
        data = json.loads(cf.read_text(encoding="utf-8"))
        key = data.get("api_key") or data.get("api-key")
        return key if key else None
    except Exception:
        return None


def is_configured() -> bool:
    return bool(_load_api_key())


def publish(video_path: str, title: str, tags: list[str] | None = None,
            desc: str | None = None) -> bool:
    """引擎入口：把一条内容（标题/描述/标签）发布为 Dev.to 文章。"""
    api_key = _load_api_key()
    if not api_key:
        print("[Dev.to] 未配置 API key，请先在控制台配置")
        return False

    body_md = desc or title
    if tags:
        body_md += "\n\n" + " ".join(f"#{t}" for t in tags[:4])
    # 附带视频文件信息（Dev.to 不支持视频上传，仅作记录）
    if video_path and os.path.exists(video_path):
        body_md += f"\n\n> 📎 配套视频文件：`{os.path.basename(video_path)}`（本地分发，多域同步）"

    payload = {
        "article": {
            "title": title[:200],
            "published": True,
            "body_markdown": body_md,
            "tags": (tags or [])[:4],
        }
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
            "User-Agent": "OpenMatrixPublisher/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        url = body.get("url") or body.get("canonical_url") or ""
        print(f"[Dev.to] ✅ 文章发布成功: {url}")
        return True
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200]
        print(f"[Dev.to] HTTP {e.code}: {detail}")
        return False
    except Exception as e:
        print(f"[Dev.to] 发布异常: {e}")
        return False
