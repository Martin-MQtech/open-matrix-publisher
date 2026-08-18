<p align="center">
  <img src="logo.png" alt="Open Matrix Publisher" width="104">
</p>

# 🌐 Open Matrix Publisher (全域矩阵)

> **专为传统国际贸易、跨境电商与出海品牌打造的 AI 原生全域社媒分发与营销中枢。**  
> 一套资产，中英双语，一键分发到 16 个平台 · 🇨🇳 国内 10 大平台 · 🌏 国际 6 大平台。100% 本地运行、免注册、开源免费。

[![GitHub Stars](https://img.shields.io/github/stars/Martin-MQtech/open-matrix-publisher?style=social)](https://github.com/Martin-MQtech/open-matrix-publisher)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://python.org)
[![MCP Ready](https://img.shields.io/badge/MCP-Protocol%20Ready-00e6ff)](https://modelcontextprotocol.io)

**核心流程演示（约 15 秒）**：选视频 → 写文案 → 勾选平台 → 一键发布。

<p align="center">
  <img src="media/demo-flow.gif" alt="Open Matrix Publisher 核心流程演示：选视频→写文案→勾选平台→一键发布" width="720">
</p>

---

## 🎯 核心定位与服务人群 (Target Persona & Mission)

Open Matrix Publisher 旨在打破国内外割裂的自媒体营销现状，为以下核心人群提供**零成本、高并发、中英双语、本地安全**的一站式全网营销中枢：

1. **🏭 传统国际贸易企业 (B2B Exporters & OEM/ODM Factories)**：
   - 痛点：拥有优质制造能力与发明专利，但缺乏海外社媒获客渠道。
   - 赋能：一键将工厂实拍、生产车间、研发质检视频分发至 **LinkedIn、YouTube、X (Twitter)、微信视频号、知乎**，大宗外贸询盘直达。
2. **🛍️ 跨境电商卖家与出海 DTC 品牌 (Cross-Border Sellers / Amazon / TikTok Shop / TEMU / Shopify)**：
   - 痛点：多平台铺货与社媒种草成本高，海外工具（Buffer/Hootsuite）极其昂贵且不支持国内平台。
   - 赋能：一键同步视频至 **TikTok、Instagram Reels、Facebook、抖音、小红书**，实现全网裂变种草。
3. **🌍 全球化出海项目与多语种创作者 (Global Marketing Projects & Independent Creators)**：
   - 痛点：中英双语内容流转繁琐，跨国平台风控与登录态管理困难。
   - 赋能：零 API 成本免费 AI 网页连通器（豆包/Kimi）自动生成地道文案，Playwright 真实浏览器指纹隔离，安全防封。

---

## 🌐 16 平台分发矩阵 (16-Platform Matrix)

> 登录方式一站式：控制台平台卡片点「扫码登录/刷新」→ 弹出登录窗口 → Cookie 自动落盘本地 `cookies/`，之后全部静默复用，无需重复登录。

### 🇨🇳 国内阵列（10 平台 · 全部已接入）

| 平台 | 引擎 | 登录方式 | 验证状态 |
| :--- | :--- | :--- | :--- |
| 视频号 | SAU 引擎 | 微信扫码 | ✅ 已接入 |
| 抖音 | SAU 引擎 | 扫码 | ✅ 已接入 |
| B站 | SAU 引擎 | 扫码 (biliup) | ✅ 已接入 |
| 快手 | SAU 引擎 | 扫码 | ✅ 已接入 |
| 小红书 | SAU 引擎 | 扫码 | ✅ 已接入 |
| 微博 | 自定义适配器 | 账号密码 | ✅ 已接入 |
| 今日头条 | 自定义适配器 | 账号密码 | ✅ 已接入 |
| 知乎 | 自定义适配器 | 扫码 | ✅ 已接入 |
| 百家号 | 自定义适配器 | 扫码 ¹ | ✅ 已接入 |
| 番茄视频 | 自定义适配器 | 扫码 ¹ | ✅ 已接入 |

### 🌏 海外阵列（6 平台 · 2 已接入 + 4 端到端验证中）

| 平台 | 引擎 | 登录方式 | 验证状态 |
| :--- | :--- | :--- | :--- |
| YouTube | SAU 引擎 | Google 账号 | ✅ 已接入 |
| Facebook | 自定义适配器 | 账号密码 | ✅ 已接入 |
| TikTok | 自定义适配器 | 扫码 / Google / Apple | 🧪 端到端验证中 |
| Instagram | 自定义适配器 | 账号密码 | 🧪 端到端验证中 |
| X (Twitter) | 自定义适配器 | 账号密码 / Google | 🧪 端到端验证中 |
| LinkedIn | 自定义适配器 | 账号密码 | 🧪 端到端验证中 |

> ¹ 百家号 / 番茄视频的上传适配器已就绪，但控制台「扫码登录」入口尚未接入：需先在平台官网手动登录，再把 Cookie 放入本地 `cookies/`（后续版本补齐 UI 登录入口）。其余 14 个平台均可直接点控制台卡片一键登录。

---

## 🤖 全球主流 AI 智能体编排生态 (Multi-Agent Harness Hub)

本项目不仅提供现代化 Web 控制台，更作为 **AI 时代的基础设施**，原生深度适配全球主流自主智能体架构：

- **Google Antigravity (AGY Jump)**：原生 Skill 规范支持（`skills/open-matrix-publisher/SKILL.md`），多 Agent 协同直接调度。
- **DeepSeek Harness**：标准 Function Calling Tools Schema 驱动。
- **Nous Hermes Agent**：`<!-- hermes-integrable argv-marker=cli -->` 标记，CLI 管道极速编排。
- **Zed / Z-Code Harness**：Zed Context Servers 原生 MCP 扩展。
- **Claude Code & Cursor**：内置标准 MCP Server（`mcp_server.py`），对话中一句话触发全网分发。
- **Dify / n8n / 扣子 Coze**：开放标准 REST Webhook（`POST /api/publish`）。

---

## 💡 核心设计哲学 (Core Philosophy)

1. **免费打底 (Zero-Cost & Free-First)**：
   - 100% 开源免费 (MIT License)，绝无隐藏订阅费。
   - 原生整合免 API 费用的豆包与 Kimi 智能连通器，提示词净化清洗，剪贴板秒级提取。
2. **极速全源输入 (Universal Video Pipeline)**：
   - 同时支持**本地视频文件**与**远程 HTTP/HTTPS 直链（OSS/COS/CDN/云端剪辑）**，自动流式拉取、校验、上传并清理缓存。
3. **真实指纹与防重锁安全 (Anti-Detection & History Ledger)**：
   - Patchright 底层 CDP 去除自动化特征，真实 Cookie 存储，历史 Ledger 严防重复撞车发布。

---

## 🖥️ 访问与使用方式

### 1. 界面预览 (Static Preview)
👉 在浏览器直接预览界面：[https://martin-mqtech.github.io/open-matrix-publisher/](https://martin-mqtech.github.io/open-matrix-publisher/)
> 注意：该页面仅展示静态界面，**发布功能需要在本机运行**（见下方「下载安装与本地运行」）；视频与 Cookie 始终留在本地。

### 2. 下载安装与本地运行

> 工具**完全在本地运行**：视频、Cookie、登录凭证都不离开你的电脑，免注册即可使用。

**前置要求**：macOS / Linux · Python 3.10+ · git。（SAU 引擎首次缺失时，`./start_ui.sh` 会自动检测并引导一键安装，也可参照 [SAU 官方安装说明](https://github.com/dreammis/social-auto-upload/blob/main/docs/install.md) 手动安装。）

**第 1 步 · 获取代码**
```bash
git clone https://github.com/Martin-MQtech/open-matrix-publisher.git
cd open-matrix-publisher
```

**第 2 步 · 启动控制台**
```bash
./start_ui.sh
# 浏览器将自动打开 http://localhost:5001
```
> `start_ui.sh` 定位 SAU 引擎的优先级：① 环境变量 `SAU_ROOT`（显式指定，如 `SAU_ROOT=/path/to/sau ./start_ui.sh`）→ ② 常见路径自动检测（`~/social-auto-upload`、仓库同级目录等）→ ③ 交互终端一键安装引导（clone + venv + 依赖 + 浏览器）。可先执行 `./start_ui.sh --check` 查看环境检测结果。

**第 3 步 · 首次扫码登录（每个平台只需一次）**
在控制台平台卡片点「扫码登录/刷新」，按提示扫码；Cookie 仅保存在本地 `cookies/` 目录，后续所有分发复用，无需重复登录。

> **Windows 用户**：下载仓库后**双击 `start_ui.bat`** 即可（自动调用 PowerShell 启动器）。首次运行会自动检测 SAU（`%USERPROFILE%\social-auto-upload` 等位置），未安装时交互引导一键安装；也可在 PowerShell 里运行 `\start_ui.ps1 -Check` 先查看环境检测结果。

### 3. MCP 智能体模式配置 (Claude Desktop / Cursor)
```json
{
  "mcpServers": {
    "open-matrix-publisher": {
      "command": "python3",
      "args": ["/path/to/open-matrix-publisher/mcp_server.py"]
    }
  }
}
```

---

## 📄 开源许可证

本项目遵循 [MIT License](LICENSE) 开源协议。
源自 **木齐科技 (MQ Tech · [www.emuqi.com](https://www.emuqi.com))** 真实出海与企业营销实战孵化。

> 🔒 发布前请按 [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) 逐项验收（敏感文件核对、素材、口径、push 清单）。
