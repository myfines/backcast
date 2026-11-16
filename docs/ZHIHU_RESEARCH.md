# 知乎历史采集与 Luna 分析试跑

## 本次实际结果（2026-11-16）

1. 在隔离环境 `.venv/zhihu-probe` 安装 **pyzhihu-cli 0.2.4**。没有读取浏览器凭证，也未全局安装同名 CLI。
2. 对 `excited-vczh` 做一次匿名资料请求，约 3.05 秒返回 `LoginError: Access denied`（库对 HTTP 403 的映射）。没有取到答主资料、回答或文章，也不能确认该目标当前可用。
3. 发现没有已保存 CLI 登录态，停止访问。将已观察到的拒绝状态写入本地熔断记录；会话未变化时不会重复请求同一资源。
4. 完成采集适配器与任务链，记录 `needs_login / blocked`，不会把这些状态当作空历史或人物不靠谱。
5. 另从公开网页检索服务读取知乎文章《深入浅出ChatGPT：技术原理一探究竟》的短节选。此路径标记 `operator_supplied_public_excerpt`，与按答主历史列表采集严格分开；未确认作者和发表时间，没有归到上述探测答主。
6. **Luna 作为分析 AI 执行了任务，没有写代码。** 提取候选、按原子事实修订并给出判定。随后后端实际下载证据页，匹配连续摘录：GPT-3 论文通过，OpenAI ChatGPT 页面取证/摘录校验未通过。模型提出的两条支持，最终只接受一条。
7. 真实取证试跑最终结果：**4 条事实，1 条支持、3 条证据不足、0 条反驳**。没有据此判断整个人。由 Luna 结果整理并收窄引用的回放样本、后端结果、Luna 最终说明在 `docs/examples/luna-*.json`。

测试通过不代表知乎正常登录采集已跑通。下一步须由用户完成本机正常登录，再实测真实答主回答分页和正文。

## 本机登录（Windows PowerShell）

本机已经安装隔离环境。在仓库目录运行：

```powershell
cd D:\黑客松\backcast
& ".\.venv\zhihu-probe\Scripts\python.exe" ".\scripts\zhihu-login.py"
```

脚本会要求你先在自己的浏览器正常登录知乎，再从开发者工具 Network 复制一条知乎请求的 Cookie 请求头值，粘贴到**本机隐藏提示**。不要发到聊天、不要写在命令参数里。

脚本用只读 `/me` 校验会话；成功才将其保存到 `.local/zhihu/cookies.json`。如果平台仍拒绝请求，停止且不保存，不宣称登录成功。`.local/` 已被 Git 和 Docker 忽略。

如果使用自定义 `ZHIHU_COOKIE_FILE`，登录脚本和 API 进程需要使用相同的环境变量。

新机器安装：

```powershell
python -m venv .venv\zhihu-probe
& ".\.venv\zhihu-probe\Scripts\python.exe" -m pip install -r requirements-zhihu.txt
```

## 登录后只读实测

```powershell
python scripts/zhihu-probe.py "https://www.zhihu.com/people/你选择的答主标识" --limit 3
```

成功返回真实条数、时间字段和链接；被拒绝则停止。不要用大量重试、验证码绕过或修改访问限制的方式继续。

## 人物调查 API

```http
POST /api/v1/research-jobs
Content-Type: application/json

{"target":"https://www.zhihu.com/people/example","goal":"检查他关于编程的事实与判断","domain":"编程技术","max_items":20,"max_pages":3,"analyst":"worker"}
```

- `GET /api/v1/research-jobs/{id}`：任务及实际覆盖。
- `POST /api/v1/research-jobs/{id}/retry`：正常登录后重试未完成的采集。正在运行时不会重复启动。
- 状态：`queued → collecting → awaiting_analysis → succeeded`；可停在 `needs_login / blocked / failed`。
- 分页去重，保留原文、发表/编辑时间、内容哈希及当前版本；不将当前抓取当作历史存证。
- 分析输入每份最多6,000字符、合计30,000字符，会披露截断与未包含材料；完整采集材料仍保存在 Sources，不把分析节选当作全历史。
- API 条数、页数预算与正文缺失都会披露；中途失败保存已经取得的材料。

## 系统 AI 的两种入口

### 这次采用：外部分析工作器（Luna）

这是**本次会话中真实调用的 Luna 子代理**，不是一个已经部署的常驻 Luna API。后端通过输入/输出接口接收它的分析；记录 `model=gpt-6-luna`、`model_provenance=worker_declared`，并自行验证原文和证据。

本机会话工作器令牌已保存在忽略的 `.env`，未公开。队友机器需要自行配置 `RESEARCH_WORKER_TOKEN`。

```powershell
python scripts/research-worker.py create "答主主页链接" --goal "检查他的技术判断" --domain "编程技术"
python scripts/research-worker.py status "返回的任务ID"
python scripts/research-worker.py input "任务ID" --output .local/research-input.json
# 分析 AI 读取 input，返回 JSON；不要让分析 AI 修改程序或访问会话凭证。
python scripts/research-worker.py submit "任务ID" .local/analyst-output.json
```

输入与回填接口分别为 `GET /research-jobs/{id}/input` 和 `POST /research-jobs/{id}/analysis`，需要后端工作器令牌，不属于普通前端用户接口。原文不存在的引用会拒绝；证据无法下载或连续摘录不匹配则降为证据不足。

回放这次真实 Luna 输出，并重新执行真实取证（不会重新调用 Luna）：

```powershell
python scripts/luna-smoke.py
```

### 常驻运行：OpenAI 兼容 API

请求设置 `analyst=openai`，并配置模型与搜索服务，会执行抽取、搜索、证据读取和模型判定。密钥未配置时保留材料并进入 `awaiting_analysis`，不会用规则伪装成已完成 AI 研究。这条外部 API 路径尚未真实联通测试。

## 给前端队友

不要修改原有文章导入流程也能接新入口。使用新增的 ResearchRequest / ResearchJob 类型：
`createBackcastClient().research(body)`、`researchJob(id)`、`retryResearch(id)`。后端契约已经更新；前端分支需要运行 `sync:contract`。

当前默认不根据本批材料推荐或否定人物。事实核验结果是材料级 AI 辅助结论，预测资格、版本存证与长期表现仍分别保留。
