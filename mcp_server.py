import sys
import os
import json
import asyncio
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from real_uploader_engine import check_profile_logged_in, RealPlatformUploader
from url_downloader import download_remote_video, cleanup_temp_video

ALL_SUPPORTED_PLATFORMS = [
    {"id": "tencent", "name": "微信视频号", "region": "cn"},
    {"id": "douyin", "name": "抖音", "region": "cn"},
    {"id": "bilibili", "name": "B站", "region": "cn"},
    {"id": "kuaishou", "name": "快手", "region": "cn"},
    {"id": "weibo", "name": "微博", "region": "cn"},
    {"id": "toutiao", "name": "今日头条", "region": "cn"},
    {"id": "zhihu", "name": "知乎", "region": "cn"},
    {"id": "xiaohongshu", "name": "小红书", "region": "cn"},
    {"id": "baijiahao", "name": "百家号", "region": "cn"},
    {"id": "fanqie", "name": "番茄视频", "region": "cn"},
    {"id": "youtube", "name": "YouTube", "region": "global"},
    {"id": "facebook", "name": "Facebook", "region": "global"},
    {"id": "x", "name": "X (Twitter)", "region": "global"},
    {"id": "linkedin", "name": "LinkedIn", "region": "global"},
    {"id": "instagram", "name": "Instagram", "region": "global"},
    {"id": "tiktok", "name": "TikTok", "region": "global"},
    {"id": "devto", "name": "Dev.to", "region": "global"},
    {"id": "wordpress", "name": "WordPress", "region": "global"},
    {"id": "telegram", "name": "Telegram", "region": "global"}
]

def list_platforms() -> Dict[str, Any]:
    """Returns list of all 18 supported domestic and international platforms."""
    return {"platforms": ALL_SUPPORTED_PLATFORMS, "total": len(ALL_SUPPORTED_PLATFORMS)}

def check_accounts() -> Dict[str, Any]:
    """Check logged-in session status across all platforms."""
    results = {}
    for p in ALL_SUPPORTED_PLATFORMS:
        pid = p["id"]
        is_logged, msg = check_profile_logged_in(pid)
        results[pid] = {
            "name": p["name"],
            "region": p["region"],
            "logged_in": is_logged,
            "status_text": msg
        }
    return {"accounts": results}

async def publish_video_tool(platforms: List[str], video_file: str, title: str, desc: str, tags: List[str]) -> Dict[str, Any]:
    """
    Publish a local or remote video across specified platforms.
    """
    local_path, is_temp = download_remote_video(video_file)
    uploader = RealPlatformUploader()
    
    results = {}
    for pid in platforms:
        try:
            res = await uploader.upload_to_platform(
                platform_id=pid,
                video_file=local_path,
                title=title,
                desc=desc,
                tags=tags or []
            )
            results[pid] = res
        except Exception as e:
            results[pid] = {"status": "error", "message": str(e)}

    if is_temp:
        cleanup_temp_video(local_path)

    return {"status": "completed", "results": results}

def run_mcp_server():
    """Stdio JSON-RPC MCP Server loop."""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            req = json.loads(line.strip())
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "open-matrix-publisher",
                            "version": "2.0.0"
                        },
                        "capabilities": {
                            "tools": {}
                        }
                    }
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "list_supported_platforms",
                                "description": "列出 Open Matrix Publisher 支持的全部 16 大国内与海外平台列表",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {}
                                }
                            },
                            {
                                "name": "check_account_status",
                                "description": "检测所有平台的账号登录态与 Cookie 有效性",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {}
                                }
                            },
                            {
                                "name": "publish_video",
                                "description": "将视频（支持本地路径或远程 HTTP/HTTPS URL）批量分发至指定的国内与海外平台矩阵",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "platforms": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "目标平台ID列表（如 ['tencent', 'douyin', 'youtube', 'tiktok']）"
                                        },
                                        "video_file": {
                                            "type": "string",
                                            "description": "本地视频绝对路径 或 远程 HTTP/HTTPS 直链"
                                        },
                                        "title": {
                                            "type": "string",
                                            "description": "视频发布标题"
                                        },
                                        "desc": {
                                            "type": "string",
                                            "description": "视频正文描述"
                                        },
                                        "tags": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "标签列表"
                                        }
                                    },
                                    "required": ["platforms", "video_file", "title", "desc"]
                                }
                            }
                        ]
                    }
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})

                if tool_name == "list_supported_platforms":
                    res = list_platforms()
                elif tool_name == "check_account_status":
                    res = check_accounts()
                elif tool_name == "publish_video":
                    res = asyncio.run(publish_video_tool(
                        platforms=tool_args.get("platforms", []),
                        video_file=tool_args.get("video_file", ""),
                        title=tool_args.get("title", ""),
                        desc=tool_args.get("desc", ""),
                        tags=tool_args.get("tags", [])
                    ))
                else:
                    res = {"error": f"Unknown tool: {tool_name}"}

                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(res, ensure_ascii=False, indent=2)
                            }
                        ]
                    }
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                }

            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"[MCP Server Error] {e}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    run_mcp_server()
