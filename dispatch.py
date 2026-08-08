#!/usr/bin/env python3
"""
Open Matrix Publisher — CLI Dispatcher
=======================================
统一命令行入口。任何视频项目只需提供一个 campaign.json 配置文件，
调用此脚本即可完成全平台分发。

用法：
    python3 dispatch.py --config /path/to/campaign.json
    python3 dispatch.py --config /path/to/campaign.json --platforms douyin xiaohongshu
    python3 dispatch.py --config /path/to/campaign.json --dry-run

campaign.json 格式参见 examples/campaign_template.json
"""
import argparse
import json
import os
import sys
import time
import subprocess
from datetime import datetime

# 让脚本从任意位置调用都能找到引擎
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOL_DIR)

from real_uploader_engine import RealPlatformUploader


# ─── 安全锁：防止多条分发链路并行运行 ──────────────────────────────────────────
LOCKFILE = os.path.join(TOOL_DIR, ".dispatch.lock")

def acquire_lock():
    """
    写入进程锁文件。若锁文件已存在且进程仍在运行，拒绝启动。
    这是防止重复发布的第一道代码层防线。
    """
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, "r") as f:
                old_pid = int(f.read().strip())
            # 检查该 PID 是否仍在运行
            os.kill(old_pid, 0)
            # 能走到这里说明进程还活着
            print(f"\n{'='*60}")
            print(f"  ⛔  [安全中止] 检测到另一条分发进程仍在运行 (PID {old_pid})")
            print(f"  执行铁律：严禁并行启动多条分发链路。")
            print(f"  如确认该进程已死亡，请手动删除锁文件后重试：")
            print(f"  rm {LOCKFILE}")
            print(f"{'='*60}\n")
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            # 旧进程已死亡，锁文件是残留，清理它
            os.remove(LOCKFILE)

    with open(LOCKFILE, "w") as f:
        f.write(str(os.getpid()))

def release_lock():
    if os.path.exists(LOCKFILE):
        try:
            os.remove(LOCKFILE)
        except Exception:
            pass


# ─── 所有支持的平台 ─────────────────────────────────────────────────────────
ALL_DOMESTIC  = ["douyin", "kuaishou", "xiaohongshu", "bilibili", "tencent", "weibo", "zhihu", "toutiao"]
ALL_GLOBAL    = ["youtube", "tiktok", "x", "linkedin", "facebook", "instagram"]
ALL_PLATFORMS = ALL_DOMESTIC + ALL_GLOBAL


def load_campaign(config_path: str) -> dict:
    """加载并校验 campaign.json"""
    if not os.path.exists(config_path):
        print(f"[ERROR] 找不到配置文件: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 校验必填字段
    required = ["campaign_name", "tasks"]
    for key in required:
        if key not in cfg:
            print(f"[ERROR] campaign.json 缺少必填字段: '{key}'")
            sys.exit(1)

    return cfg


def load_history(history_file: str) -> dict:
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(history_file: str, history: dict):
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def make_history_key(video_path: str, platform: str) -> str:
    return f"{os.path.basename(video_path)}::{platform}"


def run_campaign(cfg: dict, filter_platforms: list = None, dry_run: bool = False):
    """执行分发活动"""
    campaign_name = cfg["campaign_name"]
    history_file  = cfg.get("history_file", os.path.join(TOOL_DIR, f"dispatch_history_{campaign_name}.json"))
    history = load_history(history_file)

    print(f"\n{'='*60}")
    print(f"  Open Matrix Publisher — {campaign_name}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if dry_run:
        print(f"  ⚠️  DRY-RUN 模式：不实际发布")
    print(f"{'='*60}\n")

    results = {}

    # ── 防重预检：发布前强制打印全局状态报告 ──────────────────────────────
    print("  【防重预检报告】")
    print(f"  {'平台':<16}  {'视频':<30}  状态")
    print(f"  {'-'*70}")
    for task in cfg["tasks"]:
        vname = os.path.basename(task["video"])
        task_platforms = task.get("platforms", ALL_PLATFORMS)
        if filter_platforms:
            task_platforms = [p for p in task_platforms if p in filter_platforms]
        for platform in task_platforms:
            key = make_history_key(task["video"], platform)
            if key in history and history[key].get("status") == "success":
                print(f"  {platform:<16}  {vname:<30}  🔒 已锁定（绝不重发）")
            else:
                rec_status = history.get(key, {}).get("status", "—")
                print(f"  {platform:<16}  {vname:<30}  🚀 待发布（上次: {rec_status}）")
    print(f"  {'-'*70}")
    print("  预检完毕，5 秒后开始发布...\n")
    import time as _t; _t.sleep(5)
    # ──────────────────────────────────────────────────────────────────────

    for task in cfg["tasks"]:
        video_path = task["video"]
        title      = task["title"]
        desc       = task["desc"]
        tags       = task.get("tags", [])
        platforms  = task.get("platforms", ALL_PLATFORMS)

        # 应用命令行平台过滤
        if filter_platforms:
            platforms = [p for p in platforms if p in filter_platforms]

        if not os.path.exists(video_path):
            print(f"[SKIP] 视频文件不存在: {video_path}")
            continue

        print(f"[视频] {os.path.basename(video_path)}")
        print(f"[标题] {title[:40]}...")
        print(f"[平台] {', '.join(platforms)}\n")

        for platform in platforms:
            key = make_history_key(video_path, platform)

            # 防重检查
            if key in history and history[key].get("status") == "success":
                print(f"  [{platform:16s}] ⏭  已发布，跳过")
                results[f"{platform}/{os.path.basename(video_path)}"] = "skipped"
                continue

            if dry_run:
                print(f"  [{platform:16s}] 🔍 DRY-RUN — 将调用 RealPlatformUploader")
                results[f"{platform}/{os.path.basename(video_path)}"] = "dry-run"
                continue

            # 执行分发
            try:
                uploader = RealPlatformUploader(
                    platform_id=platform,
                    video_path=video_path,
                    title=title,
                    desc=desc,
                    tags=tags
                )
                result = uploader.execute_upload()
                ok = result.get("success", False)

                status_icon = "✅" if ok else "❌"
                print(f"  [{platform:16s}] {status_icon} {'成功' if ok else result.get('error', '失败')}")

                history[key] = {
                    "status":    "success" if ok else "fail",
                    "platform":  platform,
                    "video":     os.path.basename(video_path),
                    "timestamp": datetime.now().isoformat(),
                    "detail":    result
                }
                results[f"{platform}/{os.path.basename(video_path)}"] = "ok" if ok else "fail"

            except Exception as e:
                print(f"  [{platform:16s}] ❌ 异常: {e}")
                history[key] = {
                    "status": "error", "platform": platform,
                    "video": os.path.basename(video_path),
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                }
                results[f"{platform}/{os.path.basename(video_path)}"] = "error"

            save_history(history_file, history)
            time.sleep(2)  # 平台间间隔，避免触发风控

        print()

    # 汇总
    print(f"\n{'='*60}")
    print("  分发结果汇总")
    print(f"{'='*60}")
    success = sum(1 for v in results.values() if v == "ok")
    skipped = sum(1 for v in results.values() if v == "skipped")
    failed  = sum(1 for v in results.values() if v in ("fail", "error"))
    print(f"  ✅ 成功: {success}  ⏭ 跳过: {skipped}  ❌ 失败: {failed}")
    print(f"  历史记录: {history_file}\n")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Open Matrix Publisher — 全域矩阵 CLI 分发入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 dispatch.py --config ~/my_project/campaign.json
  python3 dispatch.py --config ~/my_project/campaign.json --platforms douyin xiaohongshu
  python3 dispatch.py --config ~/my_project/campaign.json --dry-run
        """
    )
    parser.add_argument("--config",    required=False, help="campaign.json 文件路径")
    parser.add_argument("--platforms", nargs="+",      help="只发布到指定平台（空格分隔）")
    parser.add_argument("--dry-run",   action="store_true", help="演练模式，不实际发布")
    parser.add_argument("--list-platforms", action="store_true", help="列出所有支持的平台")

    args = parser.parse_args()

    if args.list_platforms:
        print("国内平台:", ", ".join(ALL_DOMESTIC))
        print("国际平台:", ", ".join(ALL_GLOBAL))
        return

    if not args.config:
        parser.error("请提供 --config 参数，或使用 --list-platforms 查看支持的平台")

    cfg = load_campaign(os.path.expanduser(args.config))

    if args.dry_run:
        # 演练模式无需锁
        run_campaign(cfg, filter_platforms=args.platforms, dry_run=True)
        return

    # ── 获取进程锁（防止并行重复分发）──
    acquire_lock()
    try:
        run_campaign(cfg, filter_platforms=args.platforms, dry_run=False)
    finally:
        release_lock()

    # ── 铁律三：强制人工确认提示 ──
    print("\n" + "⚠️ " * 20)
    print("  【人工确认提醒】")
    print("  脚本已执行完毕，但「脚本成功」≠「视频已上线」。")
    print("  请登录以下平台的创作者后台，逐一确认视频状态：")
    print("  抖音: https://creator.douyin.com  |  小红书: https://creator.xiaohongshu.com")
    print("  B站: https://member.bilibili.com  |  微博: https://weibo.com/upload/channel")
    print("  YouTube: https://studio.youtube.com  |  TikTok: https://creator.tiktok.com")
    print("  LinkedIn: https://www.linkedin.com/video  |  X: https://twitter.com")
    print("  确认后，本次发布流程才算完成。")
    print("⚠️ " * 20 + "\n")


if __name__ == "__main__":
    main()
