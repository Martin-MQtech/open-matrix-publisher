# Postiz 平台集成论证报告（2026-08-18）

> **背景**：用户提出「Postiz 已支持 30+ 平台，为什么我们不如它多？能不能直接集成？」
> 本文档基于 Postiz 官方文档与源码调研，给出**完整平台清单对比**与**集成可行性论证**。

---

## 1. Postiz 完整平台清单（32 个，官方 API 文档实列）

来源：Postiz Public API `/integrations` 的 identifier 枚举 + providers 文档。

| # | identifier | 平台 | 接入方式 | 与我们重叠？ |
|---|---|---|---|---|
| 1 | x | X / Twitter | OAuth app | ✅ 已有 |
| 2 | linkedin | LinkedIn（个人） | OAuth app | ✅ 已有（暂不支持） |
| 3 | linkedin-page | LinkedIn（企业页） | OAuth app | ➕ 可新增 |
| 4 | facebook | Facebook | OAuth app | ✅ 已有 |
| 5 | instagram | Instagram | OAuth app | ✅ 已有 |
| 6 | instagram-standalone | Instagram 独立 | OAuth app | ➕ 可新增 |
| 7 | threads | Threads | OAuth app | ➕ 可新增 |
| 8 | bluesky | Bluesky | **用户填 app password** | ➕ 可新增 |
| 9 | mastodon | Mastodon | **用户填实例+账号** | ➕ 可新增 |
| 10 | warpcast | Farcaster | OAuth app | ➕ 可新增 |
| 11 | nostr | Nostr | **用户填私钥** | ➕ 可新增 |
| 12 | vk | VK（俄罗斯） | OAuth app | ➕ 可新增 |
| 13 | youtube | YouTube | OAuth app | ✅ 已有 |
| 14 | tiktok | TikTok | OAuth app | ✅ 已有 |
| 15 | reddit | Reddit | OAuth app | ➕ 可新增 |
| 16 | lemmy | Lemmy | **用户填实例+账号** | ➕ 可新增 |
| 17 | discord | Discord | OAuth app | ➕ 可新增 |
| 18 | slack | Slack | OAuth app | ➕ 可新增 |
| 19 | telegram | Telegram | **用户填 bot token** | ➕ 可新增 |
| 20 | kick | Kick（直播） | OAuth app | ➕ 可新增 |
| 21 | twitch | Twitch（直播） | OAuth app | ➕ 可新增 |
| 22 | pinterest | Pinterest | OAuth app | ➕ 可新增 |
| 23 | dribbble | Dribbble | OAuth app | ➕ 可新增 |
| 24 | medium | Medium | **用户填 API key** | ➕ 可新增 |
| 25 | devto | Dev.to | **用户填 API key** | ➕ 可新增 |
| 26 | hashnode | Hashnode | **用户填 API key** | ➕ 可新增 |
| 27 | wordpress | WordPress | **用户填应用密码** | ➕ 可新增 |
| 28 | gmb | Google My Business | OAuth app | ➕ 可新增 |
| 29 | listmonk | Listmonk（邮件） | **用户填账号** | ➕ 可新增 |
| 30 | moltbook | Moltbook | 应用内连接 | ➕ 可新增 |
| 31 | skool | Skool | **浏览器扩展会话** | ➕ 可新增 |
| 32 | whop | Whop | OAuth | ➕ 可新增 |

**结论：与我们重叠 6 个（x/linkedin/facebook/instagram/youtube/tiktok），新增 26 个。**

---

## 1.5 API 成本分析（2026-08-18 核实）——不是所有官方 API 都收费

> 用户关切："Postiz 全用 API，API 要付很高费用，没法合到一起。"
> **核实结论：收费是少数，免费是多数；且我们有免费替代的平台根本不需要走 API。**

| 平台 API | 费用 | 对我们的意义 |
|---|---|---|
| **X / Twitter** | ❌ **贵**：免费层已取消，按量付费 $0.015/帖（带链接 $0.20/帖），或 $100-200/月订阅 | **不需要**——我们已用 Cookie 自动化免费实测发布成功 |
| **Reddit** | ❌ 商业收费（2023 起） | 暂不接 |
| **LinkedIn** | ⚠️ 免费但需 OAuth app 审核，个人 API 受限 | 保持"暂不支持"，等开源方案成熟 |
| **Medium** | ⚠️ 免费但新应用申请受限 | 暂缓 |
| **Dev.to** | ✅ 免费（API key） | **值得接** |
| **Hashnode** | ✅ 免费（API key） | **值得接** |
| **WordPress** | ✅ 免费（应用密码） | **值得接** |
| **Telegram** | ✅ 免费（bot token） | **值得接** |
| **Bluesky / Mastodon / Nostr / Lemmy** | ✅ 免费（开放协议，填账号即可） | 按需接 |
| **YouTube / Threads / Pinterest / Instagram Graph** | ✅ 免费配额（需开发者 app 审核） | 已有免费替代（SAU/instagrapi），不重复接 |

**结论**：
1. 我们**不会为任何平台付 API 费**——已接入的 16 平台全部走免费路线（Cookie/SAU/instagrapi），X 等收费 API 平台我们已有免费替代；
2. 从 Postiz 借鉴的仅限**免费 API 平台**（Dev.to/Hashnode/WordPress/Telegram 等），零成本；
3. "合到一起"本就不成立——我们不引入 Postiz 本体（AGPL 许可证 + 重型架构），只拿它的平台清单和接入路径作参考。

---

## 2. 为什么 Postiz 有 30+ 平台，而我们只有 16？

**根本差异：接入路线不同。**

| | Postiz | 我们（OMP） |
|---|---|---|
| 接入路线 | **全部官方 API / OAuth**（合规、稳定、无反自动化） | 本地 Cookie + 浏览器自动化（零配置、免注册） |
| 新增一个平台要做什么 | 注册开发者 app → 填 key → 调官方 API | 攻克该平台的反自动化（每个平台都要单独斗法） |
| 平台越多越容易？ | **越容易**（API 是标准化的） | 越难（反自动化逐个变硬） |
| 用户门槛 | 每个平台要注册开发者应用/填 key | 扫码/Chrome 提取即可 |
| 国内平台 | **一个都没有**（无抖音/快手/小红书/B站/视频号/微博/头条/知乎/百家号/番茄） | **10 个全覆盖（护城河）** |

**一句话**：Postiz 是「官方 API 路线」的规模化优势，我们是「本地 Cookie 路线」的零门槛优势。它 30+ 是因为 API 对接可复制；我们 16 是因为每个平台的反自动化都要单独硬啃。

---

## 3. 能不能直接集成？——能，但不是「整个 Postiz 拿过来」

### ❌ 不可行方案：直接引入 Postiz 本体
- **许可证冲突**：Postiz 是 **AGPL-3.0**（传染性强的开源协议），集成进我们项目会强制开源整个产品；
- **技术栈不匹配**：Postiz 是 NestJS + NextJS + PostgreSQL + Temporal 的重型云架构，我们是轻量本地 Python 单文件服务；
- **部署模型冲突**：Postiz 要跑数据库/队列，我们承诺「100% 本地、免注册、双击即用」。

### ✅ 可行方案：借鉴平台清单 + 逐个接入官方 API 适配器
Postiz 验证了「哪些平台有官方 API、怎么接」，我们**按它的清单逐个写轻量适配器**，沿用我们现有的 `custom_uploaders/` 架构：

**第一批（零门槛，用户填 key 即可，无需注册开发者 app）**——Postiz 文档明确「10 个平台无需配置」：
- Medium（API key）、Dev.to（API key）、Hashnode（API key）、WordPress（应用密码）、Bluesky（app password）、Mastodon（实例+账号）、Nostr（私钥）、Telegram（bot token）、Lemmy（实例+账号）、Listmonk（账号）

**第二批（需注册 OAuth app，Postiz 已验证路径）**：
- Threads、Reddit、Pinterest、VK、Twitch、Kick、Dribbble、Google My Business、LinkedIn Page

**关键收益**：
1. **LinkedIn 复活**：Postiz 走 LinkedIn 官方 Marketing API（OAuth）——这正是我们「暂不支持」的解法，直接照抄其 API 对接方式；
2. **Phase 2 文章/图文天然契合**：Medium/Dev.to/Hashnode/WordPress/Reddit 本来就是文章平台——「一条内容」（不限视频）的定位完美承接；
3. **差异化保留**：国内 10 平台 Postiz 一个都没有，这是我们的护城河，继续用 Cookie 路线；
4. **合规升级**：官方 API 路线无封号风险，适合企业客户。

---

## 4. 建议节奏

| 阶段 | 内容 | 预估 |
|---|---|---|
| 近期（Phase 2 前） | 接入 API-key 类 5 个：Medium / Dev.to / Hashnode / WordPress / Telegram | 每个 1-2 天 |
| Phase 2（文章/图文） | 文章管道 + 上述平台适配器一起上 | 与文章管道合并 |
| 中期 | OAuth 类：Threads / Reddit / Pinterest / LinkedIn（官方 API） | 需注册开发者 app |
| 远期 | VK / Twitch / Kick / GMB 等按需 | 看目标用户 |

**对外口径**：平台网络继续「动态生长」——矩阵表如实更新（16 → 21 → …），Slogan 不变（一条内容，多域分发，不绑平台数）。

---

## 5. 结论

1. Postiz 的 30+ 平台**绝大部分是国际平台**（26 个新增），且多为文章/图文/社区类；
2. 我们不如它多，是因为**路线不同**（Cookie 自动化 vs 官方 API），不是能力问题——我们的国内 10 平台是它没有的护城河；
3. **不整体引入 Postiz**（AGPL 许可证 + 重型架构冲突），而是**按它的已验证清单逐个接入官方 API 适配器**；
4. 首批零门槛 5 个平台（Medium/Dev.to/Hashnode/WordPress/Telegram）可立即启动，同时解决 LinkedIn（官方 API 路径）。