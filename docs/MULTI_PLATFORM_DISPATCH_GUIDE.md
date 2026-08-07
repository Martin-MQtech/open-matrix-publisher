# 多平台视频自动化一键分发工程经验与 SOP 总结 (2026版)

## 一、 架构设计与防重机制 (Deduplication Guard)

为保证多次运行或断点重试时**绝不造成重复发布**，项目建立严格的幂等控制与状态持久化机制。

### 1.1 幂等性控制 (`dispatch_history.json`)
* **记录结构**: 每次分发任务都会记录 `video_file` (中文版 / 英文版)、`platform` (抖音、快手、小红书、B站、视频号、微博、知乎等)、`status` (`success` / `fail`) 及唯一发布 ID `pub_id`。
* **发布前校验 (Pre-Dispatch Check)**: 在执行具体平台的 Playwright / Custom Uploader 前，先校验 `dispatch_history.json`。若该视频文件在该平台已存在 `status == "success"` 记录，则自动跳过分发，输出 Warning 并防止重复操作。

---

## 二、 Cookie 捕获与持久化避坑指南

### 2.1 视频号 (Tencent / WeChat Channels) 登录坑位与解法
* **现象**: 使用 Playwright headless 或自动化脚本时，扫码完成后窗口若过早关闭或被非正常 Kill，`sau tencent login` 无法将新的 Session/State 写回 `tencent_default.json`。
* **正方向流程**:
  1. 使用 `--headed` 模式启动微信视频号登录。
  2. 用户在手机微信端点击「确认登录」。
  3. **关键点**: 自动化脚本需捕获到页面导航完成（跳转至视频号创作者平台首页 `https://channels.weixin.qq.com/platform`），并显式调用 `storage_state(path=...)` 持久化写盘后，方可关闭浏览器 context。

### 2.2 微博 (Weibo) 视频发布页 DOM 限制与 JS 注入突破
* **现象**: Playwright 定位 `https://weibo.com/upload/channel` 时，标题输入框 (`input[placeholder*='标题']`) 的 `is_visible()` 会返回 `False`，导致 `.click()` 或 `.fill()` 触发 30000ms Timeout Error。
* **根因**: 微博发布页的内部 `input` 被外层 CSS / 弹窗包裹或隐藏，仅暴露虚拟渲染框。
* **通用解法 (JS Event Dispatch)**:
  使用 Playwright 的 `page.evaluate()` 直接派发原生 DOM 事件：
  ```javascript
  const inputs = Array.from(document.querySelectorAll('input, textarea'));
  const el = inputs.find(i => i.placeholder && i.placeholder.includes('标题'));
  if (el) {
      el.value = "你的标题文本";
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  ```
  此方法可 100% 绕过 CSS 可见的判定拦截，稳定填充微博、百家号等自媒体平台的复杂文本组件。

---

## 三、 平台适配现状与执行 SOP

| 平台 | 状态 | 接入模式 | 防重机制 | 注意事项 |
| :--- | :--- | :--- | :--- | :--- |
| **抖音 (Douyin)** | ✅ 已发 | SAU Native Engine | 强校验 (Hash + History) | 稳定 |
| **快手 (Kuaishou)** | ✅ 已发 | SAU Native Engine | 强校验 (Hash + History) | 稳定 |
| **小红书 (XHS)** | ✅ 已发 | SAU Native Engine | 强校验 (Hash + History) | 包含多标签处理 |
| **B站 (Bilibili)** | ✅ 已发 | SAU Native Engine | 强校验 (Hash + History) | 需设置分区与简介 |
| **微博 (Weibo)** | 🔧 适配中 | Custom JS Uploader | 强校验 (Hash + History) | 采用 JS Event 注入 |
| **视频号 (Tencent)** | 🔐 需扫码| SAU Native Engine | 强校验 (Hash + History) | 扫码后需等待首页跳转 |
| **知乎 (Zhihu)** | 🔐 待登录| Custom Playwright | 强校验 (Hash + History) | 待提取凭证 |
| **头条 (Toutiao)** | 🔐 待登录| Custom Playwright | 强校验 (Hash + History) | 待提取凭证 |

---

## 四、 故障诊断排查路线

1. **查重**: 先看 `dispatch_history.json`，确保不重复发。
2. **看 Cookie**: 检查 `/Users/martin/social-auto-upload/cookies/<platform>_default.json` 的修改时间和字节数。
3. **试连通**: 运行单平台测试逻辑，实时打印页面 `title` 与 `url`。
4. **报表落盘**: 无论成功失败，全部更新至 `dispatch_history.json` 和日志，保证数据透明可追溯。
