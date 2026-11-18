# Frontend handoff · 给队友和 Claude

> 当前主题已经切换为作者分身讨论室，请先看 [新版对接说明](ROOM_HANDOFF.md)。本页是旧专家合订本接口记录。

## 你负责什么

前端在 `apps/web/`，可以重写页面和组件。后端位于 `services/api/`，已提供 v1 接口和真实种子案例。
产品主线：**我想了解某个领域 → 找到有历史判断记录的人 → 翻合订本 → 看证据 → 同口径比较 → 关注**。
不需要继续使用现有页面的视觉风格；不要自行生成看起来更漂亮的命中率或样本数量。

## 五分钟对接

公开库：https://github.com/myfines/backcast

```sh
git clone https://github.com/myfines/backcast.git
cd backcast
python -m pip install -r requirements.txt
python -m uvicorn services.api.main:app --reload --port 8000
```

Swagger: http://127.0.0.1:8000/docs 。契约快照：`docs/openapi.json`。
`docs/examples/` 有实际种子库响应；可直接作前端开发 fixture，文件里保留了来源及“小样本不可排名”的状态。

```sh
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

现有 Next.js rewrite 已把 `/api/*` 代理到 `http://127.0.0.1:8000`。换前端框架也可以，后端默认 CORS 允许本机 3000/5173。

## 当前前端路由（feat/frontend-redesign）

| 路由 | 页面 | 说明 |
| --- | --- | --- |
| `/` | 发现预测者 | `?domain=`、`?q=`、`?followed=1`（我的关注）、`?page=`；`/?expert=kuo` 旧分享链接重定向到合订本 |
| `/experts/{id}` | 合订本 | 判断力面板、时间轴、历史判断；`?as_of=YYYY-MM-DD` 截止日视图，`?domain=`，`?claim={id}` 打开证据抽屉 |
| `/claims/{id}` | 证据与判定（整页） | 原文、证据、判定引用、核验任务、纠错、审计历史 |
| `/compare?ids=a,b&domain=` | 对比判断记录 | 2–4 人并排；不满足比较政策时不宣布胜者 |
| `/import?author={id}` | 添加判断记录 | 新建档案或追加到已有档案 |
| `/rooms` | 作者分身讨论室入口 | `POST /api/v1/rooms/demo`（载入示例分身并建房）；本设备最近的讨论 id 存在 localStorage |
| `/rooms/{id}` | 讨论室 | `GET /rooms/{id}`、`POST /rooms/{id}/messages`、`GET /personas/{id}`、`GET /rooms/{id}/report`；发送是长请求，期间每 4 秒读取房间以显示已保存的部分；409/502 如实显示，不做假的完成动画 |
| `/replay` | 真实讨论回放 | 无接口：读取 `apps/web/lib/replay/*.json`（`docs/examples/discussion-room.json`、`author-persona.json` 的副本，因 Docker 上下文只含 apps/web）。不调用模型，不需要凭证；示例更新后需重新复制 |
| `/research` | 调查知乎答主 | 两种入口：`POST /api/v1/research-jobs`（按答主采集历史）与 `POST /api/v1/text-audits`（核查一段公开文字） |
| `/research/{id}` | 调查进度与结果 | 轮询 `GET /api/v1/research-jobs/{id}`；终态为 `succeeded / needs_login / blocked / failed`，`awaiting_analysis` 低频轮询；`needs_login / blocked / failed` 可 `POST .../retry` |
| `/methodology` | 评价方法 | 来自 `GET /api/v1/methodology` |
| `/review` | 人工复核 | 令牌仅存于当前标签页 sessionStorage，以 `X-Review-Token` 发送 |

前端类型来自 `packages/api-client/schema.d.ts` 的副本 `apps/web/lib/contract/schema.d.ts`（web 镜像的 Docker 构建上下文只有 `apps/web`）。后端更新契约后运行 `npm --prefix apps/web run sync:contract`。

前端发现的契约缺口（未改后端）：
- 讨论室页面的“质疑出处”只把追问写进输入框，用户确认后才发送；“把握度”只存在 localStorage，仅是用户自评；“原话使用情况”由回合里的 `quotes` 在前端统计。
- 讨论室没有“列出房间”接口，也没有按任意作者创建画像的前端入口（`POST /personas` 会调用真实模型，需后端 `ZHIHU_ACCESS_SECRET`）；目前前端只接示例分身和已有房间。
- `ResearchJob` 的 `coverage / documents / result` 在 OpenAPI 里是自由对象；前端按后端实际写入的字段在 `lib/api.ts` 里声明了类型，请在契约里补上明确的 schema。
- 没有“列出我的调查任务”接口；前端只在 localStorage 记住本设备创建的任务 id，状态仍从接口读取。
- `/research-jobs/{id}/input`、`/analysis` 需要后端工作器令牌，不属于前端接口，前端不调用也不保存该令牌。
- 没有跨命题的“待处理纠错”列表接口；复核后台目前逐条请求 `GET /claims/{id}/reviews` 组装队列，数据量变大后需要 `GET /api/v1/reviews?status=pending`。
- `GET /claims/{id}/reviews` 与 `/claims/{id}/audit` 的条目没有 OpenAPI schema（前端按 `{id,claim_id,note,created_at,status}` 与 `{id,action,record_id,created_at,data}` 解析）。

## 推荐页面与接口

| 页面 / 动作 | 接口 |
| --- | --- |
| 专家发现、筛选、搜索 | `GET /api/v1/authors?q=Gurman&domain=消费科技&limit=20&offset=0` |
| 个人卡片 | `GET /api/v1/authors/{id}` |
| 判断力仪表盘 | `GET /api/v1/authors/{id}/scorecard?domain=消费科技` |
| 合订本 / 分享报告 | `GET /api/v1/authors/{id}/report` |
| 历史截止日视图 | `GET /api/v1/authors/{id}/report?as_of=2023-12-31` |
| 时间线 / 命题列表 | `GET /api/v1/claims?author_id=kuo&limit=20&offset=0` |
| 命题与全部证据 | `GET /api/v1/claims/{id}` |
| 审计历史 | `GET /api/v1/claims/{id}/audit` |
| 创建档案 | `POST /api/v1/authors`，`{name,domain,role,bio?,platform_url?}` |
| 给同一个人追加文章 | `POST /api/v1/import`，`{author_id,text,url?,published_at?,edited_at?}` |
| 首次直接导入 | `POST /api/v1/import`，`{author,text,url?,published_at?}` |
| 原始材料 | `GET /api/v1/sources/{source_id}` |
| 关注 / 取消关注 | `POST /api/v1/authors/{id}/follow`，切换状态，返回 `{followed}` |
| 提交纠错 | `POST /api/v1/claims/{id}/reviews`，`{note}`，至少5字 |
| 纠错列表 | `GET /api/v1/claims/{id}/reviews` |
| 同领域比较 | `POST /api/v1/compare`，`{author_ids:["kuo","gurman"],domain:"消费科技"}` |
| 启动检索核验 | `POST /api/v1/claims/{id}/verification-jobs`，202 返回 Job |
| 轮询核验 | `GET /api/v1/jobs/{id}`，每1—2秒一次；终态停止 |
| 服务能力 | `GET /api/health`，看 `ai` / `search` 是否启用 |
| 评价政策 | `GET /api/v1/methodology` |

所有分页返回 `{items,total,offset,limit}`，limit 最大100。不要把原型 `/api/dashboard` 作为新前端的主数据源。
`follow` 是切换接口，网络重试前先读取作者 `followed`，不要无条件重复 POST。

## 分数怎么显示

- v1 `accuracy`、Wilson 区间、概率都是 **0—1 的比率**，前端乘100显示。旧 dashboard 的百分比格式不要混用。
- `null` 显示“样本不足 / 暂无”，不能显示0分或0%。
- `categorical` 是明确命题命中记录；`probabilistic.brier` 是显式概率预测的误差，越低越好。
- `probabilistic.calibration` 可直接画校准曲线；空 bin 的频率是 null，不是0。
- `readiness.eligible_for_ranking=false` 时不显示名次或“推荐专家”。展示 `warnings` 与实际样本量。
- `evidence_quality` 是证据可追溯性，不是博主的人格评价。未确认来源不能画成认证徽章。
- `comparison.comparable=false` 仍可并排展示档案，但不能宣布胜者。`paired_brier` 只来自共同事件。
- 当前真实示例每人仅少量记录，原始版本尚未独立存证，所以严格得分为空是正常行为。

## 异步任务状态

`queued → running → succeeded | failed`。
成功表示核验流程结束，**不表示预测正确**；结果可能是证据不足或尚未到期。
失败时显示 `error`，不能自动把命题判错。任务结果保存在 SQLite，进程重启中断的任务会标为 failed，不伪装成可靠分布式队列。

## 人工复核后台（可后做）

以下接口需要请求头 `X-Review-Token`，值由后端 `.env` 的 `REVIEW_API_TOKEN` 配置。不要放在客户端常量、仓库或 NEXT_PUBLIC 环境变量中。

- `POST /api/v1/claims/{id}/resolution`：完整 schema 见 OpenAPI。提交 `status,citations,reason,reviewer,event_key,outcome_at`；若确认事前版本，还需 `original_version_confirmed=true,original_snapshot_url,original_snapshot_at`。
- 概率记录额外提供 `forecast_format=probabilistic,probability,probability_quote,binary_outcome`，摘录必须存在于原文且包含一致的百分数。
- `PATCH /api/v1/evidence/{id}/metadata`：核实证据日期、原始出处及来源类型。
- `PUT /api/v1/authors/{id}/sampling`：记录完整采样窗口的人工审核声明。

## 错误与测试

404：档案不存在；422：输入/引用/时间校验失败；403：复核令牌无效；503：人工复核未配置；502：外部服务失败。
错误响应的 `detail` 可能是字符串或 Pydantic 校验数组，客户端需兼容。
后端无需 API 密钥可跑全部单元测试。CI 不调用付费服务。

可直接贴给 Claude：

> 请先读 AGENTS.md、CLAUDE.md 和 docs/FRONTEND_HANDOFF.md。你负责 apps/web 前端，基于 docs/openapi.json 接 /api/v1。围绕“找有预测能力的人”重做发现、合订本、证据和对比页面。后端返回 null 或不可排名时保留这一状态，不伪造分数。API 缺字段时提契约变更，不擅改评分逻辑。
