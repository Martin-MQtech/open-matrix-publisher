#!/usr/bin/env python3
"""
有头浏览器扫码/交互登录助手 (Headful Browser Login Assistant)
用于弹出可交互的 Chrome/Chromium 浏览器窗口，供用户扫码或输入凭据登录，
并自动检测会话状态、捕获并持久化保存 Cookie 至 SAU 和本地 cookies 目录。
"""
import os, sys, json, time, asyncio
from pathlib import Path

SAU_ROOT = os.environ.get("SAU_ROOT", "/Users/martin/social-auto-upload")
SAU_COOKIES = os.path.join(SAU_ROOT, "cookies")
LOCAL_COOKIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies")

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.7632.6 Safari/537.36"
)

PLATFORMS = {
    # ── 国内平台 ──────────────────────────────────────────────────────────
    "douyin": {
        "name": "抖音",
        "url": "https://creator.douyin.com/",
        "cookie_files": ["douyin_default.json"],
        "session_cookies": ["sessionid", "sessionid_ss", "passport_csrf_token", "odin_tt"],
        "success_domains": ["creator.douyin.com"],
        "exclude_keywords": ["login", "signin"]
    },
    "kuaishou": {
        "name": "快手",
        "url": "https://cp.kuaishou.com/article/publish/video",
        "cookie_files": ["kuaishou_default.json"],
        "session_cookies": ["kuaishou.server.web_st", "userId", "did"],
        "success_domains": ["cp.kuaishou.com"],
        "exclude_keywords": ["login"]
    },
    "xiaohongshu": {
        "name": "小红书",
        "url": "https://creator.xiaohongshu.com/login",
        "cookie_files": ["xiaohongshu_default.json"],
        "session_cookies": ["web_session", "a1", "webId"],
        "success_domains": ["creator.xiaohongshu.com"],
        "exclude_keywords": ["login"]
    },
    "tencent": {
        "name": "微信视频号",
        "url": "https://channels.weixin.qq.com/login.html",
        "cookie_files": ["tencent_default.json"],
        "session_cookies": ["sessionid", "wxuin", "channels_token"],
        "success_domains": ["channels.weixin.qq.com/platform"],
        "exclude_keywords": ["login.html"]
    },
    "bilibili": {
        "name": "B站",
        "url": "https://passport.bilibili.com/login",
        "cookie_files": ["bilibili_default.json"],
        "session_cookies": ["SESSDATA", "bili_jct", "DedeUserID"],
        "success_domains": ["bilibili.com", "member.bilibili.com"],
        "exclude_keywords": ["passport.bilibili.com/login"]
    },
    "weibo": {
        "name": "微博",
        "url": "https://weibo.com/upload/channel",
        "cookie_files": ["weibo_default.json"],
        "session_cookies": ["SUB", "SUBP"],
        "success_domains": ["weibo.com"],
        "exclude_keywords": ["login.php", "login"]
    },
    "toutiao": {
        "name": "今日头条",
        "url": "https://mp.toutiao.com/auth/page/login",
        "cookie_files": ["toutiao_default.json"],
        "session_cookies": ["LOGIN_A", "sessionid", "passport_csrf_token"],
        "success_domains": ["mp.toutiao.com/profile_v4"],
        "exclude_keywords": ["auth/page/login"]
    },
    "zhihu": {
        "name": "知乎",
        "url": "https://www.zhihu.com/signin",
        "cookie_files": ["zhihu_default.json"],
        "session_cookies": ["z_c0"],
        "success_domains": ["zhihu.com"],
        "exclude_keywords": ["signin"]
    },

    # ── 国际平台 ──────────────────────────────────────────────────────────
    "tiktok": {
        "name": "TikTok",
        "url": "https://www.tiktok.com/login?lang=en",
        "cookie_files": ["tk_default.json", "tiktok_default.json"],
        "session_cookies": ["sid_tt", "sessionid_ss", "tt_csrf_token", "sessionid"],
        "success_domains": ["tiktok.com"],
        "exclude_keywords": ["login", "signin"]
    },
    "tk": {
        "name": "TikTok",
        "url": "https://www.tiktok.com/login?lang=en",
        "cookie_files": ["tk_default.json", "tiktok_default.json"],
        "session_cookies": ["sid_tt", "sessionid_ss", "tt_csrf_token", "sessionid"],
        "success_domains": ["tiktok.com"],
        "exclude_keywords": ["login", "signin"]
    },
    "youtube": {
        "name": "YouTube",
        "url": "https://studio.youtube.com/",
        "cookie_files": ["youtube_default.json"],
        "session_cookies": ["SID", "HSID", "SSID", "LOGIN_INFO"],
        "success_domains": ["studio.youtube.com"],
        "exclude_keywords": ["accounts.google.com"]
    },
    "facebook": {
        "name": "Facebook",
        "url": "https://www.facebook.com/login",
        "cookie_files": ["facebook_default.json"],
        "session_cookies": ["c_user", "xs"],
        "success_domains": ["facebook.com"],
        "exclude_keywords": ["login.php", "login"]
    },
    "x": {
        "name": "X (Twitter)",
        "url": "https://twitter.com/i/flow/login",
        "cookie_files": ["x_default.json", "twitter_default.json"],
        "session_cookies": ["auth_token", "ct0"],
        "success_domains": ["twitter.com", "x.com"],
        "exclude_keywords": ["flow/login", "login"]
    },
    "twitter": {
        "name": "X (Twitter)",
        "url": "https://twitter.com/i/flow/login",
        "cookie_files": ["x_default.json", "twitter_default.json"],
        "session_cookies": ["auth_token", "ct0"],
        "success_domains": ["twitter.com", "x.com"],
        "exclude_keywords": ["flow/login", "login"]
    },
    "linkedin": {
        "name": "LinkedIn",
        "url": "https://www.linkedin.com/login",
        "cookie_files": ["linkedin_default.json"],
        "session_cookies": ["li_at"],
        "success_domains": ["linkedin.com/feed", "linkedin.com/in", "linkedin.com"],
        "exclude_keywords": ["login", "checkpoint"]
    },
    "instagram": {
        "name": "Instagram",
        "url": "https://www.instagram.com/accounts/login/",
        "cookie_files": ["instagram_default.json"],
        "session_cookies": ["sessionid", "ds_user_id"],
        "success_domains": ["instagram.com"],
        "exclude_keywords": ["accounts/login"]
    }
}

async def login_platform(platform_key):
    platform_key = platform_key.lower().strip()
    if platform_key not in PLATFORMS:
        print(f"❌ 未知平台: {platform_key}")
        print(f"当前支持的平台列表: {', '.join(PLATFORMS.keys())}")
        return False

    info = PLATFORMS[platform_key]
    print(f"\n==================================================")
    print(f"  🚀 正在为你打开【{info['name']}】登录浏览器窗口...")
    print(f"  🔗 目标地址: {info['url']}")
    print(f"  📱 请在弹出的浏览器中进行扫码或账号登录！")
    print(f"==================================================\n")

    try:
        from patchright.async_api import async_playwright
    except ImportError:
        from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=CHROME_UA
        )
        page = await context.new_page()

        try:
            await page.goto(info["url"], wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"⚠️ 页面加载提示: {e}，请在浏览器中继续操作...")

        print(f"⏳ 正在等待你在浏览器中完成【{info['name']}】登录...")
        print(f"（提示：检测到登录成功并进入后台后，系统将自动捕获凭证并持久化保存）\n")

        deadline = time.time() + 300  # 5分钟超时时间
        login_success = False

        while time.time() < deadline:
            await asyncio.sleep(2)
            try:
                if len(context.pages) == 0:
                    print("⚠️ 浏览器窗口已被手动关闭")
                    break

                curr_url = page.url
                state = await context.storage_state()
                cookies = state.get("cookies", [])
                cookie_names = {c.get("name") for c in cookies}

                has_session_cookie = any(req in cookie_names for req in info.get("session_cookies", []))
                url_match = any(domain in curr_url for domain in info.get("success_domains", []))
                url_not_excluded = not any(kw in curr_url.lower() for kw in info.get("exclude_keywords", []))

                # 特殊平台强化规则
                if platform_key == "zhihu":
                    is_logged_in = "z_c0" in cookie_names and "signin" not in curr_url.lower()
                elif platform_key == "tencent":
                    is_logged_in = ("channels.weixin.qq.com/platform" in curr_url) or ("sessionid" in cookie_names and "login" not in curr_url.lower())
                else:
                    is_logged_in = has_session_cookie or (url_match and url_not_excluded)

                if is_logged_in:
                    print(f"🎉 检测到【{info['name']}】已成功登录！当前页面: {curr_url}")
                    await asyncio.sleep(3)  # 等待所有 Cookie 充分写盘
                    state = await context.storage_state()

                    # 保存 Cookie 到 SAU 和 本地 两个目录的所有目标文件名
                    for target_dir in [SAU_COOKIES, LOCAL_COOKIES]:
                        os.makedirs(target_dir, exist_ok=True)
                        for cf in info["cookie_files"]:
                            target_path = os.path.join(target_dir, cf)
                            with open(target_path, "w", encoding="utf-8") as f:
                                json.dump(state, f, indent=2, ensure_ascii=False)
                            print(f"✅ Cookie 已安全持久化保存至: {target_path}")

                    login_success = True
                    break
            except Exception as e:
                # 忽略导航瞬时错误
                pass

        if not login_success:
            print(f"❌ 【{info['name']}】登录超时或未检测到凭证。")

        try:
            await browser.close()
        except Exception:
            pass

        return login_success

async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target == "all":
        for pk in ["toutiao", "weibo", "zhihu", "tiktok"]:
            await login_platform(pk)
    elif target in PLATFORMS:
        await login_platform(target)
    else:
        print(f"❌ 未知平台: {target}")
        print(f"当前支持的平台列表: {', '.join(PLATFORMS.keys())}")

if __name__ == "__main__":
    asyncio.run(main())
