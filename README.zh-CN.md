# Be-Ambitious Harness——面向高目标 AI 任务的“规划者 / 执行者 / 验证者”工作流

> 让 AI 智能体把目标定得更高，同时不失控：每个任务设两档目标，昂贵的工作开始前先做一次低成本的关卡检查，再由一个独立的验证者把关——它永远看不到执行者的推理过程。

[English](README.md) · [Русский](README.ru.md) · **简体中文** · [Español](README.es.md)

![场景](https://img.shields.io/badge/%E5%9C%BA%E6%99%AF-6-blue) ![角色](https://img.shields.io/badge/%E8%A7%92%E8%89%B2-%E8%A7%84%E5%88%92%E8%80%85%20%7C%20%E6%89%A7%E8%A1%8C%E8%80%85%20%7C%20%E9%AA%8C%E8%AF%81%E8%80%85-informational) ![评测运行](https://img.shields.io/badge/%E8%AF%84%E6%B5%8B%E8%BF%90%E8%A1%8C-2%2F8%20%E9%A1%B9%E4%BB%BB%E5%8A%A1-yellow) ![语言](https://img.shields.io/badge/%E6%96%87%E4%BB%B6-EN%20%7C%20RU-informational) ![许可证](https://img.shields.io/badge/%E8%AE%B8%E5%8F%AF%E8%AF%81-MIT-lightgrey)

---

## 这是什么：提示工程框架、Claude Code 技能、多智能体工作流

大多数 AI 提示词要的只是一个步骤：*修好这个 bug，做出这个界面，分析这个 CSV*。而你真正想要的结果——*应用不再崩溃，用户顺利完成结账，你弄清了流失率为什么上升*——始终没有说出口，于是模型交付了这一步就停下了。

Be-Ambitious Harness 是一套**提示工程框架与多智能体工作流**，能把任何任务变成一份包含以下内容的提示词：

- **两档目标**——基础结果，外加一个更有雄心的结果，并写明所需的额外工作和主要的不确定性。
- **关卡检查**（gate check）——一项低成本、结果可观察的测试，用来判断进取路径是否值得启动；通过标准在测试运行*之前*就已固定，结果有三种：通过、未通过、数据不足。
- **角色隔离**——规划者（planner）编写提示词，执行者（worker）执行它，验证者（verifier）在只能看到需求、验收标准和证据日志的情况下评判结果。没有人给自己的工作打分。
- **六套场景手册**——设计/UX、数据分析、代码、写作/研究、决策/计划、通用，每套都带有该领域特有的检查项和陷阱。
- **评测集**——8 项测试任务和一张包含 30 项标准的评分卡，让你能发现 Harness 本身什么时候出了问题。目前已运行其中两项，见[状态](#状态已测试的内容)。

它以 **Claude Code 技能**（`/be-ambitious-harness`）的形式发布，提供**英文和俄文**两个版本，也适用于任何能读取一个 Markdown 文件夹的智能体。

**安装：**`git clone https://github.com/alexpiar/be-ambitious-harness.git ~/.claude/skills/be-ambitious-harness`，然后在 Claude Code 中输入 `/be-ambitious-harness`。详细说明及俄文版本见[安装](#安装)。

---

## 缘起

2026 年 10 月 13 日，Anthropic 的工程经理 Felix Rieseberg（曾带领 Claude.ai、Cowork 和 Claude Code Desktop 的工程团队）发表了 [*How to be more ambitious: A tutorial for humans with models*](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/)（《如何更有雄心：写给与模型协作的人类的教程》）。核心观点是：着眼于结果，而不是单个任务；坚持使用业内顶尖团队所用的工具；引入更多学科领域的视角；不要让模型自己评判自己——坚持外部验证。他还分享了一段简短的提示词：*"I want a deeper version of this task, not a bigger one…"*（“我要的是这个任务更深入的版本，而不是更大的版本……”）。

几天之内，社区技能相继出现：[DannyMac180 的 `be-ambitious`](https://github.com/DannyMac180/skills) 封装了这段提示词；[robonuggets/be-ambitious](https://github.com/robonuggets/be-ambitious) 则把高度、深度和广度拆成步骤，然后直接动手完成工作。

这段提示词很出色，但也有局限：它只是一段提示词。一旦加上让雄心变得安全的规则——固定的标准、预算上限、强制验证——就会撞上近期 LLM 研究报告的三种失效模式：

| 失效模式 | 研究怎么说 | Harness 如何应对 |
|---|---|---|
| **约束饱和** | 单次生成中同时存在的约束超过 5–6 条后，可靠的指令遵循就会崩溃；在 15 个模型、k=8 的条件下，单条约束的通过率仍有约 41%，但八条同时满足的比例只有 5.7%（[Vasileva, arXiv:2608.12426](https://arxiv.org/abs/2608.12426)；ICML 2026 研讨会海报） | 每个角色只拿到自己这一步的文件（每个 250–630 词）；结构来自模板，而不是靠上下文里记着的规则 |
| **否定式指令适得其反** | 点名一个禁用词，反而会促使模型把它生成出来；在失败案例中，抑制信号弱 4.4 倍（[Rana，2026 年预印本](https://arxiv.org/abs/2601.08070)；仅测试了一个模型：Qwen2.5-7B-Instruct） | 指令一律采用正面表述：用“只包含模板中的各部分”代替“不要包含分析” |
| **自我偏好偏差** | 无论文本出自谁手，LLM 评审给低困惑度文本的评分都高于人类评估者（[Wataoka et al., NeurIPS 2024 Safe Generative AI Workshop](https://arxiv.org/abs/2410.21819)） | 验证者只看需求、标准、结果和证据，并且最好运行在另一个模型上——真正能改变评审所感知困惑度的正是这一点 |

以上每一条都只基于一项近期研究，把它们套用到智能体指令上是本 Harness 自己的外推。本 Harness 试图在这些限制之内让“更有雄心”依然奏效——而它的评测集正是用来揭示哪里不奏效的。

---

## 原则

### 1. 结果优先于步骤（高度）

每次分析都从这个问题开始：*有了这个结果之后，应该有什么事情变得可能*？修一个 bug 是步骤，“这一类崩溃不再出现”是结果。做一份幻灯片是步骤，“管理层提前一个季度发现问题”是结果。规划者把两者都写出来，并围绕结果来构建提示词。

### 2. 永远设两档目标

**基础档**（baseline bar）是在原有范围内高质量地完成任务。**进取档**（ambitious bar）是以下三种做法之一：更高的质量门槛、消除原因而不是症状，或者用一种更有用的方式达成目标。对每个进取档，规划者都要写明预期收益、额外工作量和主要的不确定性。如果找不到有用的进取档，规划者会直接说明——雄心不等于注水。

### 3. 新任务设学习目标

目标设定研究表明，具体且有难度的目标胜过“尽力而为”（[Locke & Latham, 2002](https://med.stanford.edu/content/dam/sm/s-spire/documents/PD.locke-and-latham-retrospective_Paper.pdf)）。但如果任务首先需要获取新的知识或策略，具体且有难度的*绩效*目标可能还不如“尽力而为”，而具体且有难度的*学习*目标则效果更好（Seijts & Latham, 2001; 2005）。批评者补充说，延展目标会让关注面变窄，并诱发走捷径（Ordóñez et al., 2009）。因此，对于不熟悉的任务，进取档被表述为**学习目标**（“弄清时间花在了哪里”），附带的任何数字都只是**假设**（“p95 ≤ 300 ms”），而不是承诺。Rieseberg 那个“要 5 秒而不是 10 秒？那就要 200 ms”的技巧就用在这里——作为附带可行性检查的实验性目标，这样它就不会再被当作“没有依据”而被过滤掉。

### 4. 关卡：先拿低成本的证据，再做昂贵的工作

进取分支启动之前，**关卡检查**要回答两个问题：额外的结果真的有价值吗？用现有的手段能达到吗？一个关卡只有具备以下五个属性，才算完整定义：

1. 一个具体的动作及其所需的材料；
2. 可观察的结果（一个数字、一个事实、一件产物——而不是一个观点）；
3. 在检查运行*之前*就固定下来的通过标准；
4. 成本上限，**要远小于它所解锁的工作量**（花 20 分钟做一个能省下一周的测试完全没问题，即使基础任务本身只要 5 分钟）；
5. 针对全部三种结果的行动：**通过、未通过、数据不足**。

模棱两可的情况属于第三种结果，永远不能算作第一种。标准只能照着读，不能改：如果发现标准不适用，那就是“数据不足”，而不是挪动球门的理由。缺少材料则应在工作开始*之前*向人类提出请求——它不是关卡的结果。

### 5. 范围和预算由人类掌握

关卡可以表明 200 ms 是可以达到的，而且用户能感受到差别。但这值不值得投入一周，取决于预算和优先级——这一点 Harness 从不替你决定。如果关卡通过了，而进取分支的预算尚未设定，执行者交付基础结果，**外加**关卡结果和成本估算，然后把决定权交还给人类。“ambitious extension”（进取扩展）模式只是一种*偏好*，不能替代证据。

### 6. 三个角色，严格分离

| 角色 | 读取 | 产出 |
|---|---|---|
| **规划者** | 任务、背景、模式、一个场景文件 | 一份由七个部分组成、内含关卡的提示词 |
| **执行者** | 提示词、材料、场景文件中的“给执行者”部分、它自己的指令文件 | 结果和证据日志 |
| **验证者** | 提示词的第 2 和第 6 部分、结果、材料、证据日志 | 裁定：接受 / 附意见接受 / 拒绝 |

验证者不做修改。执行者不能代替验证者给自己打分。验证者最好运行在**另一个模型**上——用同一个模型做验证，从结构上就只能算部分验证。

### 7. 模板优于规则

执行者的提示词有**七个固定部分**（目标与结果；逐字照抄的强制要求；材料；关卡；方法；验收标准与验证；完成与报告）。结构靠骨架来保证，而不是靠一串模型必须时刻记在心里的“务必……”规则。交接之前先过一遍预检清单；人类看到任何东西之前，先过一遍运行后清单。

### 8. 验证必须独立，否则就不是验证

验收标准衡量的是目标本身，而不是一个方便的替代指标。每份提示词都包含一项证伪测试（“什么样的观察结果能证明这是错的？”），并写明什么行为算作钻指标的空子。独立验证的手段按优先级排序：执行者可以运行的工具或测试；外部基准；留出数据；另一种测量方法；复现。另一个智能体**如果执行了这类检查**，就是有用的——同意答案并不是检查。

### 9. 领域知识由场景承载

六套手册按*结果落在哪里*来分流，而不是按主题。每套手册都给出四个分析要点的提示、典型陷阱、一个“给执行者”部分，以及一个两档目标的完整示例。设计/UX 手册在画第一个像素之前先看漏斗数据；数据手册把留出测试集作为执行者记录的第一个动作；代码手册先写会失败的测试，再做修复。

### 10. Harness 自我检验

`evals/` 中有六项任务（每个场景一项）和两个陷阱：缺少材料，以及一个以微弱差距未达阈值的关卡（AUC 0.60 对 0.65；10 次运行中 8 次对 9 次）。这些任务检查的是光靠阅读无法确认的东西：执行者是否从关卡开始？测试是否写在修复之前（T3）？有没有人悄悄降低了标准（L2）？

---

## 任务如何流转

```
 人类 ──▶ 任务 + 背景 + 模式
              │
              ▼
        ┌──────────┐   scenarios/_index.md
        │  规划者  │──▶ 选择场景
        └──────────┘
              │  分析（≤500 词）→ 问题（≤3）→ 提示词（7 个部分）
              ▼
        checklists/pre-flight.md       ◀── 任一项为“否” → 退回规划者
              │
              ▼
        ┌──────────┐   新会话：提示词、材料、它自己的指令文件——绝不给分析
        │  执行者  │──▶ 先过关卡 → 记录结果 → 进入分支 → 执行工作 → 报告
        └──────────┘
              │
              ▼
        ┌──────────┐   新会话，尽可能换用另一个模型
        │  验证者  │──▶ 亲自测量各项标准 → 证伪测试 → 裁定
        └──────────┘
              │
              ▼
        checklists/post-run.md ──▶ 给人类的五行摘要 ──▶ 接受 / 返工 / 停止
```

---

## 场景

| 场景 | 结果载体 | 关卡示例 |
|---|---|---|
| `design-ux` | 界面、流程、原型、设计系统 | 来自分析系统的分步漏斗；3–5 段会话录屏 |
| `data-analysis` | 发现、指标、模型、数据报告 | 在 20% 的留出集上，基线模型达到 AUC ≥ 0.6 |
| `code-engineering` | 可运行的代码、修复、功能、基础设施 | bug 在 ≥9/10 次运行中复现；某一个函数占剖析时间的 ≥50% |
| `writing-research` | 文章、综述、文档、演讲 | 在时间限制内找到 ≥2 个一手来源 |
| `decision-plan` | 决策、计划、路线图、优先级排序 | 用 5 次对话或上个月的数据检验关键假设 |
| `generic` | 其他任何东西 | 最便宜的那个动作——做完之后就能看清昂贵的路径值不值得走；或者“无关卡，走基础档” |

---

## 状态：已测试的内容

**关卡检查，2026 年 10 月 21 日**——[完整记录](evals/runs/2026-10-21-gate/)。两项评测任务（T3：代码；L2：用户流失数据集上的“标准 vs 数据”陷阱），在同一个模型上让本 Harness 与单一技能 [robonuggets/be-ambitious](https://github.com/robonuggets/be-ambitious) 对比，由运行在另一个模型上的盲评评分者打分。规程和通过标准在第一次运行之前就已提交。

- 本 Harness 在两项任务中都**没有触发任何失败条件**。单一技能**在 T3 中触发了三条中的两条**：在“keep scope”（保持范围）模式下提出了多级进取计划，以及在写测试之前就修改了源代码。
- 在 L2 中，关卡没有达到固定的阈值（ROC AUC 0.548 对 0.65）。执行者记录为“未通过”，没有改动标准，交付了基础档的模型（0.740 对静态属性的 0.537）；验证者用自己的那份数据副本重新计算了每一个数字——差异为零。
- **重要的保留意见**：两次都是单一技能给出了技术上更深入的结果——T3 中的 locale 解析器更完整，L2 中的分析更丰富。本 Harness 胜在纪律（先测试后修复、范围与要求一致、标准照着读而不是修改），而不是深度。
- 两项任务，各运行一次：这是冒烟测试，不是基准测试。盲评只是部分盲评。这些运行用的是俄文文件；英文译本尚未进行过行为层面的运行。
- 这次运行暴露了本 Harness 的一个缺陷：验证者拿不到关卡标准（提示词的第 4 部分），因此无法对照提示词核对它。修复尚待完成。

**尚未运行**：T1、作为独立任务的 T2、T4–T6、L1。

**已知不足**（来自最初的笔记）：
- 没有面向多模态任务（视频、音频、3D）的场景。
- 没有支持多日任务、连续设置多个关卡的机制。
- 在另一个模型上运行验证者只是一项建议；如何选择模型取决于你的环境。

---

## 安装

**Claude Code，英文文件**——直接克隆到你的技能目录：

```bash
git clone https://github.com/alexpiar/be-ambitious-harness.git ~/.claude/skills/be-ambitious-harness
```

Harness 文件只有英文和俄文两种版本；本 README 已译为简体中文。

**Claude Code，俄文文件**——原始版本位于 `ru/`：

```bash
git clone https://github.com/alexpiar/be-ambitious-harness.git /tmp/be-ambitious-harness
cp -r /tmp/be-ambitious-harness/ru ~/.claude/skills/be-ambitious-harness
```

如果只用于单个项目，请改为放在项目内的 `.claude/skills/be-ambitious-harness/`。之后在任意会话中输入 `/be-ambitious-harness`，或者直接说 *"make this task deeper"*（“把这个任务做得更深入”）。如果你还装了社区的某个 `be-ambitious` 技能，请用全名调用本技能——`/be-ambitious` 会调用到他们的技能。

**其他任何智能体**——把 `SKILL.md` 指定为入口即可。所有内容都是纯 Markdown，没有需要运行的代码。

---

## 快速开始

1. 给规划者提供四项信息：**任务**；**背景**（结果给谁用、材料、截止时间、强制要求）；**模式**，可选 `keep scope`（保持范围）、`ambitious extension`（进取扩展）或 `recommend`（推荐），默认 `recommend`；以及**分析后暂停**，可选 `yes` / `no`，默认 `no`。
2. 阅读分析和 ≤3 个问题。回答问题，或者接受标记为 `[...]` 的假设。
3. 在一个新会话中，把提示词连同材料交给执行者。
4. 在另一个新会话中，把第 2 和第 6 部分、结果以及证据日志交给验证者。
5. 运行 `checklists/post-run.md`，然后做出决定。

**第一次调用长什么样**（Claude Code）：

```
/be-ambitious-harness

Task: 商品目录页加载要 5 秒。把它变快。
Context: Node/Postgres 单体应用，仓库已附上，我可以提供一份生产数据库副本。截止时间：本 Sprint。
Mode: recommend
Stop after analysis: yes
```

规划者会回复一份 ≤500 词的分析（任务类型、两档目标、关卡设计、所选方案）、最多三个问题，以及一个包含七个编号部分的提示词块。设置 `Stop after analysis: yes` 时，它会等你回答之后再定稿提示词。

已记录运行中的真实输出（俄文）：[规划者的分析与提示词](evals/runs/2026-10-21-gate/T3-A/planner-output.md)、[带关卡记录块的执行者日志](evals/runs/2026-10-21-gate/L2-A/journal.md)、[验证者的裁定](evals/runs/2026-10-21-gate/L2-A/verdict.md)。在代码任务上，完整走完三个角色约用时 15 分钟、约 24.5 万个子智能体 token；在数据任务上约用时 50 分钟、约 35 万个 token。

并不是每个任务都需要它：五分钟就能做完的任务，跳过 Harness 即可。当进取分支要花一天或更长时间时，它才物有所值。

---

## 示例：一个任务，两档目标

**任务**：“商品目录页加载要 5 秒。把它变快。”

**基础档**：做性能剖析，消除主要瓶颈，在同一测试环境上做前后对比基准测试（≥5 次运行，取中位数和 p95，冷启动与热启动分开统计），并加上一个针对响应时间的回归测试。

**进取档（作为学习目标）**：把时间花在哪里弄得足够清楚，以便在冷启动下达到 p95 ≤ 300 ms——这个数字只是假设。

**关卡**：对生产环境副本做性能剖析；**通过标准**：某一层（数据库、序列化、渲染）占用 ≥70% 的时间，*并且*能在 ≤2 天内、在不改动 API 的前提下被替换；**成本上限**：2 小时。
- 通过且已设定预算 → 进取分支。
- 通过但未设定预算 → 基础结果 + 剖析数据 + 成本估算；由人类决定。
- 未通过或数据不足 → 基础结果；报告学到了什么。

**验证**：验证者重新运行基准测试，回退修复以确认回归测试会失败，并检查有没有把“热启动”的数字当成“冷启动”的数字报告。

---

## 仓库结构

```
be-ambitious-harness/
├── SKILL.md                 路由：信息收集 + 六个步骤（0–6）、规则、文件地图
├── agents/
│   ├── planner.md           四要点分析 → 提示词
│   ├── worker.md            执行顺序、证据日志
│   └── verifier.md          验证顺序、裁定
├── core/
│   ├── gate.md              关卡：5 个属性、3 种结果、先后顺序
│   ├── prompt-template.md   7 个部分 + 骨架
│   └── report-format.md     执行者报告、验证者裁定、给人类的 5 行摘要
├── scenarios/               _index.md + 六套场景手册
├── checklists/              pre-flight.md、post-run.md
├── evals/                   tasks.md（6 项 + 2 个陷阱）、scorecard.md（30 项标准）
│   └── runs/                已记录的运行：规程、测试夹具、日志、评分
├── ru/                      俄文原始版本——相同结构
├── README.md · README.ru.md · README.zh-CN.md · README.es.md
└── LICENSE · CITATION.cff
```

---

## 常见问题

**怎样让 AI 智能体更有雄心，又不至于跑偏？**
定出两档目标，在两者之间放一道低成本、标准固定的关卡，并把预算决定权留给人类。一句话概括，这就是整个 Harness。

**为什么不应该让 LLM 给自己的工作打分？**
因为在 Wataoka 等人的研究中，LLM 评审给低困惑度文本（也就是评审自己“眼熟”的文本）打的分高于人类评估者，无论这些文本是不是它们自己写的；其中 GPT-4 的自我偏好最强（[Wataoka et al.](https://arxiv.org/abs/2410.21819)）。在本 Harness 中，验证者永远看不到执行者的推理过程，理想情况下还运行在另一个模型上。

**七个部分的提示词是不是太长了？**
对人来说长，对模型来说短：每个角色只读几个简短的文件（每个 250–630 词），外加自己的输入。另一种做法——用一段提示词承载全部规则——会越过 5–6 条约束的阈值，而指令遵循正是在越过这个阈值后开始崩溃。

**AI 智能体的“harness”是什么？**
一组文件和检查清单，用来固定*谁读什么、按什么顺序读、怎样才算完成*——这样结果的质量取决于流程，而不是取决于模型能否一次记住所有东西。

**它能配合 GPT / Gemini / 本地模型使用吗？**
这些文件都是纯 Markdown，没有任何厂商专属语法。`/skill` 入口是 Claude Code 的约定；任何能读取文件夹的智能体都可以按照 `SKILL.md` 执行。目前已记录的运行只用过 Claude 模型。

**它和社区的 `/be-ambitious` 技能有什么区别？**
Rieseberg 发布的是一段提示词，而不是技能。DannyMac180 的 `be-ambitious`（2026 年 10 月 15 日）封装了这段提示词：它针对任务所在领域回答四个问题，然后改写你的提示词。robonuggets/be-ambitious（2026 年 10 月 17 日）把高度、深度和广度拆成步骤，然后直接完成工作。本 Harness 在此基础上增加了带三种结果的关卡、配有独立验证者的角色隔离、场景手册、检查清单，以及带有已记录运行的评测集。

**应该用哪种语言的版本？**
两个版本结构相同。`ru/` 中的俄文文件是原始版本，最早记录的运行用的就是它们；英文文件是译本，已核对过与原文的结构一致性。无论选哪个版本，任务和输出都可以使用任何语言。

---

## 设计背后的研究

- F. Rieseberg — [How to be more ambitious: A tutorial for humans with models](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/)（2026 年 10 月 13 日）。高度 / 深度 / 广度；外部评审；最初的那段提示词。
- M. I. Vasileva — [Large Language Models Can Follow Instructions, But Not Many at Once: Phase Transitions in Compositional Constraint Satisfaction](https://arxiv.org/abs/2608.12426)（arXiv，2026；ICML 2026 的 2nd Workshop on Compositional Learning 海报）。同时存在的约束超过 5–6 条后，可靠性就会崩溃。
- S. Rana — [Semantic Gravity Wells: Why Negative Constraints Backfire](https://arxiv.org/abs/2601.08070)（arXiv 预印本，2026）。点名一个禁用词，反而会诱发它。
- K. Wataoka, T. Takahashi, R. Ri — [Self-Preference Bias in LLM-as-a-Judge](https://arxiv.org/abs/2410.21819)（NeurIPS 2024 Safe Generative AI Workshop）。评审偏爱低困惑度的文本。
- E. Locke, G. Latham — *Building a practically useful theory of goal setting and task motivation: A 35-year odyssey*（American Psychologist，2002）。
- G. Seijts, G. Latham — *The effect of distal learning, outcome, and proximal goals on a moderately complex task*（Journal of Organizational Behavior，2001）；*Learning versus performance goals: When should each be used?*（Academy of Management Executive，2005）。
- L. Ordóñez, M. Schweitzer, A. Galinsky, M. Bazerman — *Goals Gone Wild: The Systematic Side Effects of Overprescribing Goal Setting*（Academy of Management Perspectives，2009）；Locke & Latham 在同一期中对其提出了反驳。
- N. Edwards, S. Schuster — [Ask or Assume? Uncertainty-Aware Clarification-Seeking in Coding Agents](https://arxiv.org/abs/2603.26233)（arXiv，2026）。在需求描述不充分的 SWE-bench Verified 上，把“识别需求欠明确之处”与“执行代码”拆开后，一个具备不确定性感知的智能体的解决率从 61.2% 提高到 69.4%（OpenHands + Claude Sonnet 4.5）；而一个更简单的、基于提示的交互式基线达到了 70.4%。

---

## 参与贡献

欢迎提交 Issue 和 Pull Request。最有价值的贡献依次是：

1. **评测运行**。运行 `evals/tasks.md` 中的任意一项任务，填好评分卡，然后提一个标题为 `eval: T3 — <what broke>` 的 Issue。真实的失败案例比观点更有价值。`evals/runs/` 展示了如何记录一次运行。
2. **新场景**。如果 `generic.md` 对你的领域来说明显太单薄，那就说明需要一套新的场景手册——请按照 `scenarios/_index.md` 中的结构来写。
3. **翻译**。欢迎新增语言；在某个译本通过评测之前，`ru/` 始终是唯一可信来源。
4. **研究**。如果某篇论文会改变上面的某条原则，请提一个 Issue，并用一句话概括它改变了什么。

请保持文件简短：本 Harness 依赖的正是每次只给每个角色少量指令。

---

## 路线图

- [x] 所有 Harness 文件的英文翻译
- [ ] 全部八项任务的评测运行记录——T3 和 L2 已完成，见[状态](#状态已测试的内容)
- [ ] 面向多模态任务（视频、音频、3D）的场景
- [ ] 支持跨越多天任务的多关卡机制
- [ ] 适用于 Claude Code 子智能体的“验证者运行在另一个模型上”方案

---

## 作者

由 **Chernov Alexandr**（@alexpr）创建。如果你在本 Harness 的基础上进行开发，GitHub 的“Cite this repository”按钮会根据 `CITATION.cff` 生成现成的引用格式。

如果本 Harness 帮你省下了一天白费的 AI 工作，点个 ⭐ 能帮更多人找到它：GitHub 的许多排行榜和 Explore 页面都依赖星标数。

---

## 许可证

MIT——见 [`LICENSE`](LICENSE)。

本项目与 Anthropic 没有关联，也未获得其认可。Claude 和 Claude Code 是 Anthropic, PBC 的商标。
