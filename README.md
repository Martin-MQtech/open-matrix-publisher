# 🌐 Open Matrix Publisher (全域矩阵)

> **专为传统国际贸易、跨境电商与出海品牌打造的 AI 原生全域社媒分发与营销中枢。**  
> 一套资产，中英双语，全网 28 平台静默并发分发 · 🇨🇳 国内 10 大平台做深做透 · 🌏 国际 18 大主流平台收割全球红利。

[![GitHub Stars](https://img.shields.io/github/stars/Martin-MQtech/open-matrix-publisher?style=social)](https://github.com/Martin-MQtech/open-matrix-publisher)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://python.org)
[![MCP Ready](https://img.shields.io/badge/MCP-Protocol%20Ready-00e6ff)](https://modelcontextprotocol.io)

---

## 🎯 核心定位与服务人群 (Target Persona & Mission)

Open Matrix Publisher 旨在打破国内外割裂的自媒体营销现状，为以下核心人群提供**零成本、高并发、中英双语、本地安全**的一站式全网营销中枢：

1. **🏭 传统国际贸易企业 (B2B Exporters & OEM/ODM Factories)**：
   - 痛点：拥有优质制造能力与发明专利，但缺乏海外社媒获客渠道。
   - 赋能：一键将工厂实拍、生产车间、研发质检视频分发至 **LinkedIn、YouTube、X (Twitter)、微信视频号、知乎**，大宗外贸询盘直达。
2. **🛍️ 跨境电商卖家与出海 DTC 品牌 (Cross-Border Sellers / Amazon / TikTok Shop / TEMU / Shopify)**：
   - 痛点：多平台铺货与社媒种草成本高，海外工具（Buffer/Hootsuite）极其昂贵且不支持国内平台。
   - 赋能：一键同步视频至 **TikTok、Instagram Reels、Pinterest (采购神器)、Snapchat、Facebook、抖音、小红书**，实现全网裂变种草。
3. **🌍 全球化出海项目与多语种创作者 (Global Marketing Projects & Independent Creators)**：
   - 痛点：中英双语内容流转繁琐，跨国平台风控与登录态管理困难。
   - 赋能：零 API 成本免费 AI 网页连通器（豆包/Kimi）自动生成地道文案，Playwright 真实浏览器指纹隔离，安全防封。

---

## 🌐 28 平台全球超级矩阵全景 (28-Platform Matrix)

| 分区 | 平台数量 | 覆盖平台名单 | 核心商业获客场景 |
| :--- | :--- | :--- | :--- |
| **🇨🇳 国内阵列** | **10 大平台** | 微信视频号 · 抖音 · 哔哩哔哩 (B站) · 快手 · 小红书 · 微博 · 今日头条 · 知乎 · 百家号 · 番茄视频 | 搜索 SEO · 私域公域联动 · 内循环品牌沉淀 |
| **🌏 海外阵列** | **18 大主流** | YouTube · TikTok · Instagram · Facebook · X (Twitter) · LinkedIn · **Pinterest · Snapchat · Threads · Reddit · Quora · VK (俄语区霸主) · LINE VOOM (日韩东南亚) · Vimeo · Rumble · Dailymotion · Telegram · WhatsApp** | 欧美主流 · 跨境电商选品 · 俄语区外贸 · 日韩东南亚 · 垂直极客社群 |

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

### 1. 线上产品官网 (Live Demo)
👉 **官网地址**：[https://martin-mqtech.github.io/open-matrix-publisher/](https://martin-mqtech.github.io/open-matrix-publisher/)

### 2. 本地一键启动
```bash
# 启动本地可视化控制台与 API 服务
./start_ui.sh
# 访问 http://localhost:5001
```

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
