import os
import json
import asyncio
from typing import Dict, Any

try:
    from patchright.async_api import async_playwright
except ImportError:
    from playwright.async_api import async_playwright

COOKIE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies")

AI_PORTAL_CONFIGS = {
    "doubao": {
        "name": "豆包 (Doubao)",
        "url": "https://www.doubao.com/chat/",
        "cookie_file": os.path.join(COOKIE_DIR, "doubao_session.json"),
        "input_selector": "textarea, div[contenteditable='true']",
        "send_selector": "button[type='submit'], button:has-text('发送')",
        "response_selector": ".chat-message-response, .message-content, div[class*='answer']"
    },
    "kimi": {
        "name": "Kimi 智能助手",
        "url": "https://kimi.moonshot.cn/",
        "cookie_file": os.path.join(COOKIE_DIR, "kimi_session.json"),
        "input_selector": "div[contenteditable='true'], textarea",
        "send_selector": "button:has-text('发送'), .send-button",
        "response_selector": ".chat-segment-text, div[class*='segment-text']"
    },
    "tongyi": {
        "name": "通义千问",
        "url": "https://tongyi.aliyun.com/qianwen/",
        "cookie_file": os.path.join(COOKIE_DIR, "tongyi_session.json"),
        "input_selector": "textarea, div[contenteditable='true']",
        "send_selector": "button:has-text('发送')",
        "response_selector": ".answer-content, div[class*='markdown']"
    }
}

async def generate_copy_via_free_ai(provider: str, video_topic: str) -> Dict[str, Any]:
    """
    通过 Playwright 自动化驱动用户已登录的免费 AI 网页端（豆包 / Kimi / 通义千问），
    输入提示词，获取返回内容并解析成标题与正文。
    """
    if provider not in AI_PORTAL_CONFIGS:
        return {"status": "error", "message": f"不支持的 AI 平台: {provider}"}

    cfg = AI_PORTAL_CONFIGS[provider]
    prompt = f"请为短视频【{video_topic}】撰写一段适合全网分发的文案。\n要求格式严格如下：\n标题：(控制在28字以内)\n正文：(突出痛点与产品亮点，适合社交媒体发布)"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--no-sandbox'])
        context_opts = {"viewport": {"width": 1280, "height": 800}}
        
        if os.path.exists(cfg["cookie_file"]):
            try:
                context_opts["storage_state"] = cfg["cookie_file"]
            except Exception as e:
                print(f"[AI Bridge] Cookie load failed: {e}")

        context = await browser.new_context(**context_opts)
        page = await context.new_page()

        print(f"[AI Bridge] 正在打开 {cfg['name']} 网页端: {cfg['url']}")
        await page.goto(cfg["url"], wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # 检查是否需要登录
        page_content = await page.content()
        if "登录" in page_content and not os.path.exists(cfg["cookie_file"]):
            print(f"[AI Bridge] 检测到未登录状态，等待用户在浏览器中自主完成登录...")
            # 留出 45 秒给用户登录
            for _ in range(45):
                if not page.is_closed():
                    curr_url = page.url
                    if "chat" in curr_url or "qianwen" in curr_url:
                        break
                await asyncio.sleep(1)
            
            # 保存 Session 供以后免登录使用
            try:
                os.makedirs(COOKIE_DIR, exist_ok=True)
                await context.storage_state(path=cfg["cookie_file"])
                print(f"[AI Bridge] 成功持久化 {cfg['name']} 登录 Cookie!")
            except Exception as e:
                print(f"[AI Bridge] Cookie 保存异常: {e}")

        # 查找输入框并输入 Prompt
        try:
            input_box = await page.wait_for_selector(cfg["input_selector"], timeout=10000)
            if input_box:
                await input_box.fill(prompt)
                await asyncio.sleep(1)
                await page.keyboard.press("Enter")
                print(f"[AI Bridge] 成功提交 Prompt，等待 {cfg['name']} AI 思考生成中...")

                # 等待 AI 生成完毕 (约 10-15 秒)
                await asyncio.sleep(12)

                # 提取最新一条回答内容
                elements = await page.query_selector_all(cfg["response_selector"])
                if elements:
                    last_reply = await elements[-1].inner_text()
                    print(f"[AI Bridge] 成功抓取回答文本: {last_reply[:60]}...")
                    await browser.close()
                    return parse_title_and_desc(last_reply)
        except Exception as e:
            print(f"[AI Bridge] 自动化执行细节: {e}")

        await browser.close()
        
        # 降级备用格式
        return {
            "status": "success",
            "title": f"【实测体验】{video_topic} · 温氢双护硬核推荐",
            "desc": f"关于【{video_topic}】：利用固态氢材料与道地艾草结合，热能与氢分子协同作用，带来真正深层滋养！\n木齐科技 自研固态氢 | www.emuqi.com"
        }

def parse_title_and_desc(text: str) -> Dict[str, Any]:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    title = ""
    desc_lines = []

    for l in lines:
        if l.startswith("标题：") or l.startswith("标题:"):
            title = l.replace("标题：", "").replace("标题:", "").strip()
        elif l.startswith("正文：") or l.startswith("正文:"):
            desc_lines.append(l.replace("正文：", "").replace("正文:", "").strip())
        elif title:
            desc_lines.append(l)

    if not title and lines:
        title = lines[0].replace("标题：", "").replace("标题:", "").strip()
        desc_lines = lines[1:]

    return {
        "status": "success",
        "title": title[:80] if title else "富氢热灸贴温氢双护 · 打工人肩颈救星",
        "desc": "\n".join(desc_lines) if desc_lines else text
    }
