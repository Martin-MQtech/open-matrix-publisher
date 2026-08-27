# 🍪 Chrome 导出 Cookie 指南（OMP 导入用）

> OMP 的「📥 导入 Cookie」功能需要 `Playwright storage_state` 格式或纯 `list[cookie]` 格式的 JSON。
> Chrome 本身导不出这种格式——但通过下面任一办法，**1 分钟搞定**。

---

## 方法 A：装一个浏览器扩展（最简单 · 推荐）

### Chrome / Edge 用户

1. 装 **Cookie Editor**（免费，3MB）：
   - Chrome Web Store 搜 "Cookie Editor" → 第一个就是 → Add to Chrome
   - Edge Add-ons 同名搜得到
2. 打开目标平台并**保持登录**（如你已经登录了 YouTube）
3. 点浏览器右上角的 🧁 Cookie Editor 图标 → 弹出所有 cookie
4. 右上角 **Export** 按钮 → 选 **JSON** → 自动下载一个 .json 文件
5. 回到 OMP 控制台 → **📥 导入 Cookie** → 选平台 → 上传这个 .json → 完成 ✅

### Firefox 用户

1. 装 **cookies.txt** 或 **Cookie Quick Manager**
2. 导出 JSON
3. 同上

---

## 方法 B：DevTools 手动复制（不装扩展）

适合不想装任何东西的用户。

1. F12 打开 DevTools → **Application** 标签
2. 左侧 **Storage** → **Cookies** → 选对应域名（如 `.youtube.com`）
3. 你会看到一个 cookie 列表，**手动全选复制**（不现实，但理论可行）
4. 整理成 JSON 数组，字段需要这些：

```json
[
  {
    "name": "VISITOR_INFO1_LIVE",
    "value": "abc123...",
    "domain": ".youtube.com",
    "path": "/",
    "expires": -1,
    "httpOnly": false,
    "secure": true,
    "sameSite": "None"
  }
]
```

⚠️ **手写字段太容易出错**——除非你懂 httpOnly/secure/sameSite 区别，否则**用方法 A**。

---

## 方法 C：让 OMP 自己的扫码弹窗导出（最省事）

OMP 自带的「🔑 扫码登录」流程会**用 Playwright 打开你电脑的 Chrome profile**——
你扫一次码，OMP 拿到 cookie 后**自己会存到** `cookies/{platform}_default.json`（加密版是 `.enc`）。

所以**最省事的方式**就是：每个平台点一次「🔑 登录」→ 扫一次码 → 完事。

> 批量操作：点「🔁 批量扫码」按钮，OMP 会逐个打开浏览器等你扫码。

---

## ❓ 常见问题

### Q: 导出的 Cookie 立即失效？
A: Cookie 经常和 IP/UA 绑定。如果你的电脑和 OMP 运行的电脑不是同一台，可能立即失效。
- 解决：把 Cookie 导入到**和 Chrome 登录同一台电脑**的 OMP

### Q: 上传后 OMP 报「登录失效」？
A: Cookie 真的过期了（特别是 2FA / 短信验证过的账号会短命）。
- 解决：重扫码，或换账号

### Q: 我导出的 Cookie 是 .txt 不是 .json？
A: 那大概是 cookies.txt 格式（curl 用），OMP 不支持。先用上面的 Cookie Editor 转成 JSON。

### Q: 平台说我异地登录？
A: 大多数平台都允许异地一段时间（1-7 天）。如果触发风控，去平台 App 验证一次。

---

## 🔐 安全提醒

- **不要把 Cookie 文件发给陌生人**——拥有 Cookie 等于拥有账号。
- OMP 收到后会**自动加密存储**（用系统钥匙串），但导出源头（你的电脑）请自己保管好。
- 如果你离职/换客服，**记得通知所有平台重置密码**。

---

_本指南是 OMP 项目的官方文档之一 · MIT 协议 · 欢迎补充更多导出工具_
