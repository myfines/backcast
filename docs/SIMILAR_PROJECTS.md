# 类似产品与开源项目：给团队直接看的清单

研究日期：2026-11-16。核对范围为公开网站、仓库 README / 方法文档 / 文件树及可见许可证。本次未实际安装运行下列项目，宣传中的质量与正确率不视为已独立验证。

## 1. Epistack Labs / Reliability API：产品定位最接近

- [在线查看人物与言论](https://epistacklabs.com/explore)
- [评价方法](https://epistacklabs.com/methodology)
- [公开数据仓库](https://github.com/alexcsaky/reliability-dataset)

从人物公开材料抽取事实、预测、承诺等命题，查询外部证据，形成带原话、来源和判定的人物记录。事实与预测分别评分。这与“让 AI 代替查一个人的历史发言”非常接近。

最值得看：人物报告、原句逐字校验、固定抽样规则、先定核验口径、同时寻找支持和反证、保留不可判定项、按命题类型分开比较。

**开放边界：数据 CC BY 4.0；页面明确核验代码与 prompts 不公开。** 因此可研究产品与方法、按许可引用数据，不能称其为可直接部署的开源核验引擎。网站也说明双模型会出现分歧，模型一致不等于正确；该产品自身的评分不能直接当作真值。

## 2. fluencer-predict-track：最接近知乎合订本工作流

- [仓库](https://github.com/wzj998/fluencer-predict-track)

通过 Agent skill 整理公开历史发言，筛选预测、检查编辑时间、用外部数据核验并输出报告。MIT。原设计以投资/财经为主，当前不是一个通用 Web 后端。

适合参考：作者历史内容 → 候选预测 → 时间资格 → 外部证据 → 带出处的复盘。我们需要增加事实陈述核验、人物级自动任务和非财经案例；不能照搬默认根据搜索第一名认定目标作者等身份匹配做法。

## 3. Trackrecord.info：预测抽取、数据与判定方法较完整

- [网站](https://trackrecord.info/)
- [仓库](https://github.com/TittaDiGirolamo/trackrecord.info)
- [方法](https://github.com/TittaDiGirolamo/trackrecord.info/blob/main/METHODOLOGY.md)

公开仓库包含抽取 prompts、规则/LLM 抽取器、评分包、数据生成与一致性检查。README 定义的用户路径就是：选择一个人 → 看其表现 → 打开一条已判定预测的证据。

适合参考：原始数据链路、原子命题、评分单一事实来源和一致性校验。但当前方法要求人工批准预测判定，与本项目全自动主路径不同；且它偏概率预测，不能替代事实准确性评价。

**没有确认明确的代码复用许可证；目前只研究，不拷入 MIT 主库。**

## 4. On the Record：适合参考“当年说—后来呢”的呈现

- [仓库](https://github.com/okori97/on-the-record)
- [作者 README 所列演示站](https://on-the-record-wine.vercel.app)

一个体量很小的带日期、来源与结果的公开预测记录站。数据以 JSON 整理，条目要由维护者核查后才展示。它是人工维护的记录站，不是输入某人后自动调查的系统。

适合参考：可读的预测卡片、核验状态、原始出处和纠错记录。查看时确认原文来源，不把后来流传的转述直接当作本人预测。

**未确认明确复用许可证；当前仅作为产品参考。演示站本次未进行交互验证。**

## 5. ZhiHu CLI PRO / zhihu-grabber-toolkit：知乎材料组织与覆盖

- [仓库](https://github.com/FlapPearLabs/zhihu-grabber-toolkit)

面向知乎跨问题研究，包含内容捕获、语料分析、证据链、覆盖与验证。README 明确自身也是参赛项目。

适合参考：以“问题—回答—作者”为结构组织材料，披露到底分析了多少内容，以及区分抓取成功与验证通过。

**根仓库标记 AGPL-3.0，内部存在 MIT 模块，必须逐模块确认。** 当前不直接复制。其认证、平台接口可用性与限流行为未经本次实测，不能据 README 就承诺全量读取任意答主。

## 6. zhihu-search：官方开放平台能力的第三方封装

- [仓库](https://github.com/klarkxy/zhihu-search)
- [API 覆盖与边界](https://github.com/klarkxy/zhihu-search/blob/main/docs/API_COVERAGE.md)

提供 Python / CLI / Skill / MCP 接入，覆盖知乎及全网搜索、本人或授权用户数据等。它解决数据访问与集成，不直接评价博主判断力。

适合参考：后端数据适配层与接口能力表。

**实际 LICENSE 是 SATA 2.0，而非 MIT。** 尚未运行或整合；复制前需审阅其具体条件。用户创作权限不能据此扩展为对任意答主的无限历史读取权限。

## 对当前项目的建议

以 Epistack 的“人物历史调查与事实/预测分轨报告”为产品参考，以 fluencer-predict-track 的合订本流程为起点，核查知乎官方/赛事数据通路，再补人物级自动采集与核验任务。Trackrecord 与 On the Record 用来研究数据一致性和结果表达。

现有后端的概率评分不是当前主线的充分实现。优先打通一个真实知乎答主的自动调查，再决定哪些统计指标值得放到首页。

## 许可和实测状态

本次仅阅读公开材料，没有复制上述项目的实现，也没有安装或验证其实际运行效果。文中“适合参考”表示设计价值，不代表已经集成、成熟可用或核验结果可靠。
