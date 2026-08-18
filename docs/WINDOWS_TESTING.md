# Windows 版本测试指南（Tester Guide）

> **目标**：Windows 是主要用户群。本指南供 Windows 测试者（内部或社区用户）在真实 Windows 机器上验证桌面版。
> **背景**：开发者本机是 macOS，无法直接测试 Windows；打包产物由 GitHub Actions 在**真实 Windows runner** 上构建并自动冒烟（`--selftest`），但真实使用仍需人工验证。

## 一、获取安装包

**方式 A（推荐）**：从 GitHub Actions 工件下载
1. 打开仓库 → **Actions** → 选择最新的 **"Build & Release Desktop Apps"** 运行记录；
2. 底部 **Artifacts** → 下载 `OpenMatrixPublisher-Windows`；
3. 解压得到 `OpenMatrixPublisher-Setup.exe`。

**方式 B**：正式发布后从 Releases 页面下载（打 `v*` tag 自动发布）。

## 二、安装与首次运行

1. **双击 `OpenMatrixPublisher-Setup.exe`** —— 应弹出桌面窗口，标题含「Open Matrix Publisher (全域矩阵) · 一条内容，多域分发」；
2. **首次使用需要 SAU 引擎**（上传能力依赖）：
   - 双击仓库里的 `start_ui.bat`，按提示一键安装（git clone → venv → 依赖 → 浏览器）；
   - 或手动安装：`git clone https://github.com/dreammis/social-auto-upload.git` 到 `%USERPROFILE%\social-auto-upload`，运行其安装说明。
3. 页面顶部应显示「引擎已连接」；平台网格显示国内/海外分组和登录状态。

## 三、测试清单（逐项打勾）

### 基础（必测）
- [ ] exe 双击可启动，窗口正常，无报错黑框
- [ ] 顶栏「引擎已连接」，无「未检测到 SAU」警告
- [ ] 页面 H1 为「一条内容，多域分发」，平台计数动态正确（国内 10 / 海外 6 / 已登录 X/16）
- [ ] 选一个视频 → 预览可播放 → 填标题/描述 → 勾选平台 → 发布确认弹窗出现
- [ ] 数据目录：`%APPDATA%\OpenMatrixPublisher\` 下出现 `uploads/`、`covers/`、`dispatch_history.json`

### 登录（选测）
- [ ] 点平台卡片「扫码登录」→ **弹出真实浏览器窗口**（不是第二个软件窗口！）
- [ ] 扫码成功后状态变绿，重启 exe 后登录态仍在

### 上传（选测，用测试账号）
- [ ] 单平台发布一次 → 平台后台确认视频上线
- [ ] 同一视频再发 → 被防重拦截提示「已发布过」

### 反馈
- [ ] 问题反馈：GitHub Issues 提交，附：Windows 版本号、现象截图、`%APPDATA%\OpenMatrixPublisher\` 下日志

## 四、已知限制（测试时注意）

| 项 | 说明 |
|---|---|
| 百家号 / 番茄视频 | 扫码登录已接入（2026-08-18），可直接一键扫码 |
| TikTok / Instagram / X / LinkedIn | 端到端验证中（Beta 标记），需真实账号 |
| 未装 SAU | exe 可打开但发布/登录不可用，需先按「二、2」安装 |
| 断网 | UI 和字体已本地化，可正常打开；登录/发布需联网 |

## 五、CI 自动冒烟（开发者视角）

每次构建（tag 或手动触发），GitHub 会在真实 Windows runner 上：
1. PyInstaller 打包 exe；
2. 运行 `OpenMatrixPublisher-Setup.exe --selftest` → 内嵌后端启动 → 轮询 `/api/health` → 写 `selftest_result.json`；
3. 校验结果，失败则构建标红。

这是"打包产物必须真跑过"机制的 Windows 落地，macOS 同样执行。
