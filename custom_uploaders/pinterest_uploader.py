# -*- coding: utf-8 -*-
"""Pinterest 发布器（官方 API v5，OAuth access token 认证，无需浏览器）。

凭据：cookies/pinterest_default.json = {"access_token": "...", "board_id": "..."}
获取 token：https://developers.pinterest.com → 创建 App → 生成 OAuth access token
board_id：目标画板 ID（画板 URL 里的数字，或 GET /v5/boards 查询）。

视频发布为四步官方流程（区别于图片，视频不支持单请求直传）：
  1. POST /v5/media          注册上传意图 → 拿 media_id + S3 upload_url + upload_parameters
  2. POST 到 S3 upload_url   把视频文件 + upload_parameters 作为表单字段上传
  3. GET  /v5/media/{id}     轮询直到 status 为 succeeded
  4. POST /v5/pins           用 media_id 建 Pin（media_source.source_type=video_id）

注意：Pinterest 新 App 默认 Trial 权限，POST /v5/pins 需 Standard access
审核通过后可用（免费 API，但 OAuth 审核与 LinkedIn 类似）。
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.request
import urllib.error

from .base import account_file, make_result

PLATFORM = "pinterest"
API_BASE = "https://api.pinterest.com/v5"


def _load_creds() -> dict | None:
    cf = account_file(PLATFORM)
    if not cf.exists():
        return None
    try:
        data = json.loads(cf.read_text(encoding="utf-8"))
        if data.get("access_token") and data.get("board_id"):
            return data
    except Exception:
        pass
    return None


def is_configured() -> bool:
    return bool(_load_creds())


def _json_request(url: str, payload: dict, token: str, method: str = "POST") -> dict:
    """发送 JSON 请求，返回解析后的响应体。"""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "OpenMatrixPublisher/0.1",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _s3_multipart(upload_url: str, upload_parameters: dict, file_path: str) -> None:
    """把文件 + upload_parameters 作为 multipart 表单上传到 Pinterest 的 S3 桶。

    注意：upload_parameters 必须随文件一起放在 body 里（不是 header）。
    """
    boundary = "----OMPBoundary" + os.urandom(8).hex()
    parts = []
    for name, value in (upload_parameters or {}).items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    fname = os.path.basename(file_path)
    ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\n"
        f"Content-Type: {ctype}\r\n\r\n".encode("utf-8")
    )
    with open(file_path, "rb") as f:
        parts.append(f.read())
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)

    req = urllib.request.Request(
        upload_url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        resp.read()  # S3 成功返回 204/200，内容忽略


def publish(video_path: str, title: str, tags: list[str] | None = None,
            desc: str | None = None) -> bool:
    """引擎入口：把视频真实发布为 Pinterest 视频 Pin（四步官方流程）。"""
    creds = _load_creds()
    if not creds:
        print("[Pinterest] 未配置 access_token/board_id，请先在控制台配置")
        return False

    token = creds["access_token"]
    board_id = creds["board_id"]
    description = (desc or title)[:500]

    if not video_path or not os.path.exists(video_path):
        print("[Pinterest] 需要本地视频文件（Pinterest 视频 Pin 走 S3 上传）")
        return False

    try:
        # 1. 注册上传意图
        media = _json_request(
            f"{API_BASE}/media", {"media_type": "video"}, token, "POST"
        )
        media_id = media.get("media_id")
        upload_url = media.get("upload_url")
        upload_params = media.get("upload_parameters") or {}
        if not media_id or not upload_url:
            print(f"[Pinterest] 注册上传失败: {media}")
            return False
        print(f"[Pinterest] 已注册上传 media_id={media_id}")

        # 2. 上传到 S3
        _s3_multipart(upload_url, upload_params, video_path)
        print("[Pinterest] 视频已上传 S3")

        # 3. 轮询确认上传完成
        status = ""
        for _ in range(20):
            detail = _json_request(f"{API_BASE}/media/{media_id}", None, token, "GET")
            status = (detail.get("status") or "").lower()
            if status in ("succeeded", "registered", "processed"):
                break
            if status in ("failed", "processing_failed"):
                print(f"[Pinterest] 媒体处理失败: {detail}")
                return False
            time.sleep(3)
        if status not in ("succeeded", "registered", "processed"):
            print(f"[Pinterest] 媒体处理超时，当前状态: {status}")
            return False
        print(f"[Pinterest] 媒体就绪 status={status}")

        # 4. 创建视频 Pin
        pin = _json_request(
            f"{API_BASE}/pins",
            {
                "title": title[:100],
                "description": description,
                "board_id": board_id,
                "media_source": {"source_type": "video_id", "media_id": media_id},
            },
            token,
            "POST",
        )
        pin_id = pin.get("id")
        print(f"[Pinterest] ✅ Pin 发布成功 (pin_id={pin_id})")
        return True
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        hint = ""
        if e.code == 401:
            hint = "（token 无效/过期，或 App 仍为 Trial 权限——POST /v5/pins 需 Standard access 审核）"
        elif e.code == 403:
            hint = "（Trial 权限通常只允许 GET，POST 需 Standard access 审核通过）"
        print(f"[Pinterest] HTTP {e.code}: {detail}{hint}")
        return False
    except Exception as e:
        print(f"[Pinterest] 发布异常: {e}")
        return False
