# surge-rules

[Surge](https://nssurge.com/) 规则集合。每日自动与上游同步，并附加本地补充。

## 规则清单

每个分类都同时以两种 Surge 格式发布，按 Surge 配置里用的指令选对应文件即可：

### proxy — 需要走代理的域名

| 文件 | 类型 | 对应 Surge 指令 |
| --- | --- | --- |
| [`proxy.txt`](./proxy.txt) | **DOMAIN-SET** | `DOMAIN-SET,<url>,<policy>` |
| [`proxy.list`](./proxy.list) | **RULE-SET** | `RULE-SET,<url>,<policy>` |

来源：[Loyalsoldier/surge-rules `proxy.txt`](https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/proxy.txt) + [`ruleset/gfw.txt`](https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/gfw.txt) + [`ruleset/telegramcidr.txt`](https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/telegramcidr.txt) + [`includes/proxy/openai-chatgpt.txt`](./includes/proxy/openai-chatgpt.txt)（OpenAI/ChatGPT 官方允许列表）。

`telegramcidr.txt` 是 `IP-CIDR` / `IP-CIDR6`，只能进入 `proxy.list`；`proxy.txt` 是 DOMAIN-SET，不能表达 IP 段。

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

此外还接入 [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) 的 [`data/category-ads-all`](https://github.com/v2fly/domain-list-community/blob/master/data/category-ads-all)——这是 [SagerNet/sing-geosite](https://github.com/SagerNet/sing-geosite) 编译 `geosite-category-ads-all.srs` 所用的上游文本源。构建器递归展开 v2fly 的 `include:` 指令，并严格遵守其 **属性过滤语义**：

- `include:apple @ads` 表示"只纳入 `data/apple` 中带 `@ads` 标签的终端规则"，因此 `apple.com` 主域不会进 reject，只有 `advertising.apple.com`、`iadsdk.apple.com` 等 5 条广告子域会进。
- 过滤通过嵌套 include 链路**求交集**传播（`@ads AND @cn` 等），避免父级过滤被子级忽略。
- 抓取结果带缓存，避免同一文件在多路径下重复下载。

构建时仅保留 `||domain.com^` 纯域名屏蔽规则，自动跳过外观过滤（`##`）、URL 路径、正则、`@@` 允许列表、IP 字面量、`$domain=`/`$script`/`$image` 等资源类型修饰符——Surge DOMAIN-SET 无法表达的条目一律丢弃。跨过滤段之间的重复条目与被更宽后缀规则覆盖的子域也会在 dedup 阶段合并。

上游之外还有 [`includes/reject/*.txt`](./includes/reject) 本地补充，当前包含 [`includes/reject/google-telemetry.txt`](./includes/reject/google-telemetry.txt)：`crashlyticsreports-pa.googleapis.com`（Firebase Crashlytics 崩溃上报端点，与业务功能无关）精确屏蔽。

### direct — 直连域名

| 文件 | 类型 | 对应 Surge 指令 |
| --- | --- | --- |
| [`direct.txt`](./direct.txt) | **DOMAIN-SET** | `DOMAIN-SET,<url>,DIRECT` |
| [`direct.list`](./direct.list) | **RULE-SET** | `RULE-SET,<url>,DIRECT` |

来源：[Loyalsoldier/surge-rules `ruleset/direct.txt`](https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/ruleset/direct.txt) + [`includes/direct/*.txt`](./includes/direct) 本地补充。上游是 Surge RULE-SET 格式，构建器仅转换 `DOMAIN` / `DOMAIN-SUFFIX` 两类域名规则；其它 Surge 规则类型若出现会被跳过，因为 DOMAIN-SET 无法表达。

本地补充当前包含 [`includes/direct/bitget.txt`](./includes/direct/bitget.txt)：`bitget.com`（交易所）与 `bitkeep.app`（Bitget Wallet 移动端，旧品牌 BitKeep）后端均按请求源 IP 判定国家，代理出口在美国会被判为美国并触发地区限制，故强制直连。放进 `includes/direct/` 后它同时被从 `proxy`/`reject` 跨类排除，`bitget.com` 会从上游 `proxy.list` 移除，无需依赖 Surge 配置中 `direct.list` 与 `proxy.list` 的先后顺序。

## 在 Surge 中使用

将 `<OWNER>` 替换为你自己 fork 的 GitHub 用户名（或上游的维护者）。

**A. 使用 DOMAIN-SET 指令（桌面端常用）：**

```ini
[Rule]
DOMAIN-SET,https://raw.githubusercontent.com/<OWNER>/surge-rules/main/reject.txt,REJECT
DOMAIN-SET,https://raw.githubusercontent.com/<OWNER>/surge-rules/main/direct.txt,DIRECT
DOMAIN-SET,https://raw.githubusercontent.com/<OWNER>/surge-rules/main/proxy.txt,Proxy
```

**B. 使用 RULE-SET 指令（若手机端对 `DOMAIN-SET` 报 `invalid line`，用这份）：**

```ini
[Rule]
RULE-SET,https://raw.githubusercontent.com/<OWNER>/surge-rules/main/reject.list,REJECT
RULE-SET,https://raw.githubusercontent.com/<OWNER>/surge-rules/main/direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/<OWNER>/surge-rules/main/proxy.list,Proxy
```

如果同时使用 `reject` 与 `direct`，建议把 `reject` 放在 `direct` 前面，避免广告/追踪域名被更宽泛的直连规则提前命中。

> **为什么每份有两种格式？**
> Surge 的 `RULE-SET` 指令要求每行必须带规则类型前缀（`DOMAIN-SUFFIX,...`），不接受像 `.000webhost.com` 这种前导点的纯域名——否则会报 `invalid line`。`DOMAIN-SET` 指令则相反，只接受纯域名。两种文件同步产出，避免改错指令又改错文件的尴尬。

## 数据来源

1. **proxy：** [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules) 的 `release` 分支 `proxy.txt` + `ruleset/gfw.txt` + `ruleset/telegramcidr.txt` + [`includes/proxy/openai-chatgpt.txt`](./includes/proxy/openai-chatgpt.txt)。
2. **reject：** [AdguardTeam/AdguardFilters](https://github.com/AdguardTeam/AdguardFilters) 的域名型过滤段 + [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) 的 `data/category-ads-all` + [`includes/reject/*.txt`](./includes/reject) 本地补充。
3. **direct：** [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules) 的 `release` 分支 `ruleset/direct.txt` + [`includes/direct/*.txt`](./includes/direct) 本地补充。

## CI / 自动化

三个独立 workflow：

| 文件 | 触发 | 作用 |
| --- | --- | --- |
| [`update.yml`](./.github/workflows/update.yml) | cron 18:30 UTC / `workflow_dispatch` / `push` main | 每日刷新 `proxy.*` + `reject.*` + `direct.*` 并 push |
| [`ci.yml`](./.github/workflows/ci.yml) | `pull_request` / `push` main | 跑 build.py、校验 DOMAIN-SET/RULE-SET 行格式、检测输出漂移 |
| [`automerge.yml`](./.github/workflows/automerge.yml) | `workflow_run` | CI 通过后对受信 PR 执行 squash merge |

### 自动更新节奏

- 调度：`update.yml` 每天 18:30 UTC（北京时间次日 02:30）运行。
- 过程：拉取上游 → 合并 `includes/<category>/*.txt` → 应用排除（`excludes/<category>/*.txt` 加其余各类的 `includes/*` 跨类排除）→ 去冗余 → 排序写出 `*.txt` + `*.list`。
- 仅当规则内容有实质变化时才提交（`git diff -I '^# Generated: '` 忽略纯时间戳漂移）。
- 手动触发：GitHub UI → Actions → "Update rule sets" → Run workflow，或 `gh workflow run "Update rule sets"`。

### 自动合并

`automerge.yml` 触发时机是 **CI workflow 完成后**（`on.workflow_run`），若该次 CI 结果为 `success` 且 PR 满足以下条件之一，就调 `gh pr merge --squash --delete-branch` 直接合入：

1. 作者是仓库主（通过 `github.repository_owner` 上下文解析）
2. 作者是 `github-actions[bot]`
3. PR 上贴了 `automerge` label

**为什么不用 GitHub 原生 auto-merge？**
原生 `gh pr merge --auto`（`enablePullRequestAutoMerge` API）要求目标分支已配置 branch protection rules，否则会抛出 `GraphQL: Pull request Protected branch rules not configured for this branch` 错误。对开源/fork 友好的仓库不应默认强制分支保护，所以本 workflow 改为**等 CI 完成**这个自然信号点。安全性不打折：`workflow_run` 事件始终从默认分支加载 workflow 定义，PR 无法修改 automerge 逻辑再触发自己。

**可选加固（更严格）：**
如果你还是想让 CI 成为**必须通过**的守门员（防止有人手动合并绕过），可以加一个分支保护：Settings → Branches → 为 `main` 添加规则 → Require status checks to pass → 勾选 `CI / Build + validate rule sets`。这与本 workflow 正交共存。

## 本地构建

```bash
python3 scripts/build.py
```

要求 Python 3.10+（使用 `pathlib` 与 PEP 604 类型注解）。只使用标准库，无额外依赖。

## 添加新的补充规则

根目录的六个 `*.txt` / `*.list` 是机器生成产物，**不要手工编辑**——只改下面的 `includes/` 与 `excludes/` 输入，其余交给 CI + `scripts/build.py`。

- **扩充已有分类：** 在 `includes/<category>/` 下新建 `*.txt`（DOMAIN-SET 格式，一行一条，`#` 为注释）。例如 `includes/reject/my-custom.txt`。其中的域名会**并入该分类**，并**从其余各分类中跨类排除**（把某域名强制归到 direct，就会自动从 proxy、reject 移除，不再依赖 Surge 配置里规则集的先后顺序）。同一域名不要同时出现在多个分类的 `includes/`，否则会因相互排除而被从所有分类丢弃（构建器会打 `WARN`）。
- **排除已有分类：** 在 `excludes/<category>/` 下新建 `*.txt`（DOMAIN-SET 格式，一行一条，`#` 为注释），仅从**该分类**移除。精确域名只移除同名精确规则；前导点后缀规则会移除该后缀及其子域。`reject`/`direct`/`proxy` 三类均可用。
- **新增分类：** 在 `scripts/build.py` 顶部的 `RULE_SETS` 元组里追加一条 `RuleSet(...)`，指定 `sources`（远端源）、输出文件名；本地补充与排除目录按约定即 `includes/<name>/`、`excludes/<name>/`。`parser` 可选 `"domain_set"`、`"surge_rule_set"`、`"adguard"` 或 `"v2fly"`。

推送到 `main` 后 GitHub Actions 会自动合并并发布。

## 目录结构

```
surge-rules/
├── proxy.txt / proxy.list           # proxy 分类（机器生成，勿手工编辑）
├── reject.txt / reject.list         # reject 分类（机器生成，勿手工编辑）
├── direct.txt / direct.list         # direct 分类（机器生成，勿手工编辑）
├── includes/                        # 本地补充：并入本类 + 从其余各类跨类排除
│   ├── proxy/
│   │   └── openai-chatgpt.txt       # OpenAI/ChatGPT 强制走 proxy
│   ├── reject/
│   │   └── google-telemetry.txt     # Firebase Crashlytics 上报端点，屏蔽
│   └── direct/
│       └── bitget.txt               # bitget.com / bitkeep.app 强制直连
├── excludes/                        # 仅从对应分类移除
│   ├── proxy/                       # proxy 排除项（可选）
│   ├── reject/                      # reject 排除项（可选）
│   └── direct/
│       ├── fonts-googleapis.txt        # direct 排除项
│       ├── gstatic-signin-assets.txt   # direct 排除项（登录页 gstatic 静态资源）
│       └── recaptcha.txt               # direct 排除项（reCAPTCHA 镜像域）
├── scripts/
│   └── build.py                     # 多规则集合并 + 跨类排除 + 双格式输出
└── .github/workflows/
    └── update.yml                   # 每日自动更新
```
