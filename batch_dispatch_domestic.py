#!/usr/bin/env python3
"""
全平台国内批量分发脚本 v2 — 统一完整文案版
中文版：质感生活流（完整文案）
英文版：🔬 科研创新流 B2B（第2预设，完整文案）
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(__file__))
from real_uploader_engine import RealPlatformUploader

WORKSPACE = "/Users/martin/Desktop/Codex视频处理/20260806 富氢热灸贴双语视频"
CN_VIDEO  = os.path.join(WORKSPACE, "富氢热灸贴营销短视频_中文配音版_v1_成片.mp4")
EN_VIDEO  = os.path.join(WORKSPACE, "富氢热灸贴营销短视频_英文配音版_v1_成片.mp4")
HISTORY_FILE = os.path.join(WORKSPACE, "dispatch_history.json")

# ═══════════════════════════════════════════════════════════════
# 文案库 — 按平台做字数适配，确保完整不截断
# ═══════════════════════════════════════════════════════════════

# 通用长文描述（完整版）
CN_DESC_FULL = (
    "久坐电脑前、伏案低头后，让深层积攒的寒凉在温热中悄然消融。"
    "80×205mm 人体工学大贴幅，温柔贴合肩颈、腰背与关节，"
    "伴您度过一段温润安心的时光。"
    "科研探讨，仅供参考。官网：www.emuqi.com"
)

EN_DESC_FULL = (
    "氢分子渗透 × 远红外温感协同，专为久坐伏案人群研发。"
    "80×205mm 工学贴幅，精准覆盖颈椎、腰背、关节核心区域。"
    "木齐科技 | 支持 OEM/ODM 品牌定制开发。"
    "科研探讨，仅供参考。\n"
    "Hydrogen molecular diffusion × Far-infrared thermal synergy. "
    "Designed for desk workers. 80×205mm ergonomic patch. "
    "MUQI Tech | OEM/ODM Private Label | www.emuqi.com"
)

CN_TAGS = ["富氢热灸贴", "木齐科技", "温氢双护", "体感美学", "颈肩护理", "热灸贴"]
EN_TAGS = ["富氢热灸贴", "HydrogenPatch", "木齐科技", "OEM代工", "科研探讨", "氢健康", "PrivateLabel"]

# ───────────────────────────────────────────────────────────────
# 各平台文案规格（标题字数限制各不相同）
# 抖音≤55字  快手≤50字  小红书≤20字  视频号≤60字
# B站≤80字   微博≤140字  知乎≤100字  头条≤30字
# ───────────────────────────────────────────────────────────────
PLATFORM_SPECS = {
    # ── 中文版 ──────────────────────────────────────────────────
    "cn": {
        "douyin": {
            "title": "给身体做一场微风拂过的休憩｜木齐科技富氢热灸贴，温氢双护舒缓紧绷",
            "desc":  CN_DESC_FULL,
            "tags":  CN_TAGS,
        },
        "kuaishou": {
            "title": "【温氢双护】富氢热灸贴·木齐科技｜给肩颈腰背一段温润安心的时光",
            "desc":  CN_DESC_FULL,
            "tags":  CN_TAGS,
        },
        "xiaohongshu": {
            "title": "富氢热灸贴，温暖每一处紧绷",   # 小红书标题≤20字
            "desc":  (
                "久坐族、低头族的日常救星 🌿\n"
                "80×205mm 大贴幅，肩颈腰背一贴贴合\n"
                "温热 × 氢分子，两种能量同时守护\n"
                "木齐科技 | 科研探讨，仅供参考\n"
                "官网：www.emuqi.com"
            ),
            "tags":  ["富氢热灸贴", "木齐科技", "颈肩护理", "热灸贴", "温氢双护"],
        },
        "tencent": {
            "title": "【给身体做一场微风拂过的休憩】木齐科技富氢热灸贴·温氢双护",
            "desc":  CN_DESC_FULL,
            "tags":  CN_TAGS,
        },
        "bilibili": {
            "title": "【木齐科技】富氢热灸贴开箱体验｜80×205mm 大贴幅，温氢双护肩颈腰背",
            "desc":  CN_DESC_FULL + "\n\n本视频为产品展示，科研探讨，仅供参考。",
            "tags":  CN_TAGS + ["开箱体验", "健康好物"],
        },
        "weibo": {
            "title": "【富氢热灸贴｜木齐科技】给身体做一场微风拂过的休憩，温氢双护日常紧绷",
            "desc":  CN_DESC_FULL,
            "tags":  CN_TAGS,
        },
        "zhihu": {
            "title": "木齐科技富氢热灸贴体验分享：氢分子+远红外温感，肩颈腰背的日常守护",
            "desc":  CN_DESC_FULL,
            "tags":  CN_TAGS,
        },
        "toutiao": {
            "title": "富氢热灸贴，温暖肩颈腰背",   # 头条≤30字
            "desc":  CN_DESC_FULL,
            "tags":  CN_TAGS,
        },
    },

    # ── 英文版（科研创新流 B2B·第2预设）────────────────────────
    "en": {
        "douyin": {
            "title": "氢能×热能双效｜木齐科技富氢热灸贴科研探讨版（中英双语）",
            "desc":  EN_DESC_FULL,
            "tags":  EN_TAGS,
        },
        "kuaishou": {
            "title": "【科研创新】富氢热灸贴·木齐科技 OEM｜氢分子×远红外温感协同（双语版）",
            "desc":  EN_DESC_FULL,
            "tags":  EN_TAGS,
        },
        "xiaohongshu": {
            "title": "双语｜富氢热灸贴科研体验",
            "desc":  (
                "Hydrogen × Far-infrared thermal patch 🔬\n"
                "氢分子渗透 × 远红外温感协同\n"
                "80×205mm 人体工学贴幅\n"
                "木齐科技 | OEM/ODM | www.emuqi.com\n"
                "科研探讨，仅供参考。"
            ),
            "tags":  ["富氢热灸贴", "HydrogenPatch", "木齐科技", "科研探讨", "OEM代工"],
        },
        "tencent": {
            "title": "【氢能×热能｜双语科研版】木齐科技富氢热灸贴·OEM/ODM 品牌定制",
            "desc":  EN_DESC_FULL,
            "tags":  EN_TAGS,
        },
        "bilibili": {
            "title": "【双语科研版】木齐科技富氢热灸贴｜Hydrogen Patch OEM开发展示",
            "desc":  EN_DESC_FULL + "\n\n科研探讨，仅供参考。",
            "tags":  EN_TAGS + ["双语视频", "OEM开发"],
        },
        "weibo": {
            "title": "【双语版】木齐科技富氢热灸贴·科研探讨｜氢分子×远红外协同，OEM/ODM",
            "desc":  EN_DESC_FULL,
            "tags":  EN_TAGS,
        },
        "zhihu": {
            "title": "木齐科技富氢热灸贴（双语科研版）：氢分子×远红外协同的理论探讨与产品展示",
            "desc":  EN_DESC_FULL,
            "tags":  EN_TAGS,
        },
        "toutiao": {
            "title": "双语｜富氢热灸贴科研展示",
            "desc":  EN_DESC_FULL,
            "tags":  EN_TAGS,
        },
    }
}

# 发布顺序（B站需真终端放最后，避免影响其他）
DISPATCH_ORDER = ["douyin", "kuaishou", "xiaohongshu", "tencent", "weibo", "zhihu", "toutiao", "bilibili"]

# ═══════════════════════════════════════════════════════════════
# 防重复 & 历史记录
# ═══════════════════════════════════════════════════════════════
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"records": [], "last_dispatch": {}}

def is_published(video_basename, platform_id):
    for rec in load_history().get("records", []):
        if os.path.basename(rec.get("video_file","")) == video_basename:
            p = rec.get("platforms", {}).get(platform_id, {})
            if p.get("status") == "success" and p.get("real"):
                return True, p.get("finish_time","")
    return False, ""

def mark_success(video_basename, platform_id, pub_id, link):
    hist = load_history()
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    rec = next((r for r in hist["records"]
                if os.path.basename(r.get("video_file","")) == video_basename), None)
    if rec is None:
        rec = {"video_file": video_basename, "timestamp": t, "platforms": {}}
        hist["records"].append(rec)
    rec["platforms"][platform_id] = {"status":"success","real":True,
                                     "pub_id":pub_id,"link":link,"finish_time":t}
    with open(HISTORY_FILE,"w") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════
# 核心发布逻辑
# ═══════════════════════════════════════════════════════════════
def dispatch_one(video_path, version_key, platform_id):
    """version_key: 'cn' or 'en'"""
    spec = PLATFORM_SPECS[version_key][platform_id]
    video_basename = os.path.basename(video_path)
    label = "中文版" if version_key == "cn" else "英文版"

    done, when = is_published(video_basename, platform_id)
    if done:
        print(f"  ⏭️  [{label}] {platform_id} → 已于 {when} 发布，跳过")
        return "skipped"

    print(f"\n  🚀 [{label}] {platform_id}")
    print(f"     标题: {spec['title']}")
    print(f"     描述: {spec['desc'][:60]}...")
    print(f"     标签: {','.join(spec['tags'][:4])}")

    uploader = RealPlatformUploader(
        platform_id=platform_id,
        video_path=video_path,
        title=spec["title"],
        desc=spec["desc"],
        tags=spec["tags"]
    )
    result = uploader.execute_upload()
    if result.get("success"):
        mark_success(video_basename, platform_id, result.get("pub_id",""), result.get("link",""))
        print(f"  ✅ [{label}] {platform_id} → 成功！")
        return "success"
    else:
        print(f"  ❌ [{label}] {platform_id} → {result.get('error','')[:150]}")
        return "fail"

# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════
def main():
    print("\n" + "="*65)
    print("🎬 全平台国内批量分发 v2 — 木齐科技富氢热灸贴")
    print("   中文版（质感生活流）+ 英文版（🔬 科研创新流 B2B）")
    print("="*65)

    results = {"cn":{}, "en":{}}

    for version_key, video_path, label in [
        ("cn", CN_VIDEO, "中文配音版 · 质感生活流"),
        ("en", EN_VIDEO, "英文配音版 · 科研创新流B2B（第2预设）"),
    ]:
        print(f"\n{'─'*50}")
        print(f"📀 {label}")
        print(f"{'─'*50}")
        for pid in DISPATCH_ORDER:
            r = dispatch_one(video_path, version_key, pid)
            results[version_key][pid] = r
            if r not in ("skipped",):
                time.sleep(3)  # 平台间间隔

    # 汇总
    print("\n" + "="*65)
    print("📊 发布汇总")
    print("="*65)
    for ver, vr in [("中文版", results["cn"]), ("英文版", results["en"])]:
        s = [p for p,r in vr.items() if r=="success"]
        sk= [p for p,r in vr.items() if r=="skipped"]
        f = [p for p,r in vr.items() if r=="fail"]
        print(f"\n  {ver}:")
        if s:  print(f"    ✅ 成功: {', '.join(s)}")
        if sk: print(f"    ⏭️  已发/跳过: {', '.join(sk)}")
        if f:  print(f"    ❌ 失败（需扫码/重试）: {', '.join(f)}")
    print()

if __name__ == "__main__":
    main()
