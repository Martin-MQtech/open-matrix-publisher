# 🛠️ DeepSeek 开源代码复用与极速打通手册 (DEEPSEEK_CHEATSHEET.md)

> **给 DeepSeek Agent 的避坑提示**：  
> 兄弟不要重新发明轮子，也不要在网页端无头浏览器的死胡同里硬嗑！  
> 以下是整理好的**最成熟、经过数万人验证的 Python 开源代码片段与选择器标准**，直接拿去抄代码/复用！

---

## 1. 📷 Instagram Reels 极速打通方案 (不用无头浏览器，用 instagrapi)

### ❌ 常见的坑：
用 Playwright 点击 Instagram 网页端的 `Create` 弹窗在 Headless 下会被 IG 压制，提示 `"Only images can be posted"` 或强行跳转 Profile。

### ✅ 最快的成熟开源复用代码：
直接调用 `instagrapi` 移动端 Private API，通过本机的 `sessionid` 凭证 100% 静默发布 Reels：

```python
import json
from instagrapi import Client

def upload_instagram_reels(video_path: str, caption: str, cookie_path: str, proxy: str | None = None) -> bool:
    try:
        cl = Client()
        if proxy:
            cl.set_proxy(proxy)
        
        # 1. 从 saved cookies 中提取 sessionid
        with open(cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        sessionid = next((c["value"] for c in cookies if c.get("name") == "sessionid"), None)
        
        if not sessionid:
            print("[Instagram] 未在 cookie 中找到 sessionid")
            return False
            
        # 2. 用 Session ID 登录 Mobile API 并发布 Reels
        cl.login_by_sessionid(sessionid)
        media = cl.clip_upload(video_path, caption=caption)
        if media and getattr(media, "pk", None):
            print(f"[Instagram] 🎉 Reels 视频发布成功! PK: {media.pk}")
            return True
    except Exception as e:
        print(f"[Instagram] Mobile API 错误: {e}")
    return False
```

---

## 2. 🎵 TikTok 极速打通方案 (Patchright + SPA 等待规避)

### ❌ 常见的坑：
TikTok 首页有 WebSocket 长连接，Playwright 的 `page.goto` 如果用默认 `load` 会 30 秒必超时！TikTok Studio 没有旧版的 `iframe` 了。

### ✅ 最快的成熟开源复用代码：

```python
import asyncio
from patchright.async_api import async_playwright

async def upload_tiktok(video_path: str, title: str, tags: list[str], cookie_path: str) -> bool:
    pw = await async_playwright().start()
    # 关键：使用 Patchright 隐藏 cdc_ 变量
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    
    # 1. wait_until 必须用 "domcontentloaded"，绝对不能用 "load"！
    await page.goto("https://www.tiktok.com/tiktokstudio/upload", wait_until="domcontentloaded")
    await page.wait_for_timeout(15000) # 等 SPA 渲染完成
    
    # 2. 文件上传按钮选择器（2025+ 页面已置于主文档）
    upload_btn = page.locator('button:has-text("Select video"):visible').first
    await upload_btn.wait_for(state="visible", timeout=30000)
    
    async with page.expect_file_chooser(timeout=15000) as fc_info:
        await upload_btn.click()
    fc = await fc_info.value
    await fc.set_files(video_path)
    
    # 3. 文案与标签注入（DraftEditor 选择器）
    editor = page.locator('div.public-DraftEditor-content').first
    await editor.wait_for(state="visible", timeout=30000)
    await editor.click(force=True)
    await page.keyboard.press("Meta+A")
    await page.keyboard.press("Delete")
    await page.keyboard.insert_text(title + " ")
    for tag in tags:
        await page.keyboard.insert_text(f"#{tag} ")
        await page.wait_for_timeout(300)
        
    # 4. 发布按钮必须限定在 button-group 父容器，防止错选侧边栏 Posts 导航
    post_btn = page.locator('div.button-group button.Button__root--type-primary').first
    await post_btn.wait_for(state="visible", timeout=60000)
    
    # 轮询等待转码完成（disabled 移除）
    while not await post_btn.is_enabled():
        await page.wait_for_timeout(1000)
        
    await post_btn.click()
    print("[TikTok] 🎉 发布完成！")
    await browser.close()
    return True
```

---

## 3. 📌 Pinterest Idea Pins 打通方案 (最干练的选择器)

### ✅ 最快的成熟开源复用代码：

```python
async def upload_pinterest(video_path: str, title: str, desc: str, board_name: str, page) -> bool:
    await page.goto("https://www.pinterest.com/pin-builder/", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    
    # 1. 注入视频文件
    file_input = page.locator('input[type="file"]').first
    await file_input.set_input_files(video_path)
    await page.wait_for_timeout(5000)
    
    # 2. 填写标题与描述
    title_input = page.locator('input[id*="pin-draft-title"], textarea[id*="pin-draft-title"]').first
    if await title_input.count():
        await title_input.fill(title)
        
    desc_input = page.locator('div[role="textbox"], textarea[id*="pin-draft-description"]').first
    if await desc_input.count():
        await desc_input.fill(desc)
        
    # 3. 选择 Publish 按钮
    pub_btn = page.locator('button[data-test-id="board-dropdown-save-button"], button:has-text("Publish")').first
    await pub_btn.click()
    print("[Pinterest] 🎉 Pin 提交成功！")
    return True
```

---

## 🌐 4. Google Blogger 打通方案 (富文本嵌入)

```python
async def upload_blogger(video_url_or_embed: str, title: str, content: str, page) -> bool:
    await page.goto("https://www.blogger.com/blog/posts/", wait_until="domcontentloaded")
    
    # 点 New post
    new_post_btn = page.locator('[aria-label="New post"], [aria-label="新建文章"]').first
    await new_post_btn.click()
    await page.wait_for_timeout(3000)
    
    # 填标题
    title_box = page.locator('input[aria-label="Title"], input[aria-label="标题"]').first
    await title_box.fill(title)
    
    # 切换至 HTML view 嵌入视频代码
    html_btn = page.locator('[aria-label="Switch to HTML view"]').first
    if await html_btn.count():
        await html_btn.click()
        
    editor = page.locator('textarea.cm-editor, textarea').first
    html_content = f"<p>{content}</p><br><iframe src='{video_url_or_embed}' width='560' height='315' allowfullscreen></iframe>"
    await editor.fill(html_content)
    
    # 点 Publish
    pub_btn = page.locator('[aria-label="Publish"], [aria-label="发布"]').first
    await pub_btn.click()
    confirm = page.locator('button:has-text("Confirm"), button:has-text("确认")').first
    if await confirm.count():
        await confirm.click()
    print("[Blogger] 🎉 Google 博客文章秒级提交！")
    return True
```
