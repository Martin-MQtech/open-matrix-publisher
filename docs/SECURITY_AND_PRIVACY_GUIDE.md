# 🛡️ 【全域矩阵】 隐私保护与凭证安全白皮书 (Security & Privacy Guide)

> **核心原则**：零信任架构 (Zero-Trust Architecture)、凭证彻底隔离 (Credential Isolation) 与 本地优先 (Local-First Privacy)。

---

## 一、 Agent 与本地系统的安全隔离承诺

1. **零私存机制**: AI 编码助手完全在本地受控环境中运行，没有任何私存或上传用户个人密码、API Key 的行为。
2. **自动 Git 屏蔽 (.gitignore)**: 所有本地登录生成的 `cookies/`、`*.vault`、`storage_state.json` 以及环境配置文件 `.env` 已被全局 Git 过滤墙阻断，**绝对无法被提交或推送到 GitHub 公开仓库**。

---

## 二、 行业开源项目普遍采用的 4 大凭证安全标准

```text
┌────────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│ 1. 凭证与源码彻底分离  │  ──► │ 2. 占位符模板机制      │  ──► │ 3. GitHub 密钥自动扫描 │
│ `.env` + `.gitignore`  │      │ `.env.example` 占位符   │      │ GitHub Secret Scanning │
└────────────────────────┘      └────────────────────────┘      └────────────────────────┘
```

### 1. 环境变量与凭证彻底隔离 (`.env` + `.gitignore`)
- **原则**: 源代码中 100% 禁止硬编码 (No Hardcoded Credentials) 任何真实 API Key、密码或 Cookie。
- **实现**: 所有敏感信息仅保存在用户本地电脑的 `.env` 文件或 `cookies/` 目录中。

### 2. 示例文件与占位符模式 (`.env.example`)
- 在开源仓库中，仅提供不含敏感数据的示例模板：
  ```bash
  # .env.example (示例模板，不含真实数据)
  PLATFORM_COOKIE_PATH=./cookies/
  AI_API_KEY=YOUR_API_KEY_HERE
  ```

### 3. GitHub 密钥自动扫描防护 (GitHub Secret Scanning)
- 项目开启 GitHub 官方 Secret Scanning 服务。如果开发者误将包含 Token 的代码提交，GitHub 将在 1 秒内阻断 Commit 并向作者发出安全警报。

### 4. 本地加密金库 (Local Cookie Vault)
- 用户在本地浏览器登录产生的凭证仅在本地 CPU/内存中解析，绝不上传至任何集中式云端服务器。
