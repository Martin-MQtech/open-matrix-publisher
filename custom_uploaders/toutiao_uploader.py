"""
今日头条视频上传器 — 严格上传完成校验版 v2.0
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
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=COOKIE_FILE,
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()

        print("[toutiao] 打开头条号视频发布页...")
        await page.goto("https://mp.toutiao.com/profile_v4/xigua/upload-video", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)  # 等待页面组件完全加载

        file_input = page.locator("input[type=file]").first
        if await file_input.count() == 0:
            screenshot_path = "/tmp/toutiao_debug.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"[toutiao] 当前 URL: {page.url}")
            print(f"[toutiao] 页面标题: {await page.title()}")
            print(f"[toutiao] 截图已保存到: {screenshot_path}")
            print("[toutiao] ⚠️ 未找到文件上传入口（Cookie 可能仍无效或重定向至登录）")
            await browser.close()
            return False

        print(f"[toutiao] 上传文件: {os.path.basename(video_path)}")
        await file_input.set_input_files(video_path)
        await page.wait_for_timeout(5000)

        # 标题 ≤30 字
        clean_title = title[:30]
        title_res = await page.evaluate(f"""() => {{
            const inputs = Array.from(document.querySelectorAll('input, textarea, div[contenteditable="true"]'));
            const el = inputs.find(i => {{
                const ph = i.placeholder || i.getAttribute('placeholder') || i.getAttribute('aria-label') || '';
                const cls = i.className || '';
                return ph.includes('标题') || ph.includes('作品') || cls.includes('input') || cls.includes('title');
            }});
            if (el) {{
                if (el.tagName === 'DIV') {{
                    el.innerText = {json.dumps(clean_title)};
                }} else {{
                    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                    if (setter) setter.call(el, {json.dumps(clean_title)});
                    else el.value = {json.dumps(clean_title)};
                }}
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            return false;
        }}""")
        print(f"[toutiao] 填写标题结果: {title_res}")

        print("[toutiao] 正在轮询等待头条后台视频传输完成...")
        upload_completed = False
        for i in range(100): # 最多 5 分钟
            txt = await page.evaluate("() => document.body ? document.body.innerText : ''")
            if "100%" in txt or "上传完成" in txt or "重新上传" in txt or "封面" in txt:
                print(f"[toutiao] ({i+1}/100) 视频已传输完成！")
                upload_completed = True
                break
            await page.wait_for_timeout(3000)

        if not upload_completed:
            print("[toutiao] ❌ 头条视频传输超时，未完成上传。")
            await browser.close()
            return False

        print("[toutiao] 触发最终发布...")
        for j in range(10):
            pub_res = await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button, a'));
                const pubBtn = btns.find(b => {
                    const txt = (b.innerText || b.textContent || '').trim();
                    return (txt === '发布' || txt === '确认发布') && !b.disabled;
                });
                if (pubBtn) {
                    pubBtn.click();
                    return true;
                }
                return false;
            }""")
            if pub_res:
                print("[toutiao] 已点击发布按钮！等待确认...")
                await page.wait_for_timeout(8000)
                await context.storage_state(path=COOKIE_FILE)
                await browser.close()
                return True
            await page.wait_for_timeout(2000)

        await browser.close()
        return False

def publish(video_path, title, tags, desc=""):
    return asyncio.run(_upload_async(video_path, title, tags, desc))
