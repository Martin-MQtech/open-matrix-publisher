# 🎯 开源发布 REPO 验收清单 (Release Checklist)

> **用途**：首次 push / 对外发布前，逐项核对本仓库是否达到公开标准。任何 AI Agent 或人类接手发布时，按此清单逐条确认；未通过的条目必须先处理，再执行 `git push`。
>
> **状态标注**：✅ = 已通过　⚠️ = 需注意　❌ = 未通过　⬜ = 待执行
>
> **最后核对日期**：2026-08-18

---

## 一、发布前置（仓库状态）

- [x] ✅ **远端已配置**：`git remote -v` 指向 `https://github.com/Martin-MQtech/open-matrix-publisher.git`
- [x] ✅ **存在提交历史**：`git log --oneline` 有记录（当前最新 3fc5207）
- [x] ✅ **许可证**：`LICENSE` 存在且为 MIT，版权人「Martin · MUQI Tech（木齐科技）」，与 README 声明的 MIT 一致
- [x] ✅ **平台口径**：README/执行手册/SKILL/宣传草稿统一为「20 平台（国内 10 + 海外 10，LinkedIn 暂不支持）」，无 28/19/18/16/15/14+/7 等旧数字残留
- [x] ✅ **平台口径 CI 门禁**：`.github/workflows/platform-count-check.yml` 在每次 push / PR 自动运行 `scripts/check_platform_count.py`，扫描 README/执行手册/全部 `docs/` 与 `skills/` 下 Markdown，出现 28/19/18/16/15/14+/7 等旧平台数字即失败（本地可先跑 `python3 scripts/check_platform_count.py` 自检）
- [x] ✅ **README 首屏素材**：`logo.png`（大 M + 橙黄渐变 O + 外圈，置顶居中）+ `media/demo-flow.gif`（15 秒核心流程演示）+ `logo.svg`（网页/favicon）+ `favicon.ico`（16~256px 多尺寸，浏览器降级用）+ `logo-mono-{white,black,orange}.svg/.png`（单色版）
- [x] ✅ **文档体系**：`执行手册.md`（权威总纲）、`docs/DESIGN_AND_PRODUCT_PLAN.md`（设计与产品方案）、`docs/RELEASE_CHECKLIST.md`（本文件）

---

## 二、敏感文件与凭据核对（重点，禁止提交）

> 以下任何一项若命中「已跟踪」，必须先 `git rm --cached` 移出索引并加入 `.gitignore`，**绝不强推**。

- [x] ✅ **Cookie 文件**：`cookies/` 仅跟踪 `cookies/.gitkeep`；真实 `*_default.json` 全部被忽略，`git ls-files` 无命中
- [x] ✅ **平台凭证**：`platform_credentials.json`（真实）被忽略；仅提交 `platform_credentials.template.json`（占位符模板，已确认无真实数据）
- [x] ✅ **环境变量**：`.env` 被忽略
- [x] ✅ **媒体/产物**：`*.mp4 / *.mov / *.avi / *.mkv / *.jpg / *.jpeg / *.png / *.gif`、`uploads/`、`covers/` 被忽略（唯一例外：`!media/demo-flow.gif` 白名单）
- [x] ✅ **运行痕迹**：`dispatch_history.json`、`.dispatch.lock`、`.task_progress/`、`*.log` 被忽略
- [x] ✅ **内部工具目录**：`.workbuddy/`（智能体记忆）、`.freebuff/`（工具状态）已加入 `.gitignore`，且 `.workbuddy/` 已于 2026-08-18 从 git 索引移除（磁盘文件保留）
- [x] ✅ **源码凭据扫描**：`git grep` 常见密钥模式（sk-、AKIA、api_key、password、secret）仅命中 `platform_credentials.template.json`（模板占位符）
- [x] ✅ **删除文件确认**：`git status` 中 `.workbuddy/memory/*.md` 显示为 D（staged 删除），提交后仓库不再包含

**复核命令（发布前必须重跑一遍）：**

```bash
# 1. 已跟踪敏感文件
git ls-files | grep -iE "cookie|credential|\.env|\.db|\.pkl|\.key|secret|token|\.workbuddy|\.freebuff"
# 2. 凭据模式
git grep -lIE "sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|api[_-]?key.{0,12}[:=].{8,}|password.{0,12}[:=].{8,}|secret.{0,12}[:=].{8,}"
# 3. 确认 cookies/ 只有 .gitkeep
git ls-files cookies/
```

---

## 三、`.gitignore` 完整性核对

- [x] ✅ Python：`__pycache__/ *.py[cod] *.pyo .env *.egg-info/ dist/ build/`
- [x] ✅ 凭证：`cookies/*.json *.pkl *.db platform_credentials.json *.cookie`
- [x] ✅ 媒体：`*.mp4 *.mov *.avi *.mkv *.jpg *.jpeg *.png *.gif uploads/ covers/`（+ `!media/demo-flow.gif`）
- [x] ✅ 运行痕迹：`*.log dispatch_history.json .dispatch.lock .task_progress/`
- [x] ✅ 内部工具：`.workbuddy/ .freebuff/ .venv/ .idea/ .vscode/`
- [x] ✅ OS：`.DS_Store Thumbs.db`

---

## 三·五、交付前审核门禁（强制）

- [ ] ✅ **自动审计**：`python3 scripts/pre_delivery_audit.py` 必须 0 FAIL（桌面版加 `--smoke`）
- [ ] ✅ **打包态冒烟**（桌面版）：启动 .app → `/api/health` 200 → 扫码登录弹**真实浏览器** → 静态资源 200
- [ ] ✅ **机制文档**：`docs/DELIVERY_REVIEW.md` 已随交付更新

---

## 四、首次 push 前的最后动作

> ⚠️ **当前工作区有大量未提交改动**（本轮全部视觉/功能/文档工作），首次 push 前需先完成一次干净的提交。

- [ ] ⬜ **提交范围核对**：`git status --short` 逐项确认；用 `git add -A --dry-run` 预演，确认不会带入 `uploads/ covers/ cookies/ .workbuddy/ .freebuff/`
- [ ] ⬜ **提交新资产**：`docs/ omp_paths.py start_ui.bat start_ui.ps1 media/demo-flow.gif logo.svg logo-mono-*.svg/png favicon.ico icon.ico icon.icns .gitignore` 等本次新增/修改文件
- [ ] ⬜ **提交信息**：按仓库既有风格（如 `feat: ...` / `docs: ...` / `style: ...`），一句话说明"为什么"
- [ ] ⬜ **push 前自查**：`git status` 干净；`git diff --cached --stat` 无意外文件
- [ ] ⬜ **执行 push**：`git push -u origin main`
- [ ] ⬜ **push 后验证**：GitHub 仓库页面确认文件列表无敏感项、README 动图正常渲染、LICENSE 可见

---

## 五、发布后跟进（非阻塞，但建议尽快）

- [ ] ⬜ 开启 GitHub Pages（静态界面预览页，README 已有链接）
- [x] ✅ 国际平台端到端验证已收尾：X / Facebook / TikTok / Instagram 实测发布成功，LinkedIn 暂不支持（待官方 API）
- [x] ✅ 宣发帖（`docs/PROMOTION_POSTS.md` / `docs/CREATIVE_PROMOTION_POSTS.md`）按 20 平台口径发布
- [ ] ⬜ 提交至 MagicBox.tools / Product Hunt（策略见 `docs/OPENSOURCE_GROWTH_STRATEGY.md`）

---

## 六、已知需人工判断项（不阻塞发布）

- ⚠️ **提交历史**：早期 commit（如 `3e7da55`）描述含「28-platform matrix」，历史不可改写，属正常演进痕迹，无需处理
- ⚠️ **GitHub Actions**：`desktop_app.py` 的 CI/CD workflow 仍在打包 `showcase_banner.jpg` 等旧素材（页面已不再引用），发布后建议清理 workflow 产物
- ⚠️ **5001 后端进程**：本机 5001 仍为旧代码（`/api/health` 404、`/api/history` 死锁），本地使用前需重启 `./start_ui.sh`；与发布无关
