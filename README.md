<h1 align="center">痛点雷达 · Pains</h1>

<p align="center">
  <strong>每天从公开讨论里找“反复出现、现有方案没解决好、能用代码解决”的问题，给想做产品的独立开发者一个有证据、分数不虚高的选题台账。</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/deploy-GitHub%20Actions%20+%20Pages-111111?style=flat-square" alt="Deploy: GitHub Actions + Pages">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/models-OpenRouter%20+%20DeepSeek%20fallback-111111?style=flat-square" alt="Models: OpenRouter with DeepSeek fallback">
  <img src="https://img.shields.io/badge/tests-unittest-111111?style=flat-square" alt="unittest regression suite">
</p>

<p align="center">
  <a href="https://ycl-2004.github.io/Pains/">网站</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#model-strategy">模型策略</a> ·
  <a href="#deployment">部署</a> ·
  <a href="#第-0-期基线三份研究怎么合并的">基线合并</a> ·
  <a href="#known-limitations">Known limitations</a>
</p>

这个项目把三个 agent 各自做过的痛点研究（`claude-pp`、`codex-pp`、`agy-pp`）合并成一个能持续运行的版本。它回答的问题不是“今天什么火”，而是：**哪一群具体的人在反复为某件事挣扎？现有方案为什么帮不了他们？值不值得花一周去验证？**

项目分两部分：一条 Python 管线负责抓取、初筛、聚类、打分和更新台账；一个 React 静态网站负责展示台账。和 [ai-news-radar](https://github.com/ycl-2004/ai-news-radar) 的做法一样：GitHub Actions 定时运行管线，把数据提交回仓库，再把网站发布到 GitHub Pages。整个项目不需要服务器。

> **状态：** 已有两次真实模型试跑（2026-09-13），每次初筛 30 条；这两次没有触发竞品联网核查。当前实现已补证据与状态校验，并加入业务社区来源。新逻辑经过离线回归测试，尚未重新跑付费模型链路。具体规则见 [商业证据与可靠性决策](docs/decisions/001-buyer-evidence-and-reliability.md)。

## Quick start

### 研究工作台

网站已采用 YC 酒红 / 丹宁蓝 / 纸色视觉：机会简报、桌面双栏证据底稿、手机独立详情，以及本地验证记录。筛选可通过 URL 分享；验证记录仅保存在当前浏览器，可导出/导入 JSON 备份，不会同步或改变公共评分。设计与数据契约见 [研究工作台说明](docs/research-desk.md)，商业判断校准见 [评估样本](evals/README.md)。

### 在 GitHub 上跑（推荐）

1. **加 Secrets**（Settings → Secrets and variables → Actions → Secrets）：
   - `OPENROUTER_API_KEY`：主力模型。
   - `DEEPSEEK_API_KEY`：可选，只有用 DeepSeek 官方 API 兜底时才需要。
2. **加 Variables**（同一页的 Variables 标签）：

   | 变量 | 例子 | 说明 |
   |---|---|---|
   | `RADAR_TRIAGE_MODELS` | `vendor/cheap-a,vendor/cheap-b` | 初筛用，按优先级排列，便宜快速的模型放前面 |
   | `RADAR_ANALYZE_MODELS` | `vendor/strong-a,vendor/strong-b` | 聚类和打分用，放推理能力强的模型 |
   | `RADAR_FALLBACK_MODELS` | `deepseek:deepseek-flash` | 追加在每个阶段的模型链末尾 |
   | `RADAR_SOLUTION_MODELS` | 不填 | 现有方案联网核查用，不填时沿用分析模型 |
   | `RADAR_MAX_COST_USD` | `3` | 每期软预算，不填默认 3；硬额度在服务商设置 |

3. **跑一次**：Actions → `Update pain radar` → Run workflow。勾上 `force`，并把 `limit` 填成 `30` 先小规模试跑。之后每天 UTC 14:17 自动运行。

### 在本机跑

需要 [uv](https://docs.astral.sh/uv/) 和 Node.js 20+。

```bash
uv sync
uv run python -m radar seed                  # 用第 0 期基线初始化台账
cd web && npm install && npm run dev         # 打开 http://localhost:5173
```

```bash
export OPENROUTER_API_KEY=sk-or-...
export RADAR_TRIAGE_MODELS=vendor/cheap-a RADAR_ANALYZE_MODELS=vendor/strong-a
export RADAR_FALLBACK_MODELS=deepseek:deepseek-flash DEEPSEEK_API_KEY=sk-...
uv run python -m radar run --limit 30 --max-cost 1
```

`npm run dev` 只导出现有数据后启动网站，不调用付费模型。需要研究更新时明确运行 `npm run refresh` 或 `uv run python -m radar run`。

### Commands

| 命令 | 做什么 | 需要模型 |
|---|---|---|
| `radar seed [--force]` | 用 `data/seed/baseline-2026-09-12.json` 初始化台账 | 否 |
| `radar fetch [--source NAME]` | 只抓取和规则预筛，打印结果，不改台账 | 否 |
| `radar run [--limit N] [--max-cost USD] [--skip-solution-check]` | 完整跑一期 | 是 |
| `radar refresh [--stale-after 20h] [--strict]` | 过期且模型可用时跑一期，否则只导出；`--strict` 让运行失败时返回非零退出码 | 可选 |
| `radar export` | 导出 `web/public/data/radar.json` | 否 |
| `radar status` | 台账概况、前 5 名、最近一期花费、模型是否已配置 | 否 |

## Model strategy

所有模型调用都经过 `radar/llm/client.py` 里的 `LLM.complete()`。三个阶段（初筛、分析、现有方案核查）共用同一套降级和记账逻辑。

**模型写法。** `vendor/model` 表示走 OpenRouter；`deepseek:deepseek-flash` 表示走 DeepSeek 官方 API。只有已知的服务商名才算前缀，所以 OpenRouter 的 `:free` 这类后缀不会被误判。

**降级顺序。** 以 `RADAR_ANALYZE_MODELS=a/x,b/y` 加 `RADAR_FALLBACK_MODELS=deepseek:deepseek-flash` 为例：

1. **OpenRouter 负责服务端故障。** 连续的 OpenRouter 模型合成一次请求（`models: ["a/x", "b/y"]`）。报错、限流、宕机、上下文超长、内容审核拦截时，OpenRouter 自动换下一个模型，只按最终实际使用的模型计费。
2. **我们负责输出质量。** OpenRouter 不会因为输出格式不对而降级。所以输出被截断、不是 JSON、或者不符合结构时，代码会换到下一组模型，也就是 DeepSeek。
3. **DeepSeek 官方 API 只支持 JSON 模式，不校验结构。** 所以 schema 会写进提示词，返回后再用 pydantic 校验。
4. **软预算控制。** 调用前按目录价格与输入大小保守估计，限制输出 token；余额不足跳过该路由。实际费用达到预算后不再调用，已完成部分保存。服务商搜索费、定价变化和请求异常仍可能使实际扣费超过估计；硬额度需在服务商设置。

**当前配置**（仓库 Variables，按价格优先排列；随时可以在 Settings 里改，不用改代码）：

| 位置 | 初筛 `RADAR_TRIAGE_MODELS` | 分析 `RADAR_ANALYZE_MODELS` | 输出方式 |
|---|---|---|---|
| 1 | `nvidia/nemotron-3-super-120b-a12b:free` | `openai/gpt-5.6-luna` | 严格 JSON Schema（初筛这一格免费） |
| 2 | `qwen/qwen3.7-flash` | `z-ai/glm-5.3-flash` | 初筛：JSON 模式（Qwen 只有阿里云一家服务商，不支持严格 schema）；分析：严格 JSON Schema |
| 3 | `openai/gpt-5.6-luna` | — | 严格 JSON Schema |
| 4 | `z-ai/glm-5.3-flash` | — | 严格 JSON Schema |
| 兜底 1 | `deepseek/deepseek-v4.1-flash`（经 OpenRouter） | 同左 | 严格 JSON Schema |
| 兜底 2 | `deepseek:deepseek-flash`（DeepSeek 官方 API） | 同左 | JSON 模式 |

2026-09-13 两次试跑后做了调整：
- **初筛去掉了 `nex-agi/nex-n2.5-mini:free`**：它一直输出到 16000 token 上限被截断，最后还是要降级。
- **分析去掉了 Qwen**：分析的结构比较复杂，Qwen 只能用 JSON 模式、靠提示词约束格式，这次输出不合格，白白多花一次调用。

**免费模型只放在初筛。** 初筛只判断“是不是痛点”，调用次数最多，用免费模型最省钱。分析决定台账质量：降级只在出错或格式不对时触发，免费模型输出格式合法但判断质量差时，结果会直接写进台账，所以分析仍用付费链。

**免费模型的限制：** 每分钟最多 20 次。每天的上限取决于 OpenRouter 账户累计充值：不到 10 美元是 50 次，满 10 美元是 1000 次。一期大约调用 17 次。免费模型随时可能下架或限流，出问题时会自动降级到后面的付费模型。MiniMax M3 目前就没有免费版了（2026-09-13 核对 OpenRouter 模型目录），它的收费版比上面几个模型都贵，所以没有放进链里。

**请求怎么发。** 每期第一次调用前，会读一次 OpenRouter 的公开模型目录，按每个模型的 `supported_parameters` 选择输出方式；目录读不到时，全部按严格结构化输出请求。发给 OpenRouter 的请求会带上：

- 支持 `structured_outputs` 的模型：`response_format: json_schema` 并开启 `strict`，要求输出严格符合结构。相邻且支持的模型合成一个 `models` 列表，一次请求发出。
- 不支持的模型（例如 Qwen3.7 Flash）：`response_format: json_object`，schema 写进提示词，返回后在本地校验。
- `provider.require_parameters: true`，只路由到支持本次请求参数（JSON Schema 或 JSON 模式）的服务商。
- `response-healing` 插件，修复多余逗号、Markdown 代码块包裹等小格式问题。
- 现有方案核查时，另加 `web` 插件（最多 5 条搜索结果）；DeepSeek 官方 API 没有联网能力，这一步会跳过它。

**费用记账。** OpenRouter 在每个响应的 `usage.cost` 里直接返回扣费金额，按这个数记账。DeepSeek 官方 API 不返回费用，按官网价格表的高峰时段、未命中缓存价格估算，宁可偏高。每次降级都会写进本期报告的 `notes`。

## How it works

```
fetch        Make / n8n / WooCommerce + HN / GitHub / V2EX / Stack Exchange，有限条数采样
  ↓          跳过已判断版本；每次最多复查 5 条旧证据，每条成功复查至少间隔 7 天；失败退避 1/2/4/7 天
prefilter    中英文痛点关键词 + 高互动无条件保留（目的是不漏，不负责判断）
  ↓
triage       每批 20 条；业务来源双份轮询名额；保留反证，区分付款方、预算与损失
  ↓
deepen       给互动最高的 40 条拉高赞回复（变通做法和付费信号大多在回复里）
  ↓
analyze      RADAR_ANALYZE_MODELS：并入已有簇或新建簇、写反方论证、打分、写分数变化理由、挑出 Top 3
  ↓
solution     RADAR_SOLUTION_MODELS + OpenRouter web 插件，对新簇和分数变化 ≥ 1 的簇查竞品，每期最多 3 个
check        每周到期也触发；搜索引用必须可对应；已解决则降级，新簇先观察
  ↓
ledger       data/ledger.json、data/runs/<run_id>.json、data/ledger-history/<run_id>.json
  ↓
export       web/public/data/radar.json → 静态网站
```

### Data sources

| 来源 | 抓什么 | 实测（2026-09-13，72 小时窗口） |
|---|---|---|
| Make Community | 公开 RSS 最新主题；补正文、回复和可用的解决状态 | RSS 200，返回 30 条（订阅条数，不等于 72 小时总量） |
| n8n Community | 公开 RSS 业务自动化求助；卖服务广告在初筛排除 | RSS 200，返回 30 条 |
| WooCommerce 商家支持 | WooCommerce 与 PDF 发票／装箱单插件的公开支持订阅 | 两个 feed 均 200，各返回 30 条 |
| Hacker News | Algolia 官方 API：Ask HN、分数 >150 的故事、9 个痛点短语的评论（`typoTolerance=false`） | 抓到 163 条，预筛后 129 条 |
| GitHub Issues | 限定 8 个仓库，按近期更新时间采样（含旧 issue），保留关闭状态；每仓库最多 30 条 | 原创建时间查询曾抓到 126 条；新查询覆盖范围不同，不直接比较 |
| V2EX | 公开 v1 接口：最新、最热，以及 qna / create / ideas / programmer 节点 | 抓到 58 条，预筛后 34 条 |
| Stack Exchange | Software Recommendations、Web Applications 的新问题；Super User 里含 workaround / manually 的问题 | 抓到 4 条，预筛后 3 条 |

**没有 Reddit。** [官方政策](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy)要求 API 访问获批，商业使用需明确书面批准；当前不把它作为自动采集依赖。历史基线里的 Reddit 证据不代表现在能自动复查。

**业务优先不等于保证赚钱。** 每轮 Make、n8n、WooCommerce 各取两条，其他来源各取一条；来源内部先看成本/行为语言，再看互动。付款方、原文预算或购买证据、当前成本分开记录，缺失项显示待验证。至少两条需求 URL 与行为证据、近期方案核查达标，才进入“优先验证候选”；不同 URL 仍不等于不同买家。

## Deployment

`.github/workflows/update-radar.yml` 有三个 job：

| Job | 什么时候跑 | 做什么 |
|---|---|---|
| `update` | 每天定时，或手动触发 | 跑单测 → `radar refresh --strict` → 把 `data/` 和 `web/public/data/` 整个目录提交回 `main` |
| `build` | `update` 成功或被跳过之后 | 检出最新的 `main`，`npm ci && npm run build` |
| `deploy` | `build` 成功之后 | 用 `actions/deploy-pages` 发布到 GitHub Pages |

几个取舍：

- **推送代码只重建网站。** 改了 `web/`、`data/` 或 `radar/` 并推送到 `main` 时，跳过 `update`，只重新构建和发布。
- **排队，不取消。** `concurrency` 设成排队：跑到一半取消会白花已经调用的模型费用。
- **按整个目录提交。** 同时检查有没有漏暂存的文件。ai-news-radar 出过事故：按文件名白名单提交，漏掉了新生成的文件，网站数据一直停在旧版本。
- **没配模型时不报错。** 只导出现有数据；配好后失败或部分完成会返回非零，CI 先保存已完成数据和报告，再标红，不部署这一期。
- **网站没有公开的刷新按钮。** 公开的刷新入口会让任何人都能触发模型花费；需要立即跑一期时，在 Actions 页手动触发。

## 第 0 期基线：三份研究怎么合并的

三份研究都在 2026-09-12 完成，互相没有读过对方。合并时逐条人工核对，结果写在 [`data/seed/baseline-2026-09-12.json`](data/seed/baseline-2026-09-12.json)，网站“方法与局限”页有完整对照表。

| 来源 | 拿了什么 | 没拿什么 |
|---|---|---|
| `claude-pp` | 采集方法（HN Algolia 查询、痛点短语、按回复数深读）、A/B/C/D 分类、先反方后打分、8 个聚类 + 9 个降级 + 6 个新兴信号 | Reddit 浏览器页内抓取（云端不可用） |
| `codex-pp` | JSON 台账结构、证据独立性规则、10 个簇和 39 条来源、最小验证步骤、11 维评分（合并成 7 维） | 与“缺口”互补重复的“方案质量”维度 |
| `agy-pp` | React 19 + Vite + Tailwind v4 工程配置、筛选 / 搜索 / 展开卡片的信息结构 | 3 个演示原型、关键词 if/else 的“AI 评估器”、“100% 可解”等虚高统计、没有 LICENSE 文件的 MIT 声明 |

合并结果：28 个簇（13 个活跃、1 个观察、14 个降级）、9 个新兴信号、84 条证据（49 条计入需求）、43 条合并记录。几个关键判断：

- `claude-pp` 的“工作流静默失败”和 `codex-pp` 的 OP01“生产自动化结果核验”是同一根因。两者从 r/n8n 和 Make Community 独立发现，合并为 `OP-002`，痛点置信度上调为高。
- `agy-pp` 给“AI 编码代理规则文件漂移”打 8.4 分，`claude-pp` 却把同一主题判为 A（已有多个开源 Skills Manager）。两方冲突，这一项不打分，放进观察（`OP-014`）。
- `agy-pp` 有两条证据的链接只指向 `news.ycombinator.com` 首页，无法追溯，已排除。它的“反爬拦截”和“发票催收”两项，证据是 2023/2024 年的旧帖，已降级。

## Why Pains

- **问题优先于趋势。** 讨论热度高但已经解决的问题分数给低，并保留在“已降级”里，防止以后把同一个伪机会当成新发现。
- **行为优先于观点。** 自建脚本、手工表格、已经在付钱，比“我希望有个工具”更有分量。卖方回帖、产品发布和官方文档一律不计入需求。
- **先反方论证，再打分。** 综合分是写完反方之后的判断，不是加权平均。
- **观察和推断分开。** 证据只写原文里出现的内容（转述加链接），根因和机会假设明确标成推断。

## Data and privacy

- **只读取公开内容。** 所有数据源都是公开只读接口，不发帖、不投票，也不登录任何社区账号。
- **网站只放转述和链接。** 导出的数据不含用户名，也不贴长段原文；版权归原作者和平台。
- **会发给 OpenRouter（以及它路由到的模型服务商）和 DeepSeek 的内容：** 帖子标题、正文摘要（最多 1500 字符）、高赞回复摘要（每条最多 400 字符）和台账摘要。
- **仓库是公开的。** 台账、运行报告、`seen.json`（已判断条目的 ID）都会提交进去；key 只存在 GitHub Secrets 里。

## Project layout

```
Pains/
├── .github/workflows/update-radar.yml   # 定时更新 + 构建 + 发布 Pages
├── radar/
│   ├── models.py            # 数据契约：RawItem、Evidence、Cluster、Ledger、RunReport、LLM 输出结构
│   ├── scoring.py           # 评分维度、A/B/C/D、置信度、阈值；提示词里的评分标准由它生成
│   ├── sources/base.py      # SourceAdapter 抽象基类：HTTP 重试、时间窗口、预筛、去重
│   ├── sources/*.py         # hackernews / github / v2ex / stackexchange
│   ├── registry.py          # 数据源注册表
│   ├── llm/client.py        # 服务商表、模型链解析、降级、结构化输出、花费上限
│   ├── llm/triage.py        # 初筛
│   ├── llm/analyze.py       # 聚类打分 + 现有方案核查
│   ├── llm/prompts/         # 三个阶段的提示词
│   ├── ledger.py            # 台账读写和“把一期分析并入台账”的规则
│   ├── export.py            # 导出网站数据
│   └── cli.py               # python -m radar 各命令
├── data/                    # seed、ledger.json、seen.json、runs/、ledger-history/
├── web/                     # React 19 + Vite + Tailwind v4 网站
└── tests/                   # unittest，不访问网络
```

## Build and test

```bash
uv run python -m unittest discover -s tests   # 含证据、失败状态、预算和业务采样回归测试
cd web && npm run build                        # 输出到 web/dist/
```

测试按层划分：

- `test_contracts.py`：抓取的共用机制只在这里测一次。
- `test_sources.py`：每个适配器只测自己的解析。
- `test_ledger.py`：台账规则。
- `test_llm.py`：用桩客户端测模型链解析、OpenRouter 请求格式、降级、费用记账，以及三个阶段传给模型的内容。

## Known limitations

- **新规则尚未重新进行付费模型试跑。** 旧两次试跑记录仍保留；建议下一次设 `limit=30`，检查各来源入选数、转述和买方证据。
- **OpenRouter 的 `web` 插件能不能和 `json_schema` 结构化输出一起用，官方文档没说明，还没实测。** 如果不兼容，现有方案核查会失败并写进报告，不影响其他阶段。
- **JSON 模式的模型更容易输出不合格。** Qwen3.7 Flash 这类不支持严格 schema 的模型，只能靠提示词约束结构；尤其是分析阶段的结构比较复杂，输出不合格时会降级到 GPT-5.6 Luna，这种情况会写进报告的 `notes`。
- **GitHub 的定时任务不保证准点。** ai-news-radar 写的是每 30 分钟，实际间隔 2–4 小时。
- **来源仍偏软件用户、偏英语。** 已补业务社区，中文只有 V2EX；没有自动覆盖 Reddit、X、Discord 和应用商店评论。
- **断点恢复有边界。** `data/audit/calls/` 保存已完成调用的脱敏输入、输出和费用，本地同输入重试可复用；它不入 Git，新的 CI runner 不会自动恢复。请求中途终止且未拿到响应的费用不能靠缓存追回。
- **分数是判断，不是市场测算。** 没有用户访谈、成交或市场规模数据；LLM 的聚类和转述可能出错，重要结论请点开原文核对。
- **`data/ledger-history/` 会慢慢变大。** 每期大约 110 KB 快照，需要定期清理旧快照。

## License

未设置许可证。引用的帖子和页面版权归原作者和对应平台所有。
