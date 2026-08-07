"""
今日头条视频上传器 — 稳定版
"""
import os, sys, json, asyncio
sys.path.insert(0, "/Users/martin/social-auto-upload")

COOKIE_FILE = "/Users/martin/social-auto-upload/cookies/toutiao_default.json"

async def _upload_async(video_path, title, tags, desc=""):
    from patchright.async_api import async_playwright

    if not os.path.exists(COOKIE_FILE):
        print(f"[toutiao] Cookie 未找到: {COOKIE_FILE}")
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=COOKIE_FILE,
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()

        print("[toutiao] 打开头条号发布页...")
        await page.goto("https://mp.toutiao.com/profile_v4/graphic/publish-video", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        file_input = page.locator("input[type=file]").first
        if await file_input.count() == 0:
            print("[toutiao] 未找到文件上传入口")
            await browser.close()
            return False

        print(f"[toutiao] 上传文件: {os.path.basename(video_path)}")
        await file_input.set_input_files(video_path)
        await page.wait_for_timeout(5000)

        # 标题 ≤30 字
        clean_title = title[:30]
        title_res = await page.evaluate(f"""() => {{
            const inputs = Array.from(document.querySelectorAll('input, textarea'));
            const el = inputs.find(i => i.placeholder && i.placeholder.includes('标题'));
            if (el) {{
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                if (setter) setter.call(el, {json.dumps(clean_title)});
                else el.value = {json.dumps(clean_title)};
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            return false;
        }}""")
        print(f"[toutiao] 填写标题结果: {title_res}")

        print("[toutiao] 等待上传完成并发布...")
        for i in range(40):
            pub_res = await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button, a'));
                const pubBtn = btns.find(b => (b.innerText || '').includes('发布') && !b.disabled);
                if (pubBtn) {
                    pubBtn.click();
                    return true;
                }
                return false;
            }""")
            if pub_res:
                print("[toutiao] 已触发发布按钮！")
                await page.wait_for_timeout(5000)
                await context.storage_state(path=COOKIE_FILE)
                await browser.close()
                return True
            await page.wait_for_timeout(3000)

        await browser.close()
        return False

def publish(video_path, title, tags, desc=""):
    return asyncio.run(_upload_async(video_path, title, tags, desc))
