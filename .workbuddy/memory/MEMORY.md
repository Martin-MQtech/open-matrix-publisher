# Open Matrix Publisher — 项目长期记忆

## 定位
开源、AI-Native、跨平台视频静默分发引擎（Martin·木齐科技 / MUQI Tech）。MIT 免费，双轮驱动：
① Web 可视化控制台（index.html + local_bridge_server.py Flask，端口 5001）
② AI-Native CLI 引擎（dispatch.py → real_uploader_engine.py → SAU + custom_uploaders/）。
目标：用作品传播个人 IP 与开发者影响力，不以直接变现为 KPI。

## 设计铁律（来自 执行手册.md，2026-08-07 事故复盘）
- 发布前先 kill 所有分发进程；全程只跑唯一一条分发链路；防重 Ledger(dispatch_history.json)+进程锁(.dispatch.lock) 只在单一脚本内有效。
- "脚本成功"≠视频已上线，必须人工登录各平台后台确认状态。
- 发现重复发布立刻 kill 全部进程，绝不用脚本撤稿（交用户人工删）。
- cookies/ 与 platform_credentials.json 永不入库（.gitignore 已屏蔽）。

## 关键架构事实
- SAU 依赖：/Users/martin/social-auto-upload（第三方，勿改其代码）。SAU_ROOT 可经环境变量覆盖（引擎、base、__init__、tiktok_adapter、start_ui.sh 均已支持）。
- 运行环境：控制台(Flask)与上传任务统一用 SAU 的 venv Python（/Users/martin/social-auto-upload/.venv/bin/python），已装 flask + browser_cookie3 + patchright + playwright。启动用 `./start_ui.sh`（自动补装依赖、支持 SAU_ROOT 覆盖）。
- 国内 8 家（抖音/快手/小红书/B站/视频号/微博/知乎/头条）：上传器具备、Cookie 齐全、引擎命令(`sau <p> upload-video`)经 CLI --help 验证匹配。
- 国际 6 家（YouTube/TikTok/X/LinkedIn/FB/IG）：上传器已写且 import 验证通过、Cookie 齐全；IG 为"真实尝试"版（反自动化未必过）。E2E 待用户实测。
- 代理：X/TikTok/LinkedIn/FB/IG/YouTube 经 Clash 代理（conf.YT_PROXY=127.0.0.1:7890）。国内平台直连。
- 防重：dispatch_history.json + is_already_published（默认禁止重复发布，force 才允许），位于 local_bridge_server。
- 通用工具原则：引擎/控制台必须通用，不写具体产品词；产品专属脚本（batch_dispatch_*/multi_platform_dispatcher_v2）属"首个使用案例"，应归 examples/。

## 2026-08-09 状态
- 已完成：Batch1 解耦重构(fe6021e..3148a14)、LICENSE、GitHub Pages+仓库元数据、UI 重构与视觉精修、运行性 bug 修复(dfb8f79)。
- 已验证（不实际发布）：14/14 平台 Cookie 登录态识别、桥接服务 /api/status=14/14 logged_in、sau CLI 参数匹配、8 个自定义上传器 import OK。
- 待用户实测：各平台真实发布成功率、IG 反自动化、Cookie 发布时新鲜度。
