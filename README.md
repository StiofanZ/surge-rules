# surge-rules

个人维护的 [Surge](https://nssurge.com/) 规则集合。每日自动与上游同步，并附加本地补充。

## 规则清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| [`proxy.txt`](./proxy.txt) | DOMAIN-SET | 代理域名集。上游 [Loyalsoldier/surge-rules `proxy.txt`](https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/proxy.txt) + 本地 OpenAI/ChatGPT 白名单补充，自动去重。 |

## 在 Surge 中使用

```ini
[Rule]
DOMAIN-SET,https://raw.githubusercontent.com/StiofanZ/surge-rules/main/proxy.txt,Proxy
```

> `DOMAIN-SET` 内约定：裸域 `example.com` 为精确匹配，`.example.com` 为精确 + 全部子域匹配。

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
├── proxy.txt                      # 合并后的代理规则（机器生成）
├── sources/
│   └── openai-chatgpt.txt         # 本地补充源
├── scripts/
│   └── build.py                   # 合并 + 去重脚本
└── .github/workflows/
    └── update.yml                 # 每日自动更新
```
