# surge-rules

个人维护的 [Surge](https://nssurge.com/) 规则集合。每日自动与上游同步，并附加本地补充。

## 规则清单

每个分类都同时以两种 Surge 格式发布，按 Surge 配置里用的指令选对应文件即可：

### proxy — 需要走代理的域名

| 文件 | 类型 | 对应 Surge 指令 |
| --- | --- | --- |
| [`proxy.txt`](./proxy.txt) | **DOMAIN-SET** | `DOMAIN-SET,<url>,<policy>` |
| [`proxy.list`](./proxy.list) | **RULE-SET** | `RULE-SET,<url>,<policy>` |

来源：[Loyalsoldier/surge-rules `proxy.txt`](https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/proxy.txt) + [`sources/proxy/openai-chatgpt.txt`](./sources/proxy/openai-chatgpt.txt)（OpenAI/ChatGPT 官方允许列表）。

### reject — 广告 / 追踪 / 挖矿域名

| 文件 | 类型 | 对应 Surge 指令 |
| --- | --- | --- |
| [`reject.txt`](./reject.txt) | **DOMAIN-SET** | `DOMAIN-SET,<url>,REJECT` |
| [`reject.list`](./reject.list) | **RULE-SET** | `RULE-SET,<url>,REJECT` |

来源：[AdguardTeam/AdguardFilters](https://github.com/AdguardTeam/AdguardFilters)，覆盖该仓库中**所有**面向域名的过滤段：

| 来源文件 | 作用 |
| --- | --- |
| `BaseFilter` / `MobileFilter` / `ChineseFilter` / `JapaneseFilter` 的 `adservers.txt` | 第三方广告网络主域 |
| `BaseFilter` / `ChineseFilter` / `JapaneseFilter` 的 `adservers_firstparty.txt` | 合法网站下挂的广告子域 |
| `SpywareFilter/tracking_servers.txt` | 第三方追踪/分析 |
| `SpywareFilter/tracking_servers_firstparty.txt` | 第一方追踪（埋点域） |
| `SpywareFilter/mobile.txt` | 移动端追踪/遥测 |
| `BaseFilter/cryptominers.txt` | 挖矿脚本域 |

额外与 [SagerNet/sing-geosite](https://github.com/SagerNet/sing-geosite) 的 `geosite-adblock.srs` / `geosite-adblockplus.srs` 保持对齐——这两个 SRS 实际是从 [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) 的 `data/adblock`、`data/adblockplus` 编译而来，构建时直接抓取文本源避免 SRS 二进制解码（它们仅含 `adblockcdn.com` / `getadblock.com` / `adblockplus.org` 三个 AdBlock 工具自家的域名，并非广告黑名单本身）。

构建时仅保留 `||domain.com^` 纯域名屏蔽规则，自动跳过外观过滤（`##`）、URL 路径、正则、`@@` 允许列表、IP 字面量、`$domain=`/`$script`/`$image` 等资源类型修饰符——Surge DOMAIN-SET 无法表达的条目一律丢弃。跨过滤段之间的重复条目与被更宽后缀规则覆盖的子域也会在 dedup 阶段合并。

## 在 Surge 中使用

**A. 使用 DOMAIN-SET 指令（桌面端常用）：**

```ini
[Rule]
DOMAIN-SET,https://raw.githubusercontent.com/StiofanZ/surge-rules/main/proxy.txt,Proxy
DOMAIN-SET,https://raw.githubusercontent.com/StiofanZ/surge-rules/main/reject.txt,REJECT
```

**B. 使用 RULE-SET 指令（若手机端对 `DOMAIN-SET` 报 `invalid line`，用这份）：**

```ini
[Rule]
RULE-SET,https://raw.githubusercontent.com/StiofanZ/surge-rules/main/proxy.list,Proxy
RULE-SET,https://raw.githubusercontent.com/StiofanZ/surge-rules/main/reject.list,REJECT
```

> **为什么每份有两种格式？**
> Surge 的 `RULE-SET` 指令要求每行必须带规则类型前缀（`DOMAIN-SUFFIX,...`），不接受像 `.000webhost.com` 这种前导点的纯域名——否则会报 `invalid line`。`DOMAIN-SET` 指令则相反，只接受纯域名。两种文件同步产出，避免改错指令又改错文件的尴尬。

## 数据来源

1. **上游主数据：** [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules) 的 `release` 分支 `proxy.txt`。
2. **本地补充：** [`sources/openai-chatgpt.txt`](./sources/openai-chatgpt.txt) — 基于 OpenAI 官方[《网络建议》帮助文章](https://help.openai.com/zh-hans-cn/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)所列的 OpenAI/ChatGPT 允许列表域名（含 WorkOS、Statsig、Stripe、Cloudflare Turnstile、Sentry、Datadog RUM 等第三方依赖）。

## 自动更新

- 调度：[`.github/workflows/update.yml`](./.github/workflows/update.yml) 每天 **18:30 UTC**（北京时间次日 02:30）运行。
- 过程：拉取上游 → 合并 `sources/*.txt` → 去冗余（子域被更宽后缀规则覆盖时自动删除）→ 排序写出 `proxy.txt`。
- 仅当规则内容有实质变化时才提交，纯时间戳变化忽略。
- 手动触发：GitHub UI → Actions → "Update rule sets" → Run workflow，或 `gh workflow run "Update rule sets"`。

## 本地构建

```bash
python3 scripts/build.py
```

要求 Python 3.10+（使用 `pathlib` 与 PEP 604 类型注解）。只使用标准库，无额外依赖。

## 添加新的补充规则

- **扩充已有分类：** 在 `sources/<category>/` 下新建 `*.txt`（DOMAIN-SET 格式，一行一条，`#` 为注释）。例如 `sources/reject/my-custom.txt`。
- **新增分类：** 在 `scripts/build.py` 顶部的 `RULE_SETS` 元组里追加一条 `RuleSet(...)`，指定 `sources`（远端源）、`local_dir`（本地子目录）、输出文件名；`parser` 可选 `"domain_set"` 或 `"adguard"`。

推送到 `main` 后 GitHub Actions 会自动合并并发布。

## 目录结构

```
surge-rules/
├── proxy.txt / proxy.list           # proxy 分类（机器生成）
├── reject.txt / reject.list         # reject 分类（机器生成）
├── sources/
│   ├── proxy/
│   │   └── openai-chatgpt.txt       # proxy 本地补充源
│   └── reject/                      # reject 本地补充源（可选）
├── scripts/
│   └── build.py                     # 多规则集合并 + AdGuard 解析 + 双格式输出
└── .github/workflows/
    └── update.yml                   # 每日自动更新
```
