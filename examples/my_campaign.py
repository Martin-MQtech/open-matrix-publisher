#!/usr/bin/env python3
"""
Open Matrix Publisher — Campaign Example
==========================================
Copy this file to your project folder and edit the CONFIG section.
Then run: python3 my_campaign.py
"""
import os, sys
# Point to the Open Matrix Publisher tool directory
TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOL_DIR)

from real_uploader_engine import RealPlatformUploader

# ─── CONFIG ───────────────────────────────────────────────────────────────────
WORKSPACE   = "/path/to/your/video/project"          # ← Your project folder
CN_VIDEO    = os.path.join(WORKSPACE, "video_cn.mp4")
EN_VIDEO    = os.path.join(WORKSPACE, "video_en.mp4")

TITLE_CN    = "你的视频标题（中文）"
TITLE_EN    = "Your Video Title (English)"
DESC_CN     = "视频描述，支持话题标签 #话题"
DESC_EN     = "Video description with hashtags #hashtag"
TAGS_CN     = ["标签1", "标签2", "标签3"]
TAGS_EN     = ["tag1", "tag2", "tag3"]
# ─────────────────────────────────────────────────────────────────────────────

def main():
    uploader = RealPlatformUploader(headless=True)

    # Domestic platforms (Chinese video)
    domestic = [
        ("douyin",    CN_VIDEO, TITLE_CN, DESC_CN, TAGS_CN),
        ("weibo",     CN_VIDEO, TITLE_CN, DESC_CN, TAGS_CN),
        ("xiaohongshu", CN_VIDEO, TITLE_CN, DESC_CN, TAGS_CN),
    ]

    # Global platforms (English video)
    global_platforms = [
        ("youtube",   EN_VIDEO, TITLE_EN, DESC_EN, TAGS_EN),
        ("tiktok",    EN_VIDEO, TITLE_EN, DESC_EN, TAGS_EN),
        ("x",         EN_VIDEO, TITLE_EN, DESC_EN, TAGS_EN),
        ("linkedin",  EN_VIDEO, TITLE_EN, DESC_EN, TAGS_EN),
        ("instagram", EN_VIDEO, TITLE_EN, DESC_EN, TAGS_EN),
    ]

    all_tasks = domestic + global_platforms
    results = {}

    for platform, video, title, desc, tags in all_tasks:
        print(f"\n[→] Dispatching to {platform}...")
        try:
            ok = uploader.upload(platform, video, title, desc, tags)
            results[platform] = "✅ OK" if ok else "⚠️ FAILED"
        except Exception as e:
            results[platform] = f"❌ ERROR: {e}"

    print("\n" + "="*50)
    print("Dispatch Results:")
    for p, r in results.items():
        print(f"  {p:16s} {r}")

if __name__ == "__main__":
    main()
