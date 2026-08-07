import os, sys, json
import browser_cookie3

DOMAINS_MAP = {
    "sph": ["weixin.qq.com", "qq.com"],
    "douyin": ["douyin.com", "bytedance.com"],
    "xhs": ["xiaohongshu.com"],
    "kuaishou": ["kuaishou.com"],
    "bilibili": ["bilibili.com"],
    "weibo": ["weibo.com", "weibo.cn"],
    "haokan": ["baidu.com"],
    "xigua": ["toutiao.com", "ixigua.com"]
}

def sync_cookies_from_chrome(platform_id):
    domains = DOMAINS_MAP.get(platform_id, [])
    all_cookies = []

    profile_dir = os.path.expanduser(f"~/.config/codex_video_dispatch/chromium_profiles/{platform_id}")
    os.makedirs(profile_dir, exist_ok=True)
    state_file = os.path.join(profile_dir, "state.json")

    for domain in domains:
        try:
            cj = browser_cookie3.chrome(domain_name=domain)
            for c in cj:
                all_cookies.append({
                    "name": str(c.name),
                    "value": str(c.value),
                    "domain": str(c.domain),
                    "path": str(c.path),
                    "expires": float(c.expires) if c.expires else -1.0,
                    "httpOnly": False,
                    "secure": bool(c.secure),
                    "sameSite": "Lax"
                })
        except Exception as e:
            print(f"提取 {domain} Cookie 时提示: {e}")

    if all_cookies:
        state_data = {
            "cookies": all_cookies,
            "origins": []
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)
        print(f"✅ 成功从 Mac Chrome 自动提取 {len(all_cookies)} 条凭证，写入 {state_file}")
        return True, len(all_cookies)

    return False, 0

def sync_all_platforms():
    summary = {}
    for pid in DOMAINS_MAP:
        ok, count = sync_cookies_from_chrome(pid)
        summary[pid] = {"success": ok, "count": count}
    return summary

if __name__ == "__main__":
    res = sync_all_platforms()
    print("全局 Cookie 自动同步结果:", json.dumps(res, indent=2, ensure_ascii=False))
