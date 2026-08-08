#!/usr/bin/env python3
"""
有头浏览器扫码登录助手 (Headful Chrome Login Assistant)
用于弹出可交互的浏览器窗口，供用户扫码登录并自动提取/持久化保存 Cookie
"""
import os, sys, json, time, asyncio

SAU_COOKIES = "/Users/martin/social-auto-upload/cookies"
LOCAL_COOKIES = "/Users/martin/Documents/2026 BUSINESS MTRIX /20260807 OpenMatrixpublister/cookies"

PLATFORMS = {
    "toutiao": {
        "name": "今日头条",
        "url": "https://mp.toutiao.com/auth/page/login",
        "success_indicator": "mp.toutiao.com/profile_v4",
        "cookie_file": "toutiao_default.json"
    },
    "weibo": {
        "name": "微博",
        "url": "https://weibo.com/upload/channel",
        "success_indicator": "weibo.com",
        "cookie_file": "weibo_default.json"
    },
    "zhihu": {
        "name": "知乎",
        "url": "https://www.zhihu.com/signin",
        "success_indicator": "zhihu.com",
        "cookie_file": "zhihu_default.json"
    }
}

async def login_platform(platform_key):
    info = PLATFORMS[platform_key]
    print(f"\n==================================================")
    print(f"  正在为你打开【{info['name']}】登录浏览器窗口...")
    print(f"  请在弹出的浏览器中用手机 App 扫码登录！")
    print(f"==================================================\n")

    try:
        from patchright.async_api import async_playwright
    except ImportError:
        from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # 打开真实的有头浏览器窗口 (headless=False)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        await page.goto(info["url"])

        print(f"⏳ 正在等待你在浏览器中完成【{info['name']}】扫码登录...")
        print(f"（提示：扫码成功并成功进入后台后，脚本将自动捕获凭证并关闭窗口）\n")

        deadline = time.time() + 180 # 3分钟超时时间
        login_success = False

        while time.time() < deadline:
            await asyncio.sleep(2)
            curr_url = page.url
            state = await context.storage_state()

            # 专属平台的精确登录成功条件判断
            if platform_key == "zhihu":
                has_zc0 = any(c.get("name") == "z_c0" for c in state.get("cookies", []))
                is_logged_in = has_zc0 and "signin" not in curr_url.lower()
            else:
                is_logged_in = (
                    info["success_indicator"] in curr_url 
                    and "login" not in curr_url.lower() 
                    and "auth" not in curr_url.lower() 
                    and "signin" not in curr_url.lower()
                )

            if is_logged_in:
                print(f"🎉 检测到【{info['name']}】已成功登录并捕获凭证！当前页面: {curr_url}")
                await asyncio.sleep(2)
                state = await context.storage_state()
                
                # 保存 Cookie 到两个目录
                for target_dir in [SAU_COOKIES, LOCAL_COOKIES]:
                    os.makedirs(target_dir, exist_ok=True)
                    target_path = os.path.join(target_dir, info["cookie_file"])
                    with open(target_path, "w", encoding="utf-8") as f:
                        json.dump(state, f, indent=2, ensure_ascii=False)
                    print(f"✅ Cookie 已安全持久化保存至: {target_path}")

                login_success = True
                break

        if not login_success:
            print(f"❌ 【{info['name']}】登录超时或未成功保存。")
        
        await browser.close()
        return login_success

async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target == "all":
        for pk in ["toutiao", "weibo"]:
            await login_platform(pk)
    elif target in PLATFORMS:
        await login_platform(target)
    else:
        print(f"未知平台: {target}")

if __name__ == "__main__":
    asyncio.run(main())
