#!/usr/bin/env python3
"""
有头浏览器扫码/交互登录助手 (Headful Browser Login Assistant)
用于弹出可交互的 Chrome/Chromium 浏览器窗口，供用户扫码或输入凭据登录，
并自动检测核心会话凭证状态、捕获并持久化保存 Cookie 至 SAU 和本地 cookies 目录。
"""
import os, sys, json, time, asyncio
from pathlib import Path

from omp_paths import data_dir  # noqa: E402

SAU_ROOT = os.path.expanduser(os.environ.get("SAU_ROOT", "~/social-auto-upload"))
SAU_COOKIES = os.path.join(SAU_ROOT, "cookies")
# 本地 Cookie 目录：统一走 omp_paths.data_dir()（源码态=项目 cookies/，打包态=Application Support 持久目录）
LOCAL_COOKIES = os.path.join(data_dir(), "cookies")

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.7632.6 Safari/537.36"
)

# 各平台严格的核心登录鉴权 Token 列表（绝不包含未登录访客/CSRF Token，防止提前误判退出）
PLATFORMS = {
    # ── 国内平台 ──────────────────────────────────────────────────────────
    "douyin": {
        "name": "抖音",
        "url": "https://creator.douyin.com/",
        "cookie_files": ["douyin_default.json"],
        "auth_cookies": ["sessionid_ss", "sessionid"],
        "success_domains": ["creator.douyin.com"],
        "exclude_keywords": ["login", "signin", "passport"]
    },
    "kuaishou": {
        "name": "快手",
        "url": "https://cp.kuaishou.com/article/publish/video",
        "cookie_files": ["kuaishou_default.json"],
        "auth_cookies": ["kuaishou.server.web_st"],
        "success_domains": ["cp.kuaishou.com"],
        "exclude_keywords": ["login", "pass"]
    },
    "xiaohongshu": {
        "name": "小红书",
        "url": "https://creator.xiaohongshu.com/login",
        "cookie_files": ["xiaohongshu_default.json"],
        "auth_cookies": ["web_session"],
        "success_domains": ["creator.xiaohongshu.com"],
        "exclude_keywords": ["login"]
    },
    "tencent": {
        "name": "微信视频号",
        "url": "https://channels.weixin.qq.com/login.html",
        "cookie_files": ["tencent_default.json"],
        "auth_cookies": ["sessionid", "wxuin"],
        "success_domains": ["channels.weixin.qq.com/platform"],
        "exclude_keywords": ["login.html"]
    },
    "bilibili": {
        "name": "B站",
        "url": "https://passport.bilibili.com/login",
        "cookie_files": ["bilibili_default.json"],
        "auth_cookies": ["SESSDATA"],
        "success_domains": ["bilibili.com", "member.bilibili.com"],
        "exclude_keywords": ["passport.bilibili.com/login", "passport.bilibili.com"]
    },
    "weibo": {
        "name": "微博",
        "url": "https://weibo.com/upload/channel",
        "cookie_files": ["weibo_default.json"],
        "auth_cookies": ["SUB"],
        "success_domains": ["weibo.com"],
        "exclude_keywords": ["login.php", "login", "s.weibo.com"]
    },
    "toutiao": {
        "name": "今日头条",
        "url": "https://mp.toutiao.com/auth/page/login",
        "cookie_files": ["toutiao_default.json"],
        "auth_cookies": ["LOGIN_A", "sessionid"],
        "success_domains": ["mp.toutiao.com/profile_v4"],
        "exclude_keywords": ["auth/page/login", "login"]
    },
    "zhihu": {
        "name": "知乎",
        "url": "https://www.zhihu.com/signin",
        "cookie_files": ["zhihu_default.json"],
        "auth_cookies": ["z_c0"],
        "success_domains": ["zhihu.com"],
        "exclude_keywords": ["signin"]
    },
    "baijiahao": {
        "name": "百家号",
        "url": "https://baijiahao.baidu.com/",
        "cookie_files": ["baijiahao_default.json"],
        "auth_cookies": ["BDUSS", "BAIDUID"],
        "success_domains": ["baijiahao.baidu.com"],
        "exclude_keywords": ["login", "passport"]
    },
    "fanqie": {
        "name": "番茄视频",
        "url": "https://pugc.yueduwuxian.com/fqvideo/login",
        "cookie_files": ["fanqie_default.json"],
        "auth_cookies": ["sessionid", "sessionid_ss"],
        "success_domains": ["pugc.yueduwuxian.com"],
        "exclude_keywords": ["login"]
    },

    # ── API-key 平台（免费官方 API，无浏览器登录，前端走「配置 Key」）──
    "devto": {
        "name": "Dev.to",
        "url": "https://dev.to/settings/account",
        "api_key": True,
        "cookie_files": ["devto_default.json"],
        "auth_cookies": [],
        "success_domains": ["dev.to"],
        "exclude_keywords": []
    },
    "wordpress": {
        "name": "WordPress",
        "url": "https://wordpress.com/me/security",
        "api_key": True,
        "cookie_files": ["wordpress_default.json"],
        "auth_cookies": [],
        "success_domains": ["wordpress.com", "wp-admin"],
        "exclude_keywords": []
    },
    "telegram": {
        "name": "Telegram",
        "url": "https://t.me/BotFather",
        "api_key": True,
        "cookie_files": ["telegram_default.json"],
        "auth_cookies": [],
        "success_domains": ["t.me"],
        "exclude_keywords": []
    },
    "pinterest": {
        "name": "Pinterest",
        "url": "https://developers.pinterest.com/",
        "api_key": True,
        "cookie_files": ["pinterest_default.json"],
        "auth_cookies": [],
        "success_domains": ["pinterest.com"],
        "exclude_keywords": []
    },

    # ── 国际平台 ──────────────────────────────────────────────────────────
    "tiktok": {
        "name": "TikTok",
        "url": "https://www.tiktok.com/login?lang=en",
        "cookie_files": ["tk_default.json", "tiktok_default.json"],
        "auth_cookies": ["sessionid_ss", "sid_tt", "sessionid"],
        "success_domains": ["tiktok.com"],
        "exclude_keywords": ["login", "signin", "accounts.google", "appleid.apple.com"]
    },
    "tk": {
        "name": "TikTok",
        "url": "https://www.tiktok.com/login?lang=en",
        "cookie_files": ["tk_default.json", "tiktok_default.json"],
        "auth_cookies": ["sessionid_ss", "sid_tt", "sessionid"],
        "success_domains": ["tiktok.com"],
        "exclude_keywords": ["login", "signin", "accounts.google", "appleid.apple.com"]
    },
    "youtube": {
        "name": "YouTube",
        "url": "https://studio.youtube.com/",
        "cookie_files": ["youtube_default.json"],
        "auth_cookies": ["SID", "SSID", "HSID", "LOGIN_INFO"],
        "success_domains": ["studio.youtube.com"],
        "exclude_keywords": ["accounts.google.com", "signin"]
    },
    "facebook": {
        "name": "Facebook",
        "url": "https://www.facebook.com/login",
        "cookie_files": ["facebook_default.json"],
        "auth_cookies": ["c_user"],
        "success_domains": ["facebook.com"],
        "exclude_keywords": ["login.php", "login", "recover"]
    },
    "x": {
        "name": "X (Twitter)",
        "url": "https://twitter.com/i/flow/login",
        "cookie_files": ["x_default.json", "twitter_default.json"],
        "auth_cookies": ["auth_token"],
        "success_domains": ["twitter.com", "x.com"],
        "exclude_keywords": ["flow/login", "login", "signin"]
    },
    "twitter": {
        "name": "X (Twitter)",
        "url": "https://twitter.com/i/flow/login",
        "cookie_files": ["x_default.json", "twitter_default.json"],
        "auth_cookies": ["auth_token"],
        "success_domains": ["twitter.com", "x.com"],
        "exclude_keywords": ["flow/login", "login", "signin"]
    },
    "linkedin": {
        "name": "LinkedIn",
        "url": "https://www.linkedin.com/login",
        "cookie_files": ["linkedin_default.json"],
        "auth_cookies": ["li_at"],
        "success_domains": ["linkedin.com/feed", "linkedin.com/in", "linkedin.com"],
        "exclude_keywords": ["login", "checkpoint", "authwall"]
    },
    "instagram": {
        "name": "Instagram",
        "url": "https://www.instagram.com/accounts/login/",
        "cookie_files": ["instagram_default.json"],
        "auth_cookies": ["sessionid"],
        "success_domains": ["instagram.com"],
        "exclude_keywords": ["accounts/login", "login"]
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
    print(f"  📱 请在弹出的浏览器中扫码或使用 Google/账号 登录！")
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
        print(f"（提示：检测到真正登录成功进入后台后，系统将自动捕获凭证并持久化保存）\n")

        deadline = time.time() + 600  # 10分钟超时时间
        login_success = False

        while time.time() < deadline:
            await asyncio.sleep(2)
            try:
                # 检查窗口是否被用户手动全部关闭
                if len(context.pages) == 0:
                    print("⚠️ 浏览器窗口已被用户手动关闭")
                    break

                # 获取所有打开页面的 URL（支持 Google 登录弹窗等子页面）
                active_urls = [p.url for p in context.pages if not p.is_closed()]
                main_url = active_urls[0] if active_urls else page.url

                # 获取当前 context 中保存的所有 Cookie
                state = await context.storage_state()
                cookies = state.get("cookies", [])
                
                # 过滤出有实际值的 Cookie 名称
                cookie_map = {c.get("name"): c.get("value", "") for c in cookies if len(c.get("value", "")) > 0}

                # 检查是否存在必须的真实鉴权 Cookie (严格匹配)
                has_auth_token = any(
                    token in cookie_map and len(cookie_map[token]) >= 6 
                    for token in info.get("auth_cookies", [])
                )

                # 检查 URL 状态：是否有任何一个页面进入了成功页面，且未停留在登录/认证页
                in_oauth_page = any(
                    "accounts.google" in u or "appleid.apple" in u or "oauth" in u.lower() or "login" in u.lower() or "signin" in u.lower()
                    for u in active_urls
                )

                # 专属平台严格判定规则
                is_logged_in = False
                
                if platform_key in ["tiktok", "tk"]:
                    # TikTok: 必须持有 sessionid_ss 或 sid_tt，且不能还在 Google/Apple OAuth 中间页
                    has_tk_session = ("sessionid_ss" in cookie_map and len(cookie_map["sessionid_ss"]) > 10) or \
                                     ("sid_tt" in cookie_map and len(cookie_map["sid_tt"]) > 10) or \
                                     ("sessionid" in cookie_map and len(cookie_map["sessionid"]) > 10)
                    is_logged_in = has_tk_session and (not in_oauth_page or "tiktok.com/@" in main_url or "tiktok.com/foryou" in main_url or "tiktok.com/upload" in main_url)

                elif platform_key == "zhihu":
                    is_logged_in = "z_c0" in cookie_map and len(cookie_map["z_c0"]) > 10 and "signin" not in main_url.lower()

                elif platform_key == "tencent":
                    is_logged_in = "channels.weixin.qq.com/platform" in main_url

                elif platform_key in ["x", "twitter"]:
                    is_logged_in = "auth_token" in cookie_map and len(cookie_map["auth_token"]) > 15 and "flow/login" not in main_url

                elif platform_key == "facebook":
                    is_logged_in = "c_user" in cookie_map and len(cookie_map["c_user"]) > 4 and "login" not in main_url.lower()

                elif platform_key == "linkedin":
                    is_logged_in = "li_at" in cookie_map and len(cookie_map["li_at"]) > 15 and "login" not in main_url.lower()

                elif platform_key == "instagram":
                    is_logged_in = "sessionid" in cookie_map and len(cookie_map["sessionid"]) > 10 and "accounts/login" not in main_url.lower()

                elif platform_key == "youtube":
                    is_logged_in = has_auth_token and "studio.youtube.com" in main_url and "accounts.google" not in main_url

                elif platform_key == "bilibili":
                    is_logged_in = "SESSDATA" in cookie_map and len(cookie_map["SESSDATA"]) > 10 and "passport" not in main_url.lower()

                elif platform_key == "weibo":
                    is_logged_in = "SUB" in cookie_map and len(cookie_map["SUB"]) > 15 and "login" not in main_url.lower()

                elif platform_key == "toutiao":
                    is_logged_in = ("LOGIN_A" in cookie_map or "sessionid" in cookie_map) and "profile_v4" in main_url

                elif platform_key == "xiaohongshu":
                    is_logged_in = "web_session" in cookie_map and len(cookie_map["web_session"]) > 10 and "login" not in main_url.lower()

                elif platform_key == "kuaishou":
                    is_logged_in = "kuaishou.server.web_st" in cookie_map and len(cookie_map["kuaishou.server.web_st"]) > 10

                elif platform_key == "douyin":
                    is_logged_in = ("sessionid_ss" in cookie_map or "sessionid" in cookie_map) and "login" not in main_url.lower()

                else:
                    is_logged_in = has_auth_token and not in_oauth_page

                if is_logged_in:
                    print(f"🎉 检测到【{info['name']}】已成功完成登录！捕获到核心会话凭据。")
                    print(f"📍 当前最终页面: {main_url}")
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

                    # 视频号特例：SAU 上传器实际读取 cookies/tencent_uploader/default，
                    # 而默认 cookie_files 只写 tencent_default.json，故此处额外同步一份，
                    # 否则登录成功但上传器仍报 cookie 失效。
                    if platform_key == "tencent":
                        tdir = os.path.join(SAU_ROOT, "cookies", "tencent_uploader")
                        os.makedirs(tdir, exist_ok=True)
                        tpath = os.path.join(tdir, "default")
                        with open(tpath, "w", encoding="utf-8") as f:
                            json.dump(state, f, indent=2, ensure_ascii=False)
                        print(f"✅ 视频号 Cookie 已同步至上传器目录: {tpath}")

                    login_success = True
                    break
            except Exception as e:
                # 忽略轮询瞬时错误
                pass

        if not login_success:
            print(f"❌ 【{info['name']}】登录超时或未检测到有效凭证。")

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
