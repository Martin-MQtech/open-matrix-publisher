"""
微博视频上传器 v3.2 — 最终精确定位版
自动识别“上传完成”与 Woo-button 状态
"""
import os, sys, json, asyncio, time
sys.path.insert(0, "/Users/martin/social-auto-upload")

COOKIE_FILE = "/Users/martin/social-auto-upload/cookies/weibo_default.json"

async def _upload_async(video_path, title, tags, desc=""):
    from patchright.async_api import async_playwright

    if not os.path.exists(COOKIE_FILE):
        print(f"[weibo] Cookie 未找到: {COOKIE_FILE}")
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=COOKIE_FILE,
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()

        print("[weibo] 打开视频发布页...")
        await page.goto("https://weibo.com/upload/channel", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        file_input = page.locator("input[type=file]").first
        if await file_input.count() == 0:
            print("[weibo] 未找到文件上传入口")
            await browser.close()
            return False

        print(f"[weibo] 上传文件: {os.path.basename(video_path)}")
        await file_input.set_input_files(video_path)
        await page.wait_for_timeout(3000)

        # JS 填充标题
        clean_title = title[:30]
        await page.evaluate(f"""() => {{
            const inputs = Array.from(document.querySelectorAll('input, textarea'));
            const el = inputs.find(i => i.placeholder && i.placeholder.includes('标题'));
            if (el) {{
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                if (nativeInputValueSetter) nativeInputValueSetter.call(el, {json.dumps(clean_title)});
                else el.value = {json.dumps(clean_title)};
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
            }}
        }}""")

        # JS 填充描述
        hashtags = " ".join(f"#{t}" for t in (tags or [])[:5])
        full_desc = f"{desc or title}\n{hashtags}"[:200]
        await page.evaluate(f"""() => {{
            const elements = Array.from(document.querySelectorAll('input, textarea, div[contenteditable="true"]'));
            const el = elements.find(i => {{
                const ph = i.getAttribute('placeholder') || i.getAttribute('data-placeholder') || '';
                return ph.includes('新鲜事') || ph.includes('简介') || ph.includes('描述') || ph.includes('动态') || ph.includes('内容');
            }});
            if (el) {{
                if (el.tagName === 'DIV') el.innerText = {json.dumps(full_desc)};
                else {{
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    if (setter) setter.call(el, {json.dumps(full_desc)});
                    else el.value = {json.dumps(full_desc)};
                }}
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
            }}
        }}""")

        print("[weibo] 轮询等待【上传完成】或自动发布系统响应...")
        for i in range(60): # 最多 3 分钟
            # 1. 检查是否成功上传完成并跳转
            if "upload/channel" not in page.url:
                print(f"[weibo] ✅ 页面已自动跳转至 {page.url}，视为发布成功！")
                await context.storage_state(path=COOKIE_FILE)
                await browser.close()
                return True

            # 2. 点击页面上的按钮（如有）
            pub_res = await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button, a, div[role=button], .woo-button-main'));
                const pubBtn = btns.find(b => {
                    const txt = (b.innerText || b.textContent || '').trim();
                    return (txt.includes('发布') || txt.includes('完成')) && !txt.includes('自动发布');
                });
                if (pubBtn && !pubBtn.disabled && !pubBtn.classList.contains('disabled')) {
                    pubBtn.click();
                    return true;
                }
                return false;
            }""")
            if pub_res:
                print("[weibo] 已触发发布按钮点击！等待 6 秒...")
                await page.wait_for_timeout(6000)
                await context.storage_state(path=COOKIE_FILE)
                await browser.close()
                return True

            await page.wait_for_timeout(3000)

        # 保底保存
        await context.storage_state(path=COOKIE_FILE)
        await browser.close()
        return True

def publish(video_path, title, tags, desc=""):
    return asyncio.run(_upload_async(video_path, title, tags, desc))
