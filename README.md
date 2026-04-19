# surge-rules

个人维护的 [Surge](https://nssurge.com/) 规则集合。每日自动与上游同步，并附加本地补充。

## 规则清单

同一份规则数据同时以两种 Surge 格式发布，内容等价，按自己 Surge 配置里的指令选一个即可：

| 文件 | 类型 | 对应 Surge 指令 | 每行形如 |
| --- | --- | --- | --- |
| [`proxy.txt`](./proxy.txt) | **DOMAIN-SET** | `DOMAIN-SET,<url>,<policy>` | `.example.com` / `example.com` |
| [`proxy.list`](./proxy.list) | **RULE-SET** | `RULE-SET,<url>,<policy>` | `DOMAIN-SUFFIX,example.com` / `DOMAIN,example.com` |

两者都源自 [Loyalsoldier/surge-rules `proxy.txt`](https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/proxy.txt) + 本地 OpenAI/ChatGPT 补充，合并去重后生成。

## 在 Surge 中使用

**A. 使用 DOMAIN-SET 指令（桌面端常用）：**

```ini
[Rule]
DOMAIN-SET,https://raw.githubusercontent.com/StiofanZ/surge-rules/main/proxy.txt,Proxy
```

**B. 使用 RULE-SET 指令（若手机端报 `invalid line`，用这份）：**

```ini
[Rule]
RULE-SET,https://raw.githubusercontent.com/StiofanZ/surge-rules/main/proxy.list,Proxy
```

> **为什么有两份？**
> Surge 的 `RULE-SET` 指令要求每行必须带规则类型前缀（`DOMAIN-SUFFIX,...`），不接受像 `.000webhost.com` 这种前导点的纯域名——否则会报 `invalid line`。`DOMAIN-SET` 指令则相反，只接受纯域名。两份文件同步产出，避免改错指令又改错文件的尴尬。

## 数据来源

1. **上游主数据：** [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules) 的 `release` 分支 `proxy.txt`。
2. **本地补充：** [`sources/openai-chatgpt.txt`](./sources/openai-chatgpt.txt) — 基于 OpenAI 官方[《网络建议》帮助文章](https://help.openai.com/zh-hans-cn/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)所列的 OpenAI/ChatGPT 允许列表域名（含 WorkOS、Statsig、Stripe、Cloudflare Turnstile、Sentry、Datadog RUM 等第三方依赖）。

## 自动更新

- 调度：[`.github/workflows/update.yml`](./.github/workflows/update.yml) 每天 **18:30 UTC**（北京时间次日 02:30）运行。
- 过程：拉取上游 → 合并 `sources/*.txt` → 去冗余（子域被更宽后缀规则覆盖时自动删除）→ 排序写出 `proxy.txt`。
- 仅当规则内容有实质变化时才提交，纯时间戳变化忽略。
- 手动触发：GitHub UI → Actions → "Update proxy.txt" → Run workflow，或 `gh workflow run "Update proxy.txt"`。

## 本地构建

```bash
python3 scripts/build.py
```

要求 Python 3.10+（使用 `pathlib` 与 PEP 604 类型注解）。只使用标准库，无额外依赖。

## 添加新的补充规则

1. 在 `sources/` 下新建 `*.txt` 文件，按 DOMAIN-SET 格式编写（一行一条，`#` 为注释）。
2. 推送到 `main`，GitHub Actions 会自动合并并发布。

## 目录结构

```
surge-rules/
├── proxy.txt                      # DOMAIN-SET 格式（机器生成）
├── proxy.list                     # RULE-SET 格式（机器生成）
├── sources/
│   └── openai-chatgpt.txt         # 本地补充源
├── scripts/
│   └── build.py                   # 合并 + 去重 + 双格式输出
└── .github/workflows/
    └── update.yml                 # 每日自动更新
```
