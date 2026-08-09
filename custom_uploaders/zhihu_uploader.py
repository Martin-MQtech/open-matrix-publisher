"""
知乎视频上传器 — 严格上传完成校验版 v2.0
解决了视频未切片传完就虚报“发布成功”的缺陷
"""
import os, sys, json, asyncio
sys.path.insert(0, os.environ.get("SAU_ROOT", "/Users/martin/social-auto-upload"))

SAU_COOKIES = os.path.join(os.environ.get("SAU_ROOT", "/Users/martin/social-auto-upload"), "cookies")
COOKIE_FILE = os.path.join(SAU_COOKIES, "zhihu_default.json")

async def _upload_async(video_path, title, tags, desc=""):
    try:
        from patchright.async_api import async_playwright
    except ImportError:
        from playwright.async_api import async_playwright

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
        await page.wait_for_timeout(5000)  # 有头模式下等待页面完全渲染

        file_input = page.locator("input[type=file]").first
        if await file_input.count() == 0:
            screenshot_path = "/tmp/zhihu_debug.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"[zhihu] 当前 URL: {page.url}")
            print(f"[zhihu] 页面标题: {await page.title()}")
            print(f"[zhihu] 截图已保存到: {screenshot_path}")
            print("[zhihu] ⚠️ 未找到文件上传入口（Cookie 可能仍无效或重定向至登录）")
            await browser.close()
            return False

        print(f"[zhihu] 开始上传文件: {os.path.basename(video_path)}")
        await file_input.set_input_files(video_path)
        await page.wait_for_timeout(5000)

        # 1. 强制覆盖知乎自动从文件名截取的默认标题
        clean_title = title[:80]
        title_filled = await page.evaluate("""([newTitle]) => {
            const titleEl = document.querySelector('textarea[placeholder*="标题"], input[placeholder*="标题"], textarea.css-1ta9b1n, input.Input');
            if (titleEl) {
                titleEl.focus();
                titleEl.value = newTitle;
                titleEl.dispatchEvent(new Event('input', { bubbles: true }));
                titleEl.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }
            return false;
        }""", [clean_title])
        print(f"[zhihu] 覆盖原始文件名标题 ({clean_title[:20]}...): {'成功' if title_filled else '失败'}")

        # 2. 填充完整正文 Description 到 DraftEditor 富文本框
        if desc:
            desc_filled = await page.evaluate("""([descText]) => {
                const editor = document.querySelector('div.public-DraftEditor-content, div[contenteditable="true"]');
                if (editor) {
                    editor.focus();
                    document.execCommand('insertText', false, descText);
                    editor.dispatchEvent(new Event('input', { bubbles: true }));
                    return true;
                }
                return false;
            }""", [desc])
            print(f"[zhihu] 填写正文 Description 文案: {'成功' if desc_filled else '失败'}")

        # 轮询等待视频上传 100% / 上传成功
        print("[zhihu] 正在轮询等待知乎后台视频切片传输完成...")
        upload_completed = False
        for i in range(100): # 最多等待 5 分钟
            txt = await page.evaluate("() => document.body ? document.body.innerText : ''")
            if "100%" in txt or "上传成功" in txt or "重新上传" in txt or "生成封面" in txt:
                print(f"[zhihu] ({i+1}/100) 视频已传输完成！")
                upload_completed = True
                break
            await page.wait_for_timeout(3000)

        if not upload_completed:
            print("[zhihu] ❌ 视频传输超时（>5分钟），未能在知乎后台完成上传。")
            await browser.close()
            return False

        # 点击发布按钮
        print("[zhihu] 触发最终发布提交...")
        for j in range(10):
            pub_res = await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const pubBtn = btns.find(b => {
                    const t = (b.innerText || b.textContent || '').trim();
                    return t === '发布' || t === '发布视频' || t === '确认发布';
                });
                if (pubBtn && !pubBtn.disabled && !pubBtn.classList.contains('disabled')) {
                    pubBtn.click();
                    return true;
                }
                return false;
            }""")
            if pub_res:
                print("[zhihu] 已点击发布按钮，等待页面确认...")
                await page.wait_for_timeout(6000)
                curr_url = page.url
                page_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                if "manage" in curr_url or "creation" in curr_url or "成功" in page_text or "审核" in page_text or "已发布" in page_text:
                    print(f"[zhihu] ✅ 视频已成功提交发布！当前页面: {curr_url}")
                    await context.storage_state(path=COOKIE_FILE)
                    await browser.close()
                    return True
            await page.wait_for_timeout(2000)

        await browser.close()
        return False

def publish(video_path, title, tags, desc=""):
    return asyncio.run(_upload_async(video_path, title, tags, desc))
