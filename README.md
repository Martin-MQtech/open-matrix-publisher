# 🌐 Open Matrix Publisher (全域矩阵)

> **An open-source, AI-native, cross-platform video distribution engine.**  
> Dispatch a single video to 10+ platforms — silently, in the background, zero front-end interruption.

[![GitHub Stars](https://img.shields.io/github/stars/Martin-MQtech/open-matrix-publisher?style=social)](https://github.com/Martin-MQtech/open-matrix-publisher)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://python.org)

---

## ✨ What It Does

| Platform Tier | Platforms |
|---|---|
| 🇨🇳 Domestic | 抖音 · 小红书 · 微博 · B站 · 视频号 · 今日头条 |
| 🌏 Global | YouTube · TikTok · X (Twitter) · LinkedIn · Facebook · Instagram |

**One command → simultaneous dispatch to all platforms. No manual copy-paste. No repeated logins.**

---

## 🚀 AI-Native QuickStart (Zero Learning Curve)

> **If you're new to command-line tools or environment setup — skip all of it.**

Copy the repo link below and hand it directly to any AI Agent you're already using:

```
https://github.com/Martin-MQtech/open-matrix-publisher.git
```

Then say:

> **"Please clone this open-source project, install its dependencies, configure the environment, and help me distribute the video files in my folder to Douyin and Xiaohongshu."**

Compatible AI Agents: **Codex · Claude Code · Google Antigravity · 腾讯 Workbuddy · Open Code · Mimo Code** — and any agent with filesystem + shell access.

The agent will handle: cloning, `pip install`, cookie login, and background dispatch — automatically.

---

## 🛠️ Manual Setup (Developer)

### 1. Clone
```bash
git clone https://github.com/Martin-MQtech/open-matrix-publisher.git
cd open-matrix-publisher
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Login & Save Cookies
```bash
python3 qr_login_manager.py
```
Scan the QR code for each platform once. Sessions are saved to `cookies/` and reused silently on every subsequent run.

### 4. Run a Campaign
Copy `examples/my_campaign.py`, edit the `CONFIG` section with your video path and copy, then:
```bash
python3 examples/my_campaign.py
```

---

## 📁 Project Structure

```
open-matrix-publisher/
├── real_uploader_engine.py      # Core dispatch engine
├── qr_login_manager.py          # One-time login & cookie saver
├── cookie_extractor.py          # Chrome cookie import utility
├── local_bridge_server.py       # Local HTTP bridge server
├── multi_platform_dispatcher_v2.py  # High-level dispatcher
├── batch_dispatch_domestic.py   # Quick-run: CN platforms
├── batch_dispatch_global.py     # Quick-run: Global platforms
├── open_matrix_publisher/       # Python package
│   ├── __init__.py
│   └── core.py
├── custom_uploaders/            # Per-platform upload adapters
│   ├── tiktok_adapter.py
│   ├── x_uploader.py
│   ├── linkedin_uploader.py
│   ├── facebook_uploader.py
│   ├── instagram_uploader.py
│   ├── weibo_uploader.py
│   ├── zhihu_uploader.py
│   └── toutiao_uploader.py
├── cookies/                     # Session storage (git-ignored)
├── examples/
│   └── my_campaign.py          # Template for your own campaign
├── docs/                        # Architecture & strategy docs
├── platform_credentials.template.json
├── requirements.txt
└── .gitignore
```

---

## 🔒 Security & Privacy

- **Cookies are stored locally** in the `cookies/` directory and **never committed to git** (enforced by `.gitignore`)
- **No credentials in source code** — all sensitive data lives in `cookies/` or `.env`
- **Headless background execution** — after initial QR login, all dispatch runs silently with no browser window
- See [`docs/SECURITY_AND_PRIVACY_GUIDE.md`](docs/SECURITY_AND_PRIVACY_GUIDE.md) for the full security architecture

---

## ⚙️ Architecture: Non-Intrusive Background Dispatch

```
[One-time setup]  QR Login → cookie saved to cookies/
                      ↓
[Every run]       Load cookie → headless browser → platform API/UI
                      ↓
                  Upload in background → log result → exit
```

The user's foreground browser and work are never interrupted after initial setup.  
See [`docs/ADVANCED_AUTOMATION_ARCHITECTURE.md`](docs/ADVANCED_AUTOMATION_ARCHITECTURE.md) for the full four-tier hybrid driver architecture (Playwright → Patchright → CDP → Official API).

---

## 🗺️ Roadmap

- [ ] Web dashboard (local) for drag-and-drop dispatch
- [ ] Scheduled / recurring dispatch (cron)
- [ ] OAuth official API integrations (YouTube, LinkedIn)
- [ ] Plugin system for custom uploaders
- [ ] Windows & Linux support

---

## 🤝 Contributing

This project is open-source under the MIT License. PRs, issues, and stars are all welcome.

**Star the repo** if this saves you time. Share it with a creator friend.

---

## 👤 Author

**Martin · MQ Tech** | [@Martin-MQtech](https://github.com/Martin-MQtech)  
Builder · Strategist · Cross-border Content Creator  
[www.emuqi.com](https://www.emuqi.com)
