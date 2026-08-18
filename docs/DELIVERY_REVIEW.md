# 交付前审核机制（Pre-Delivery Review）

> **原则：任何改动交付给用户之前，必须全量自检一遍——低级错误、逻辑不自洽、使用不通顺，一个都不放过。宁可慢，不可错。**

## 为什么要有这个机制

2026-08 桌面版首次交付时暴露了低级错误：打包后的 App 点击「扫码登录」会弹出**第二个软件窗口**而不是浏览器。根因是 `sys.executable` 在打包态指向 App 本体——开发态（源码运行）一切正常，所以长期没被发现。

**教训**：开发环境会掩盖打包态的行为差异（`sys.executable` 变 App、`__file__` 变临时目录、静态资源不会自动进包）。必须靠**机制**而非运气来拦截这类错误。

## 审核时机

| 场景 | 是否必跑 |
|---|---|
| 任何代码/资源/文档改动后、交付给用户前 | ✅ 必跑 |
| 重新打包桌面版（DMG/App）后 | ✅ 必跑（含 `--smoke`） |
| 修改了平台清单 / 登录 / 上传引擎 | ✅ 必跑 |
| 纯文案微调（如宣传文档） | ⚠️ 建议跑（成本极低） |

## 第一步：自动审计（机器查）

```bash
python3 scripts/pre_delivery_audit.py            # 全量检查
python3 scripts/pre_delivery_audit.py --smoke    # 额外对运行中的服务做冒烟
python3 scripts/pre_delivery_audit.py --verbose  # 显示通过项明细
```

覆盖 12 类检查，分三组：

**A. 低级错误**
- A1 全部 Python 文件语法编译
- A2 `sys.executable` 雷区（打包态会指向 App 本体）
- A3 `__file__` 相对可写路径（打包态指向临时目录，数据会丢）
- A4 打包产物资源完整性（前端引用 vs 包内文件）

**B. 逻辑不自洽**
- B1 前端引用的本地资源均存在
- B2 外网/CDN 依赖（桌面版断网可用性）
- B3 前端调用的 API 与后端路由一一对应
- B4 16 平台口径跨模块一致性（后端引擎 / MCP / 前端 / 登录检测）
- B5 登录覆盖缺口（有登录按钮但无登录入口的平台）
- B6 静态路由扩展名覆盖前端引用

**C. 使用不通顺**
- C1 运行中服务冒烟检查（`--smoke` 时）
- C2 文档平台数字口径（复用 `scripts/check_platform_count.py`）
- C3 遗留 TODO/FIXME/调试代码

**门禁规则**：`❌ 失败` = 阻断交付，必须修复；`⚠️ 警告` = 可交付但必须逐条确认。

> `--smoke` 模式额外包含 **C4 视觉冒烟**：用 `scripts/visual_eye.py` 截图 + OCR 校验 UI 关键文案（H1/Slogan/平台区）真实渲染，不再只信代码。

## 第二步：打包态冒烟（桌面版必做）

自动审计通过后，桌面版还必须人工/脚本跑一轮真实启动：

```bash
# 1. 启动打包产物（无源码干扰）
./dist/OpenMatrixPublisher.app/Contents/MacOS/OpenMatrixPublisher

# 2. 验证健康检查
curl http://127.0.0.1:5001/api/health   # 期望 status:"ok"

# 3. 验证登录链路：点击某平台「扫码登录」→ 应弹出【真实浏览器】窗口
#    （不是第二个软件窗口！这是历史踩坑点）
curl -X POST http://127.0.0.1:5001/api/launch-login -H 'Content-Type: application/json' -d '{"platform_id":"douyin"}'

# 4. 验证静态资源（打包态下这些必须 200）
for f in logo.svg favicon.ico vendor/fontawesome/all.min.css; do
  curl -s -o /dev/null -w "$f: %{http_code}\n" "http://127.0.0.1:5001/$f"
done
```

## 第三步：人工确认项（机器查不了，必须人来）

| 确认项 | 方法 |
|---|---|
| 真实发布链路 | 用测试内容单平台发布一次，到平台后台确认上线 |
| 登录实测 | 扫码登录一个平台，确认 Cookie 落盘、状态变绿 |
| 视觉检查 | 用 `python3 scripts/visual_eye.py page http://127.0.0.1:5001` 截图+OCR 核对页面文案/状态；`window "Open Matrix Publisher"` 可读真实桌面窗口 |
| 数据持久化 | 重启服务后历史记录/上传仍在 |
| Windows 兼容 | 若有 Windows 用户，需在真实 Windows 环境跑一遍 |

## 变更记录

- 2026-08-18 建立机制：新增 `scripts/pre_delivery_audit.py` + 本文档 + CI 门禁（`.github/workflows/pre-delivery-audit.yml`）。
