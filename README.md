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

## 💡 Core Philosophy (产品核心设计理念)

1. **免费打底 (Zero-Cost & Free-First)**：
   - 100% 开源免费 (MIT License)，绝不强制订阅，绝不强制购买大模型 API 密钥。
   - 原生整合免费网页端 AI Chatbot（豆包、Kimi、通义千问、ChatGPT），提供 1 键唤醒与 1 键剪贴板自动识别解析，让所有创作者零门槛享用 AI 赋能。
2. **极致便捷的聚合集成中枢 (Convenience Hub)**：
   - 打造一站式聚合中心：视频点选 + 模板/AI 创作 + 账号 Cookie 持久化 + 全网 14 平台并发分发。
3. **高阶智商弹性升级 (Elastic API Upgrade)**：
   - 为有更高自动化需求的高阶用户与 AI Agent 提供 API 密钥插槽，支持 DeepSeek、OpenAI、Claude、Ollama 等模型的全自动无感调用。

---

## 🌐 Online Web Live Demo (公网在线域名体验)

👉 **在线控制台访问地址**：[https://martin-mqtech.github.io/open-matrix-publisher/](https://martin-mqtech.github.io/open-matrix-publisher/)

无需提前 Clone 仓库，全球任何用户只需点击上述 GitHub Pages 域名链接，即可直接在浏览器中打开全域矩阵 15 平台中英双语控制台！

---

## 🖥️ Web Dashboard (GUI 可视化控制台)

Open Matrix Publisher 支持 **GitHub Pages 线上部署** 与 **本地一键拉起** 两种模式：

- **线上访问**：直接打开 [https://martin-mqtech.github.io/open-matrix-publisher/](https://martin-mqtech.github.io/open-matrix-publisher/)
- **本地一键启动**：运行 `./start_ui.sh` 自动调起 `http://localhost:5001`
- **核心功能**：中英双语模式选择、本地视频点选、15 平台网格状态实时校验、扫码登录弹窗与 🔒 防重历史 Ledger。

```bash
# 本地 1 秒一键启动 GUI
./start_ui.sh
```

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

## 🛠️ Manual Setup & Web UI Usage

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

### 3. Option A: Launch Web GUI Dashboard
```bash
./start_ui.sh
# Opens http://localhost:5001 automatically in your browser
```

### 4. Option B: CLI / Script Campaign
Scan QR code for one-time cookie setup:
```bash
python3 qr_login_manager.py
```
Then run campaign via CLI or config file:
```bash
python3 dispatch.py --config /path/to/your/campaign.json
```

---

## 📁 Project Structure

```
open-matrix-publisher/
├── index.html                   # Web GUI Dashboard frontend
├── start_ui.sh                  # 1-Click launcher script for Web UI
├── real_uploader_engine.py      # Core dispatch engine
├── interactive_login.py         # Headed browser QR login assistant
├── qr_login_manager.py          # One-time login & cookie saver
├── cookie_extractor.py          # Chrome cookie import utility
├── local_bridge_server.py       # Local HTTP bridge server (Port 5001)
├── dispatch.py                  # CLI dispatcher entry point
├── batch_dispatch_domestic.py   # Quick-run: CN platforms
├── batch_dispatch_global.py     # Quick-run: Global platforms
├── custom_uploaders/            # Per-platform upload adapters
│   ├── toutiao_uploader.py
│   ├── weibo_uploader.py
│   ├── zhihu_uploader.py
│   ├── facebook_uploader.py
│   └── ...
├── cookies/                     # Session storage (git-ignored)
├── examples/
│   └── campaign_template.json   # Template for your campaign
├── docs/                        # Architecture & strategy docs
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

- [x] Web dashboard (local UI) with 1-click launcher `./start_ui.sh`
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
