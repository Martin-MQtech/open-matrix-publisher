#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从本机真实 Chrome 提取已登录平台的 Cookie → 写入引擎 storage_state。

用法：
    python3 scripts/extract_chrome_cookies.py [platform_id ...]
    # 不带参数 = 提取全部已映射平台

与「弹新窗口重新登录」不同：直接读用户已登录 Chrome 的会话，避免触发
谷歌/领英等平台的真人验证。写入 cookies/{platform}_default.json（本地 + SAU
两处），供 custom_uploaders 的 account_file() 读取。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, os.path.expanduser("~/social-auto-upload"))

import browser_cookie3  # noqa: E402

from omp_paths import data_dir  # noqa: E402
from custom_uploaders.base import SESSION_COOKIES  # noqa: E402

# 平台 → 需提取的域名（浏览器 cookie 的 domain 后缀匹配）
PLATFORM_DOMAINS = {
    "linkedin":   ["linkedin.com"],
    "tiktok":     ["tiktok.com"],
    "x":          ["x.com", "twitter.com"],
    "instagram":  ["instagram.com"],
    "facebook":   ["facebook.com"],
    "youtube":    ["youtube.com"],
    "weibo":      ["weibo.com", "weibo.cn"],
    "zhihu":      ["zhihu.com"],
    "toutiao":    ["toutiao.com", "ixigua.com"],
    "xiaohongshu":["xiaohongshu.com"],
    "douyin":     ["douyin.com", "bytedance.com"],
    "tencent":    ["weixin.qq.com", "qq.com"],
    "bilibili":   ["bilibili.com"],
    "kuaishou":   ["kuaishou.com"],
    "baijiahao":  ["baidu.com"],
    "fanqie":     ["yueduwuxian.com", "fanqienovel.com"],
}

# 输出目录：SAU + 本地持久目录
SAU_COOKIES = Path(os.path.expanduser("~/social-auto-upload/cookies"))
LOCAL_COOKIES = Path(data_dir()) / "cookies"


def extract_platform(platform: str) -> tuple[bool, int]:
    domains = PLATFORM_DOMAINS.get(platform, [])
    if not domains:
        print(f"❌ 未映射平台: {platform}")
        return False, 0

    cookies: list[dict] = []
    seen = set()
    for domain in domains:
        try:
            cj = browser_cookie3.chrome(domain_name=domain)
            for c in cj:
                key = (c.name, c.domain, c.path)
                if key in seen:
                    continue
                seen.add(key)
                cookies.append({
                    "name": str(c.name),
                    "value": str(c.value),
                    "domain": str(c.domain),
                    "path": str(c.path),
                    "expires": float(c.expires) if c.expires else -1.0,
                    "httpOnly": False,  # browser_cookie3 读不到该字段，下方按已知会话 cookie 名补
                    "secure": bool(getattr(c, "secure", False)),
                    "sameSite": "Lax",
                })
                # httpOnly 无法从 browser_cookie3 直接读，按平台会话 cookie 常见值补
                if str(c.name) in ("li_at", "sessionid", "sessionid_ss", "sid_tt",
                                   "auth_token", "ct0", "SESSDATA", "BDUSS"):
                    cookies[-1]["httpOnly"] = True
        except Exception as e:
            print(f"  ⚠️ 提取 {domain} 失败: {e}")

    if not cookies:
        print(f"❌ {platform}: 未从 Chrome 提取到任何 Cookie（该平台在 Chrome 可能未登录）")
        return False, 0

    state = {"cookies": cookies, "origins": []}
    for d in (SAU_COOKIES, LOCAL_COOKIES):
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{platform}_default.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 校验会话 cookie 是否齐全
    want = SESSION_COOKIES.get(platform, [])
    have = {c["name"] for c in cookies}
    missing = [w for w in want if w not in have]
    ok = not missing
    status = "✅ 会话完整" if ok else f"⚠️ 缺会话 cookie: {missing}"
    print(f"{'✅' if ok else '⚠️'} {platform}: 提取 {len(cookies)} 条 Cookie，{status}")
    return ok, len(cookies)


def main():
    targets = sys.argv[1:] or list(PLATFORM_DOMAINS.keys())
    print("从本机 Chrome 提取已登录平台 Cookie（不弹新窗口）...\n")
    results = {}
    for p in targets:
        ok, n = extract_platform(p)
        results[p] = {"ok": ok, "count": n}
    print("\n=== 汇总 ===")
    for p, r in results.items():
        print(f"  {p}: {'✅' if r['ok'] else '❌'} ({r['count']} 条)")
    ok_all = all(r["ok"] for r in results.values())
    print("\n结论:", "全部提取成功 ✅" if ok_all else "部分平台会话不完整，需人工在 Chrome 登录后重跑")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
