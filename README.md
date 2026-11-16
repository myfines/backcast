# Backcast · 合订本

**想找有判断力的专业人士？先翻翻他的历史记录。**

公开仓库：[myfines/backcast](https://github.com/myfines/backcast) · MIT License

> 当前分工：后端主开发，前端交给队友 / Claude。现有 `apps/web` 只是可替换的演示原型。

## 队友先看这里

- [前端交接说明](docs/FRONTEND_HANDOFF.md)：接口、页面映射、错误处理、可直接贴给 Claude 的任务说明。
- [OpenAPI 契约](docs/openapi.json) / [TypeScript 客户端](packages/api-client/) / [真实响应示例](docs/examples/)。
- [开源方案研究与评分方法](docs/OPEN_SOURCE_RESEARCH.md)：参考 Metaculus、ForecastBench、forecasting-tools、SIFT 来源评价。
- [协作约定](AGENTS.md) / [Claude 入口](CLAUDE.md)。

## 只启动后端

```sh
python -m pip install -r requirements.txt
python -m uvicorn services.api.main:app --reload --host 127.0.0.1 --port 8000
```

打开 [Swagger](http://127.0.0.1:8000/docs)。无需启动前端即可查询真实案例、导入材料和运行测试。

```sh
python -m unittest discover -s tests
python scripts/export_contract.py
```

## 后端现有能力

- [知乎历史采集与 Luna 实跑说明](docs/ZHIHU_RESEARCH.md)：可选 pyzhihu-cli 适配器、登录、人物调查任务与 AI 工作器协议。匿名实测被拒绝，正常登录后的直接采集仍待验证。
- `/api/v1/authors`：档案、搜索、领域过滤、分页；同一博主可追加多篇历史文章。
- `/api/v1/authors/{id}/scorecard`：独立事件去重、命中率及 Wilson 区间、显式概率的 Brier / 校准、来源和采样覆盖。
- `/api/v1/authors/{id}/report`：带原文、来源、证据的合订本；支持 `as_of` 截止日期视图。
- `/api/v1/compare`：同领域、同题目集合对比，样本不足或口径不同时拒绝宣布排名。
- `/api/v1/claims/{id}/verification-jobs`：异步检索核验；状态可轮询、写入 SQLite，重启中断会如实标记失败。
- 人工裁定、证据原始出处标注、采样声明、纠错处理与 before/after 审计。
- `REVIEW_API_TOKEN` 保护人工评分相关写操作；模型与检索密钥只在后端读取。

不以粉丝数、点赞、语气或一次命中推断专家能力。标准概率统计公式由本项目独立实现；来源与许可证见 [开源说明](THIRD_PARTY_NOTICES.md)。

## 现有整栈演示

本地可运行的黑客松原型：发现预测者 → 历史合订本 → 证据 → 对比 → 关注。
前端 Next.js / Tailwind CSS / ECharts；后端 FastAPI / SQLite。

## 启动

需要 Python 3.12+、Node.js 22+。

```powershell
cd backcast
python -m pip install -r requirements.txt
npm --prefix apps/web ci
Copy-Item .env.example .env
npm run dev
```

打开 http://127.0.0.1:3000 。API 文档：http://127.0.0.1:8000/docs 。
首次启动自动创建本机 SQLite 数据库并载入五份真实来源案例。
无密钥可体验发现、过滤、关注、合订本、证据、对比、分享地址、纠错、规则候选抽取与持久化。
无密钥时不会伪装成已完成 AI 核验。

## 配置模型和检索

在 `.env` 中设置 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。
兼容 `/chat/completions` 和 JSON object 输出的 OpenAI 风格服务。
搜索支持 `SEARCH_PROVIDER=tavily` 或 `brave`，以及 `SEARCH_API_KEY`。
重启 API 后生效，密钥仅在 Python 服务读取，不发送给浏览器。

导入文章后打开命题证据面板，点击“检索外部证据并重新核验”。
每条最多搜索 4 个网页，下载正文上限 2MB；无法取得正文、可靠日期或合法引用时保留证据不足。
证据日期为网页提取值，会明确标识尚未独立确认；不等于已取得历史版本存证。
无需把所有领域写进提示词：`services/api/plugins.py` 提供独立领域数据适配器契约，目前未接入外部专业数据插件。

## 数据与演示

- 郭明錤：Vision Pro 上市窗口（MacRumors 报道 / Apple 实际上市记录）。
- Mark Gurman：Vision Pro 二月上市计划的前瞻报道（9to5Mac 转述 Bloomberg / Apple 实际上市记录）；可与郭明錤并排查看同一产品。
- IEA：2023 年全球电动车销量（2023 展望 / 2024 统计）。
- NASA：Artemis I 目标与实际发射日（任务日志）。
- 高盛研究团队：2014 世界杯概率预测（SBS 赛前报道 / UEFA 决赛报道）。

完整链接保存在 `services/api/seed.py`，也可在界面逐条打开。
内容均为注明来源的人工转述，不是抓取的知乎用户档案。个人和机构明确区分。
首批每个档案仅一条，不构成专家推荐；没有伪造准确率、粉丝数或长期样本。
原始历史版本未独立存证，因此严格计分样本为 0。结果吻合数与预测准确率分别展示。
报告地址 `/?expert=kuo` 可直接打开，分享双方需要能访问同一服务及数据库。
用户导入的作者身份和日期均未核实，不能直接用于公开排名。

建议三分钟演示：
1. 从消费科技找到郭明錤，打开合订本，展示当时判断与 Apple 后来发布的记录。
2. 切换体育案例，说明概率预测不能因为一次落空就判定模型无效。
3. 选择两位预测者比较，显示样本和不同领域的边界；关注其中一位。
4. 粘贴一段有明确时间的公开判断，生成新档案，展示实时服务配置或未到期状态。

## 测试

```powershell
npm test
npm run build
# E2E 自动启动 3001 / 8001 服务与独立测试数据库，避免混入演示数据
npm run test:e2e
```

E2E 默认使用已安装的 Chrome（Playwright channel=chrome）。
构建与 E2E 请顺序运行，避免 Next.js 生成类型文件时相互覆盖。
`BACKCAST_DB` 可覆盖数据库路径。运行记录见 `docs/TEST_RESULTS.md`。

## 部署

```powershell
docker compose up --build
```

先复制 `.env.example` 为 `.env`。Compose 仅把前端暴露在回环地址，SQLite 使用持久卷。
Docker 配置未在当前机器执行验证；本地 Node/Python 运行是已验证路径。
当前是本地单用户 MVP，没有用户隔离、身份认证或生产级访问防护；互联网发布前需要补齐这些部分。

## 开源

核验流程受 `fluencer-predict-track`（MIT）启发，独立实现。
分阶段证据检索参考 DEFAME 与 GPT Researcher；网页正文抽取使用 Trafilatura。
未复制这些项目的大段代码。依赖与来源详见 `THIRD_PARTY_NOTICES.md`。
