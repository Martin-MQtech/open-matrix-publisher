"""
知乎视频上传器 — 稳定修正版 (修复 TypeError Illegal invocation)
"""
import os, sys, json, asyncio
sys.path.insert(0, "/Users/martin/social-auto-upload")

COOKIE_FILE = "/Users/martin/social-auto-upload/cookies/zhihu_default.json"

async def _upload_async(video_path, title, tags, desc=""):
    from patchright.async_api import async_playwright

    if not os.path.exists(COOKIE_FILE):
        print(f"[zhihu] Cookie 未找到: {COOKIE_FILE}")
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=COOKIE_FILE,
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()

        print("[zhihu] 打开知乎创作中心...")
        await page.goto("https://www.zhihu.com/creator/video-upload", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        file_input = page.locator("input[type=file]").first
        if await file_input.count() == 0:
            print("[zhihu] 未找到文件上传入口")
            await browser.close()
            return False

        print(f"[zhihu] 上传文件: {os.path.basename(video_path)}")
        await file_input.set_input_files(video_path)
        await page.wait_for_timeout(5000)

        # 设置标题
        clean_title = title[:80]
        title_res = await page.evaluate(f"""() => {{
            const inputs = Array.from(document.querySelectorAll('input, textarea'));
            const el = inputs.find(i => i.placeholder && (i.placeholder.includes('标题') || i.placeholder.includes('写个标题')));
            if (el) {{
                el.value = {json.dumps(clean_title)};
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            return false;
        }}""")
        print(f"[zhihu] 填写标题结果: {title_res}")

        # 设置描述
        full_desc = f"{desc or title}\n" + " ".join(f"#{t}" for t in (tags or [])[:5])
        desc_res = await page.evaluate(f"""() => {{
            const elements = Array.from(document.querySelectorAll('input, textarea, div[contenteditable="true"]'));
            const el = elements.find(i => {{
                const ph = i.getAttribute('placeholder') || i.getAttribute('data-placeholder') || '';
                return ph.includes('简介') || ph.includes('描述') || ph.includes('详细') || ph.includes('添加');
            }});
            if (el) {{
                if (el.tagName === 'DIV') el.innerText = {json.dumps(full_desc)};
                else {{
                    el.value = {json.dumps(full_desc)};
                }}
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            return false;
        }}""")
        print(f"[zhihu] 填写描述结果: {desc_res}")

        print("[zhihu] 等待上传完成并发布...")
        for i in range(40):
            pub_res = await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const pubBtn = btns.find(b => (b.innerText || '').includes('发布') && !b.disabled);
                if (pubBtn) {
                    pubBtn.click();
                    return true;
                }
                return false;
            }""")
            if pub_res:
                print("[zhihu] 已触发发布按钮！")
                await page.wait_for_timeout(5000)
                await context.storage_state(path=COOKIE_FILE)
                await browser.close()
                return True
            await page.wait_for_timeout(3000)

        await browser.close()
        return False

def publish(video_path, title, tags, desc=""):
    return asyncio.run(_upload_async(video_path, title, tags, desc))
