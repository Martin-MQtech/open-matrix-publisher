# -*- coding: utf-8 -*-
"""平台登录态判定 —— 全项目唯一权威来源（Single Source of Truth）。

背景：登录成功判定此前散落三处且互不同步——
  1. interactive_login.py（扫码窗口轮询判定，决定关窗时机）
  2. real_uploader_engine.py check_profile_logged_in（主界面 /api/status 判定）
  3. custom_uploaders/base.py SESSION_COOKIES（自定义上传器判定）
平台一改版（快手 web_st→passToken、小红书 web_session→galaxy_creator_session_id）
三处各自过时，导致"扫码成功关窗了但主界面仍显示需扫码"、"扫完永不关窗"等连环 bug。

规则：
  - 每个平台一组「会话信号 cookie」，**任一存在且值长度 >= MIN_TOKEN_LEN 即视为已登录**。
  - 多信号是刻意的：平台改版时旧信号消失、新信号出现，任一命中即可，避免单点过时。
  - API-key 平台（devto / wordpress / telegram / pinterest）不走本模块，
    由各自凭证文件的字段判定。

公共 API：
  check_cookie_map(platform_id, cookie_map) -> bool
  check_cookies(platform_id, cookies: list[dict]) -> bool
  check_file(platform_id, cookie_file_path) -> tuple[bool, str]   # 含过期过滤
"""
from __future__ import annotations

import json
import os
import time

MIN_TOKEN_LEN = 6

# 每平台的会话信号 cookie（并集口径，任一命中即登录）
PLATFORM_SESSION_COOKIES: dict[str, list[str]] = {
    # ── 国内 ──
    "tencent":     ["sessionid", "pass_ticket", "wxuin", "session_key"],
    "douyin":      ["sessionid_ss", "sessionid"],
    "bilibili":    ["SESSDATA"],
    "kuaishou":    ["kuaishou.server.web_st", "passToken", "kuaishou.server.web_ph"],
    "xiaohongshu": ["web_session", "galaxy_creator_session_id",
                    "galaxy.creator.beaker.session.id", "access-token-creator.xiaohongshu.com"],
    "weibo":       ["SUB"],
    "toutiao":     ["LOGIN_A", "sessionid_ss", "sessionid"],
    "zhihu":       ["z_c0"],
    "baijiahao":   ["BDUSS", "STOKEN"],
    "haokan":      ["BDUSS", "STOKEN", "BDUSS_BFESS"],
    # 百度系（好看视频 / 百家号）登录会话靠 BDUSS；BAIDUID 是匿名设备标识不可用。
    # 在好看视频首页登录百度账号并不会发 BDUSS——必须点击「创作者中心」
    # 进入创作后台才会真正写入 BDUSS/BDUSS_BFESS。
    # ── 国际 ──
    "youtube":     ["SID", "SAPISID", "__Secure-3PAPISID", "__Secure-1PAPISID"],
    "tiktok":      ["sessionid_ss", "sid_tt", "sessionid"],
    "tk":          ["sessionid_ss", "sid_tt", "sessionid"],
    "x":           ["auth_token"],
    "twitter":     ["auth_token"],
    "facebook":    ["c_user", "xs"],
    "instagram":   ["sessionid"],
    "linkedin":    ["li_at"],
    # API-key 平台不在字典中：devto / wordpress / telegram / pinterest
}

API_KEY_PLATFORMS = ("devto", "wordpress", "telegram", "pinterest")


def session_signals(platform_id: str) -> list[str]:
    """返回该平台的会话信号 cookie 列表（API-key 平台返回空）。"""
    return PLATFORM_SESSION_COOKIES.get(platform_id, [])


def check_cookie_map(platform_id: str, cookie_map: dict) -> bool:
    """从 name->value 映射判定登录态。任一信号命中即 True。"""
    signals = session_signals(platform_id)
    if not signals:
        return False
    for name in signals:
        v = cookie_map.get(name)
        if v is not None and len(str(v)) >= MIN_TOKEN_LEN:
            return True
    return False


def check_cookies(platform_id: str, cookies: list[dict]) -> bool:
    """从 Playwright cookie 列表判定登录态。"""
    cookie_map = {c.get("name"): c.get("value", "") for c in cookies if c.get("name")}
    return check_cookie_map(platform_id, cookie_map)


def check_file(platform_id: str, cookie_file_path: str) -> tuple[bool, str]:
    """从 storage_state JSON 文件判定登录态（过滤已过期 cookie）。

    返回 (logged_in, message)。文件不存在/损坏 → (False, 提示)。
    """
    if platform_id in API_KEY_PLATFORMS:
        return False, "API-key 平台不走 cookie 判定"

    if not os.path.exists(cookie_file_path):
        return False, "🔑 需扫码登录"

    try:
        with open(cookie_file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
    except Exception:
        return False, "🔑 凭证读取失败"

    cookies = content.get("cookies", []) if isinstance(content, dict) else []
    if not cookies:
        return False, "🔑 需扫码登录"

    now = time.time()
    # expires <= 0 视为 session cookie（视为有效）；否则要求未过期
    valid = [c for c in cookies if c.get("expires", 0) <= 0 or c.get("expires", 0) > now]
    cookie_map = {c.get("name"): c.get("value", "") for c in valid if c.get("name")}

    if check_cookie_map(platform_id, cookie_map):
        return True, "✅ 已登录"
    if check_cookie_map(platform_id, {c.get("name"): c.get("value", "") for c in cookies if c.get("name")}):
        # 信号 cookie 存在但已过期
        return False, "🔑 Cookie 已失效 (需扫码)"
    return False, "🔑 Cookie 已失效 (需扫码)"
