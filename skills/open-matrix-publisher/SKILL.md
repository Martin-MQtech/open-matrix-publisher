---
name: open-matrix-publisher
description: Open Matrix Publisher (全域矩阵) 智能体发布技能。支持 16 大国内与海外主流视频与社交媒体平台（视频号、抖音、B站、快手、小红书、微博、头条、知乎、百家号、好看视频、YouTube、TikTok、Instagram、Facebook、X、LinkedIn）一键静默并发发布与账号状态检测。
---

# Open Matrix Publisher 智能体分发技能

本技能为智能体（Google Antigravity、DeepSeek Harness、Hermes Agent、Zed、Claude Code、Cursor）提供全网多渠道并发分发与状态查询能力（当前已接入 20 平台）。

## 核心能力
- **`publish_video`**：将本地或远程 HTTP/HTTPS 直链视频批量推送到指定的国内与海外平台矩阵。
- **`check_account_status`**：检查各平台的登录 Cookie 与账号授权有效性。
- **`list_supported_platforms`**：获取当前支持的平台列表与配置。

## 调用方式

### 方式 1：标准 MCP Server (Stdio)
```bash
python3 mcp_server.py
```

### 方式 2：REST Webhook API
```bash
curl -X POST http://localhost:5001/api/publish \
  -H "Content-Type: application/json" \
  -d '{"platforms":["tencent","douyin","youtube","tiktok"],"video_file":"/path/to/video.mp4","title":"标题","desc":"描述"}'
```
