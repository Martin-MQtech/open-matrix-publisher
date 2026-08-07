#!/usr/bin/env python3
"""
国际主流平台一键批量分发脚本 v1 — 英文版短视频
适配平台：YouTube Shorts, TikTok, X (Twitter), LinkedIn, Facebook, Instagram
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(__file__))
from real_uploader_engine import RealPlatformUploader

WORKSPACE = "/Users/martin/Desktop/Codex视频处理/20260806 富氢热灸贴双语视频"
EN_VIDEO  = os.path.join(WORKSPACE, "富氢热灸贴营销短视频_英文配音版_v1_成片.mp4")
HISTORY_FILE = os.path.join(WORKSPACE, "dispatch_history.json")

# 英文版通用文案与标题
EN_TITLE = "Hydrogen Molecular Synergy Ergonomic Patch | MUQI Tech OEM/ODM"
EN_DESC = (
    "Hydrogen molecular diffusion × Far-infrared thermal synergy. "
    "Designed for desk workers. 80×205mm ergonomic patch.\n"
    "MUQI Tech | OEM/ODM Private Label\n"
    "Scientific discussion for reference only.\n"
    "Website: www.emuqi.com"
)
EN_TAGS = ["HydrogenPatch", "MUQITech", "OEM", "PrivateLabel", "HydrogenHealth", "Ergonomics"]

GLOBAL_PLATFORMS = ["youtube", "tiktok", "x", "linkedin", "facebook", "instagram"]

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"records": [], "last_dispatch": {}}

def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def is_published(platform_id):
    history = load_history()
    video_basename = os.path.basename(EN_VIDEO)
    for rec in history.get("records", []):
        if rec.get("video_file") == video_basename:
            p_data = rec.get("platforms", {}).get(platform_id, {})
            if p_data.get("status") == "success":
                return True
    return False

def record_success(platform_id, pub_id, link):
    history = load_history()
    video_basename = os.path.basename(EN_VIDEO)
    
    target_rec = None
    for rec in history.get("records", []):
        if rec.get("video_file") == video_basename:
            target_rec = rec
            break
            
    if not target_rec:
        target_rec = {
            "id": f"dispatch_global_{int(time.time())}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "video_file": video_basename,
            "title": EN_TITLE,
            "platforms": {}
        }
        history["records"].append(target_rec)
        
    target_rec["platforms"][platform_id] = {
        "status": "success",
        "real": True,
        "pub_id": pub_id,
        "link": link,
        "finish_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_history(history)

def dispatch_global_all():
    print("==================================================")
    print("🌐 开始国际主流平台批量分发（英文版短视频）")
    print(f"📹 目标文件: {os.path.basename(EN_VIDEO)}")
    print("==================================================")
    
    results = {}
    for platform in GLOBAL_PLATFORMS:
        if is_published(platform):
            print(f"⏭️ [{platform}] 已在历史记录中发布成功，跳过防重")
            results[platform] = "already_published"
            continue
            
        print(f"\n🚀 正在推送国际平台: [{platform}] ...")
        uploader = RealPlatformUploader(
            platform_id=platform,
            video_path=EN_VIDEO,
            title=EN_TITLE,
            desc=EN_DESC,
            tags=EN_TAGS
        )
        res = uploader.execute_upload()
        if res.get("success"):
            print(f"✅ [{platform}] 发布成功! ID: {res.get('pub_id')}")
            record_success(platform, res.get("pub_id"), res.get("link"))
            results[platform] = "success"
        else:
            print(f"❌ [{platform}] 发布失败: {res.get('error')}")
            results[platform] = "fail"
            
        time.sleep(2)

    print("\n==================================================")
    print("📋 国际平台分发汇总表:")
    for k, v in results.items():
        print(f"  - {k}: {v}")
    print("==================================================")

if __name__ == "__main__":
    dispatch_global_all()
