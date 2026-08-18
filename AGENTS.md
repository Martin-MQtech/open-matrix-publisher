# AGENTS.md — 多代理协同约定（必读）

> 本仓库由 **多个 AI 代理并行协作**（目前：Freebuff/Codebuff 与 Antigravity，可能还有 Claude Code / Cursor）。
> **任何代理在动手前必须先读本文件**，并遵守以下规则，否则会互相覆盖、破坏交付。

---

## 0. 项目是什么（30 秒版）

Open Matrix Publisher（全域矩阵）——开源、本地运行的内容多域分发工具。
**Slogan：一条内容，多域分发。**
目标用户：传统外贸 B2B、跨境电商与 DTC 出海品牌、出海创作者。
形态：Web 优先（本地 Flask 控制台）+ 桌面客户端（macOS DMG / Windows exe）+ GitHub Pages 官网。

## 1. 品牌铁律（禁止违反，违反即返工）

1. **Slogan 只有一个：「一条内容，多域分发」**。禁止用具体平台数量（如"16 平台"）作口号——平台数量只允许出现在矩阵表等**事实数据**位置。
2. **配色**：炭黑/灰 + 橙黄。主橙 `#e8892e`，浅橙黄 `#f5b25a`，深橙 `#d6762a`。背景炭黑 `#141414`。
3. **严禁青色/霓虹/赛博朋克**：`#00e5ff`、`#0a0d14` 深蓝底、发光渐变（box-shadow glow）、青色渐变一律禁用——这是历史上被用户明确否决的风格。
4. **渐变仅限两处**：logo 的 O 环、主要 CTA 按钮。其余一律纯色、扁平。
5. **平台网络是动态生长的**：平台清单是数据（`PLATFORMS` 数组等 4 处数据源），不是身份。UI 计数必须动态计算，禁止写死数字。
6. **文字优先中文**（面向国内用户），技术名词可保留英文。

## 2. 文件所有权地图（防冲突核心）

| 文件 | 归属 | 内容 | 谁改 |
|---|---|---|---|
| `index.html` | **官网落地页** | 产品介绍/使用指南/下载/FAQ（GitHub Pages 主页） | 任一方可改，但**必须遵守品牌铁律** |
| `app.html` | **产品控制台** | 本地/桌面版实际 UI（上传/平台网格/分发/历史） | 任一方可改，但**禁止删掉控制台功能** |
| `local_bridge_server.py` | 后端 | Flask 服务，`/` 必须返回 `app.html` | 谨慎，先读再改 |
| `scripts/pre_delivery_audit.py` | 交付审计 | 交付前必跑，0 失败才可交付 | 谨慎 |
| `.github/workflows/*.yml` | CI | 构建/发布/审计门禁 | 谨慎，YAML 必须合法 |
| `OpenMatrixPublisher.spec` | 打包 | 桌面版打包清单（含 app.html） | 谨慎 |
| `docs/`、`执行手册.md` | 文档 | 设计/交付/发布口径 | 任一方可改，保持口径一致 |

**核心红线**：
- `index.html` 与 `app.html` 是**两个不同页面**，不要互相合并、不要用一个覆盖另一个。
- 产品控制台（`app.html`）是唯一的产品功能入口，**任何重构都不得删除其功能**。

## 3. 操作协议（每次动手前）

1. **先看状态**：`git status --short` + `git log --oneline -3`。工作区里**已修改的文件视为其他代理占用**，不要动它（除非任务明确要求且已确认）。
2. **读最新版再改**：要改共享文件（index.html / app.html / 后端 / workflow）前，先读磁盘当前内容，不要基于旧印象改。
3. **小步提交**：一次提交只做一件事，commit message 写清「为什么」。
4. **不要 push 别人的未提交工作**；自己 commit 后及时 push，避免领先过多。
5. **改动落地后**：跑 `python3 scripts/pre_delivery_audit.py`（无 `❌ 失败` 才允许交付），涉及桌面版再跑打包冒烟。

## 4. 交付验证（强制）

- 修改前端后：`python3 scripts/pre_delivery_audit.py` → 0 失败。
- 修改品牌相关后：用 `python3 scripts/visual_eye.py` 截图核对渲染（H1 slogan、配色无青色）。
- 修改 CI/打包后：YAML 用 `python3 -c "import yaml; yaml.safe_load(open(...))"` 校验。
- 仓库口径检查 CI（`.github/workflows/pre-delivery-audit.yml`）会在 push 时自动跑，失败即阻断。

## 5. 给 Antigravity 的特别说明

- 你之前把 `index.html` 重写成了落地页并删除了产品控制台——**产品控制台已恢复为 `app.html`**，这是有意设计（落地页=官网，控制台=产品）。
- 你初版落地页用了青色霓虹（`#00e5ff`）——**已被品牌铁律禁止**，现在的落地页是橙黑扁平版，请在此风格上迭代。
- 下载链接：macOS 用 DMG（`releases/latest/download/OpenMatrixPublisher-0.1.0.dmg`），Windows 用 exe。
- 两个代理不要同时大改 `index.html` / `app.html`——先 `git pull` / `git status` 确认没有对方未提交的改动。

---

## 6. 当前工作流分工（2026-08-18 定稿）

> 两个代理按工作流分工，**避免同时改同一文件**。改动前仍先看 §3 操作协议。

### 🎨 Antigravity 负责（官网 / 视觉 / 内容方向）
- `index.html` 落地页的**视觉与内容迭代**（hero 呈现、响应式细节、交互微调、文案润色）。
- 品牌展示素材：banner、OG 社交分享图、README 首屏视觉。
- 官网内容补充（使用场景、案例、FAQ 扩充）。
- **不改**：`app.html`、后端、workflow、打包配置。

### 🛠️ Freebuff/Codebuff 负责（功能 / 后端 / 交付方向）
- `app.html` 产品控制台功能完善与缺陷修复。
- 后端 `local_bridge_server.py`、登录链路（如补齐百家号/番茄扫码入口）、平台适配器。
- 打包 / CI / Release / 交付审计（`pre_delivery_audit.py`、`build-releases.yml`）。
- 文档口径（README、执行手册、docs/）与仓库一致性。

### 🤝 双方均可 / 需协调
- `AGENTS.md`、`README.md` 顶部：改动前先看对方是否有未提交改动。
- 任何**结构性改动**（新增页面、改路由、改平台清单）先在本节登记，避免冲突。

### 📋 当前已知待办（供认领）
- 补齐百家号 / 番茄扫码登录入口（登录链路，Freebuff 侧）。
- 4 个国际平台（TikTok/Instagram/X/LinkedIn）端到端验证（需真实账号，任一方可协助）。
- Phase 2：文章 / 图文分发管道（未启动，需用户确认优先级）。

---

*本文件由 Freebuff/Codebuff 建立于 2026-08-18，作为双代理协同的基准。如有冲突，以品牌铁律 §1 与文件所有权 §2 为准。*
