# 观点分身对抗：真实运行案例

主题：**远程办公是否应成为知识工作的默认模式**。

2026-11-17 已实际运行成功：`remote-qualitative-20261117`，`completed`，7 条来源、2 个分身、6 次发言和模型生成总结。每条来源引用及后续发言的回应锚点均通过精确子串校验。可查看仓库中的 [独立报告](examples/debate-remote-work.html) 和 [真实结果快照](examples/debate-remote-work.json)。快照只保留被引用的来源片段，不发布完整搜索摘要。

验证结果：`python -m unittest discover -s tests` 共 133 项通过；API 客户端 TypeScript 检查通过；真实本地 HTTP 返回 200；Playwright 已打开报告、展开引用依据，并检查完成状态和三轮发言。浏览器首次出现的唯一控制台错误为默认 `favicon.ico` 的 404，不影响报告功能。

示范用户偏好远程；系统从知乎官方公开搜索取回相关材料，建立 A、B 两个主题观点分身，生成三轮六次交锋和分歧总结。分身是材料支持下的 AI 推演，非原作者本人，也不代表对其完整人格的复刻。示范用户立场是测试输入，不是对真实用户的画像。

## 运行

复用现有 `ZHIHU_ACCESS_SECRET` 或本机忽略文件 `.local/zhihu-official.env`。不要将凭证提交到仓库。

```powershell
python scripts/run_debate_case.py
```

实际调用知乎官方搜索，以及 `https://developer.zhihu.com/v1/chat/completions` 的 `zhida-fast-1p5` 模型。不使用预写辩论文本。结果落盘：

- `.local/debate-case/result.json`：来源、逐轮对话、精确引用、总结及状态。
- `.local/debate-case/report.html`：可打开的独立报告，展开查看每轮依据。
- `.local/debate-case/case.sqlite3`：每一步的持久化结果，包括中断任务。

失败时保留已有内容并返回非零退出码。使用输出中的任务 ID 续跑：

```powershell
python scripts/run_debate_case.py --resume TASK_ID
```

## 队友对接

后端提供 `POST /api/v1/debates`（`topic`、`stance`），返回 202 和任务 ID；轮询 `GET /api/v1/debates/{id}` 获取 `status`、`sources`、`plan.personas`、`turns`、`summary`。`GET /api/v1/debates/{id}/report` 返回独立 HTML。契约见 `docs/openapi.json`。

状态：queued → collecting → planning → debating → completed；异常为 failed，可保留部分发言。当前后台任务为本机进程内任务，不保证跨服务重启续跑，CLI 支持显式续跑。生产队列、流式输出和队友前端尚未接入。

## 这次实际暴露的问题

第一次真实运行在两次发言后遇到 HTTP 429。第二次运行也发生网络或 JSON 异常，没有伪造剩余发言。检查发现模型把文章中的未经核验的研究数字用作论据，因此增加定性材料过滤，禁止引用研究统计，重新生成案例。模型调用按至少 25 秒间隔发起，429 最多重试两次（等待 20、40 秒）；仍失败则停止。

定性版在五次发言后遭遇 JSON 解析失败，续跑补齐第六次发言；总结也曾解析失败。将总结输入缩减为实际发言正文、明确短 JSON 结构后，重新调用真实模型成功，任务最终完成。凭证与私有运行数据库均未加入公开快照。

引用检查只能证明引用在检索材料中存在，**不能证明作者说的事实正确**。当前输入是搜索摘要，不能据此宣称读完作者全历史，也不能保证原始发表版本。回应锚点检查只能阻止伪造被引用文字，不能保证整段论证没有语义曲解。这些限制在报告中明确展示。

MVP 的展示价值是：输入一个立场，找到不同取舍的公开材料，把分歧推进到具体条件和可追问问题，并让观众展开检查依据。当前案例是复合观点分身，按真实作者一对一克隆和用户现场插话尚未完成。
