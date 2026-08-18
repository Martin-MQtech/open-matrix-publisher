# -*- coding: utf-8 -*-
"""WordPress 发布器（免费官方 REST API，应用密码认证，无需浏览器）。

凭据：cookies/wordpress_default.json =
    {"site_url": "https://yourblog.com", "username": "...", "app_password": "..."}
获取：站点 → 用户 → 应用程序密码（WordPress 5.6+ 内置；wordpress.com 在账户设置里）。

API：POST {site}/wp-json/wp/v2/posts（Basic Auth）
- 免费、无配额（自有站或 wordpress.com 免费博客）。
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
import urllib.error

from .base import account_file, make_result

PLATFORM = "wordpress"


def _load_creds() -> dict | None:
    cf = account_file(PLATFORM)
    if not cf.exists():
        return None
    try:
        data = json.loads(cf.read_text(encoding="utf-8"))
        if data.get("site_url") and data.get("username") and data.get("app_password"):
            return data
    except Exception:
        pass
    return None


def is_configured() -> bool:
    return bool(_load_creds())


def publish(video_path: str, title: str, tags: list[str] | None = None,
            desc: str | None = None) -> bool:
    """引擎入口：把一条内容发布为 WordPress 文章。"""
    creds = _load_creds()
    if not creds:
        print("[WordPress] 未配置站点/应用密码，请先在控制台配置")
        return False

    site = creds["site_url"].rstrip("/")
    auth = base64.b64encode(
        f"{creds['username']}:{creds['app_password']}".encode("utf-8")
    ).decode("utf-8")

    # 正文：描述 + 标签
    content = desc or title
    if tags:
        content += "\n\n" + " ".join(f"#{t}" for t in tags[:8])
    if video_path and os.path.exists(video_path):
        content += f"\n\n<!-- 配套视频文件：{os.path.basename(video_path)}（本地分发，多域同步） -->"

    payload = {
        "title": title[:200],
        "content": content,
        "status": "publish",
    }
    req = urllib.request.Request(
        f"{site}/wp-json/wp/v2/posts",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
            "User-Agent": "OpenMatrixPublisher/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        link = body.get("link") or ""
        print(f"[WordPress] ✅ 文章发布成功: {link}")
        return True
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200]
        print(f"[WordPress] HTTP {e.code}: {detail}")
        return False
    except Exception as e:
        print(f"[WordPress] 发布异常: {e}")
        return False
