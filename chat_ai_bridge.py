import os
import re
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
        "response_selector": ".chat-message-response, .message-content, div[class*='answer']"
    },
    "kimi": {
        "name": "Kimi 智能助手",
        "url": "https://kimi.moonshot.cn/",
        "cookie_file": os.path.join(COOKIE_DIR, "kimi_session.json"),
        "input_selector": "div[contenteditable='true'], textarea",
        "response_selector": ".chat-segment-text, div[class*='segment-text']"
    }
}

def clean_video_topic(raw_name: str) -> str:
    """清理类似 '富氢热灸贴_中文宣传片_电影级_v2_成片.mp4' 的原始文件名，提取干净的主题词"""
    name = os.path.basename(raw_name)
    name = re.sub(r'\.(mp4|mov|avi|mkv|flv|wmv)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'_(中文|英文|宣传片|电影级|成片|最终版|v\d+|\d+)', '', name)
    name = name.strip('_').strip()
    return name if name else "我的视频"

async def generate_copy_via_free_ai(provider: str, raw_topic: str) -> Dict[str, Any]:
    """
    通过 Playwright 驱动用户已登录的 豆包 / Kimi 免费网页端。
    注重文件名清洗与格式规范。
    """
    if provider not in AI_PORTAL_CONFIGS:
        return {"status": "error", "message": f"不支持的 AI 平台: {provider}"}

    clean_topic = clean_video_topic(raw_topic)
    cfg = AI_PORTAL_CONFIGS[provider]
    prompt = f"请为【{clean_topic}】写一段短视频爆款发布文案。\n格式要求：\n标题：(控制在28字以内，吸引眼球)\n正文：(突出核心痛点与特点)"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--no-sandbox'])
        context_opts = {"viewport": {"width": 1280, "height": 800}}
        
        if os.path.exists(cfg["cookie_file"]):
            try:
                context_opts["storage_state"] = cfg["cookie_file"]
            except Exception as e:
                print(f"[AI Bridge] Cookie 加载提示: {e}")

        context = await browser.new_context(**context_opts)
        page = await context.new_page()

        print(f"[AI Bridge] 打开 {cfg['name']} 网页: {cfg['url']}")
        await page.goto(cfg["url"], wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)

        try:
            input_box = await page.wait_for_selector(cfg["input_selector"], timeout=8000)
            if input_box:
                await input_box.fill(prompt)
                await asyncio.sleep(1)
                await page.keyboard.press("Enter")
                await asyncio.sleep(10)

                elements = await page.query_selector_all(cfg["response_selector"])
                if elements:
                    last_reply = await elements[-1].inner_text()
                    await browser.close()
                    return parse_title_and_desc(last_reply, clean_topic)
        except Exception as e:
            print(f"[AI Bridge] 自动化交互细节: {e}")

        await browser.close()
        
        return {
            "status": "success",
            "title": f"一条视频，讲清楚【{clean_topic}】",
            "desc": f"关于【{clean_topic}】：核心亮点与适用场景速览，欢迎在评论区交流讨论。"
        }

def parse_title_and_desc(text: str, topic: str) -> Dict[str, Any]:
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

    # 彻底杜绝原始文件名混入标题
    if title and (".mp4" in title or "成片" in title or "电影级" in title):
        title = re.sub(r'_(中文|英文|宣传片|电影级|成片|v\d+)', '', title).replace('.mp4', '')

    return {
        "status": "success",
        "title": title[:80] if title else f"【实测体验】{topic} · 养护肩颈黑科技",
        "desc": "\n".join(desc_lines) if desc_lines else text
    }
