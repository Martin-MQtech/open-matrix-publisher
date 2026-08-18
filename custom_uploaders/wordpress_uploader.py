# -*- coding: utf-8 -*-
"""WordPress 发布器（免费官方 REST API，应用密码认证，无需浏览器）。

凭据：cookies/wordpress_default.json =
    {"site_url": "https://yourblog.com", "username": "...", "app_password": "..."}
获取：站点 → 用户 → 应用程序密码（WordPress 5.6+ 内置；wordpress.com 在账户设置里）。

能力（v2）：
1. 真实视频上传：POST {site}/wp-json/wp/v2/media（multipart/raw，Content-Disposition）
   → 入库媒体库，返回 source_url；
2. 文章嵌入：POST {site}/wp-json/wp/v2/posts，正文用 WordPress 原生
   [video src="..."] shortcode 嵌入视频，附描述与标签；
3. 视频上传失败时优雅降级为纯文字文章（不阻塞分发）。

免费、无配额（自有站或 wordpress.com 免费博客）。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
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


def _ascii_filename(path: str) -> str:
    """文件名 ASCII 化（Content-Disposition 对非 ASCII 文件名兼容差）。"""
    name = os.path.basename(path)
    stem, ext = os.path.splitext(name)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", stem)[:60] or "video"
    return f"{safe}{ext.lower() or '.mp4'}"


def _upload_video(site: str, auth: str, video_path: str) -> str | None:
    """上传视频到 WordPress 媒体库，返回 source_url（失败返回 None）。"""
    fname = _ascii_filename(video_path)
    ctype = mimetypes.guess_type(fname)[0] or "video/mp4"
    with open(video_path, "rb") as f:
        data = f.read()

    req = urllib.request.Request(
        f"{site}/wp-json/wp/v2/media",
        data=data,
        headers={
            "Content-Type": ctype,
            "Content-Disposition": f'attachment; filename="{fname}"',
            "Authorization": f"Basic {auth}",
            "User-Agent": "OpenMatrixPublisher/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    url = body.get("source_url") or ""
    if not url:
        print(f"[WordPress] 媒体上传响应无 source_url: {json.dumps(body)[:200]}")
        return None
    print(f"[WordPress] 🎬 视频已上传媒体库: {url}")
    return url


def publish(video_path: str, title: str, tags: list[str] | None = None,
            desc: str | None = None) -> bool:
    """引擎入口：上传视频到媒体库并发布嵌入视频的文章。"""
    creds = _load_creds()
    if not creds:
        print("[WordPress] 未配置站点/应用密码，请先在控制台配置")
        return False

    site = creds["site_url"].rstrip("/")
    auth = base64.b64encode(
        f"{creds['username']}:{creds['app_password']}".encode("utf-8")
    ).decode("utf-8")

    video_embedded = False
    if video_path and os.path.exists(video_path):
        try:
            src = _upload_video(site, auth, video_path)
            if src:
                video_embedded = True
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            print(f"[WordPress] 视频上传失败 HTTP {e.code}: {detail}（降级为纯文字文章）")
        except Exception as e:
            print(f"[WordPress] 视频上传异常: {e}（降级为纯文字文章）")

    # 正文：视频嵌入 + 描述 + 标签
    if video_embedded:
        content = f'[video src="{src}"]\n\n'
    else:
        content = ""
    content += desc or title
    if tags:
        content += "\n\n" + " ".join(f"#{t}" for t in tags[:8])

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
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        link = body.get("link") or ""
        tag = "🎬 视频文章" if video_embedded else "📄 文字文章（视频上传失败降级）"
        print(f"[WordPress] ✅ {tag}发布成功: {link}")
        return True
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200]
        print(f"[WordPress] 文章发布 HTTP {e.code}: {detail}")
        return False
    except Exception as e:
        print(f"[WordPress] 文章发布异常: {e}")
        return False
