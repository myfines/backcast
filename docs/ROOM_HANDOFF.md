# 队友先玩这个：作者分身讨论室

当前主线：**用户表达立场 → 选作者分身 → 连续讨论 → 可邀请 AI 辩论团 → 展开原话依据**。作者分身和辩论团已接真实模型，旧专家评分页面可以暂时搁置。`apps/web/` 仍由你负责，后端提供一个简陋的独立试玩页。

## 拉取与启动

```powershell
git fetch origin
git switch feat/zhihu-research
git pull --ff-only origin feat/zhihu-research
python -m pip install -r requirements.txt
```

在本机 `.env` 中设置 `ZHIHU_ACCESS_SECRET`，或在忽略目录 `.local/zhihu-official.env` 配置同名变量。凭证只在后端，不要发给前端或提交 Git。

```powershell
python -m uvicorn services.api.main:app --reload --host 127.0.0.1 --port 8000
```

打开 **http://127.0.0.1:8000/api/v1/rooms/playground/ui**，点击“新建示例讨论室”。示例已经提供真实材料生成的“解虫”画像卡，无需重新采集或生成画像。勾选辩论团时，每次提问会产生一位作者分身和两位虚构 AI 角色的回应。默认使用知乎官方 `zhida-fast-1p5`，本轮没有接 OpenAI 模型切换。

**无密钥也能看** [三轮真实讨论报告](examples/discussion-room.html)、[原始对话快照](examples/discussion-room.json)、[作者画像](examples/author-persona.html)。不能无密钥生成新回答。

## 前端只接主体

现有 TypeScript 客户端 `packages/api-client/client.ts` 已增加以下方法：

```ts
const api = createBackcastClient('/api/v1');
const room = await api.createDemoRoom(true); // false 为单独与作者讨论
const updated = await api.sendRoomMessage(room.id, '我倾向远程优先，你最担心什么？');
const restored = await api.room(room.id); // 恢复对话或检查部分输出
const persona = await api.persona(room.persona_id);
```

自定义作者：`createPersona({author_name, documents:[{author_name,url,text,title,is_excerpt}]})`，然后 `createRoom({persona_id,topic,council})`。默认示例画像和材料来自真实先前运行，静态卡片可复用；新的回答每次调用真实模型。不要把示例中只有一篇材料的画像展示成“完整人格”。

| 接口 | 用途 |
|---|---|
| `POST /api/v1/rooms/demo`，`{"council":true}` | 载入示例作者并创建新讨论室 |
| `POST /api/v1/rooms` | 使用已有作者分身创建讨论室 |
| `GET /api/v1/rooms/{id}` | 完整对话和当前状态 |
| `POST /api/v1/rooms/{id}/messages`，`{"message":"..."}` | 用户发言，返回更新后对话 |
| `GET /api/v1/rooms/{id}/report` | 可展开引用的 HTML 讨论记录 |
| `POST /api/v1/personas` | 从同一作者公开材料创建画像 |
| `GET /api/v1/personas/{id}` | 画像、覆盖范围和资料链接 |

状态为 `ready / generating / failed`。发送消息是同步长请求，一般每轮两次模型调用，调用间隔至少二十五秒；按钮应显示等待状态并禁用重复提交。可轮询 GET 查看已经写入的部分回答。同房间重复发送返回 409。失败返回 502，已生成部分保留，可通过 GET 查看，不显示假的完成动画。一场最多十二次用户发言，模型能看到最近十二条历史发言。引用检查确认原文存在和回应锚点存在，尚不能自动保证整个论证都忠实。

这是本地黑客松原型，尚未实现登录、跨进程任务队列和重启续跑。生成过程中重启服务可能留下 generating 状态，此时新建讨论室继续。请不要直接作为多用户公网服务部署。

## 本次实跑

2026-11-17，Codex 扮演人类用户，逐轮看实际回答再追问，不是独立真人用户测试。真实模型为 `zhida-fast-1p5`。共 **三次用户发言、三次作者分身回应、六次 AI 辩论团发言**，最终 `ready`。

1. 用户提出十人软件团队远程优先、对新人保留到岗的方案。分身质疑验收与文档化；辩论团分别提出试点及权责澄清。
2. 用户质问分身无依据的“第一个月就会出问题”，并补充验收、确认与争议裁决。分身记得新增条件，转为有条件接受，但仍为先前说法辩解。
3. 用户要求直接承认没有来源，并补充共同签署、完整交付周期与观测指标。分身明确承认原断言没有来源、改称提醒属于事后找补，接受远程优先试点，并把风险列为待验证项。

这次测试体现出连续对话与辩论团能工作，也暴露出模型会自行添加结论；完整记录保留了错误与纠正，不能宣称已消除所有语义曲解。

首轮通过 CLI 调用后端，第二轮通过真实 HTTP（200），第三轮通过 Playwright 在试玩页填写并发送。引用与回应锚点均逐字校验。仅 favicon 404 出现在浏览器控制台。

复跑单轮案例：

```powershell
python scripts/play_room_case.py --council --message "我想把远程设为默认，你最担心什么？"
python scripts/play_room_case.py --room-id 输出中的ID --message "如果先做试点，你会接受吗？"
```

API 契约见 `docs/openapi.json`；类型见 `packages/api-client/schema.d.ts`。开源复用与协议见 `docs/AUTHOR_PERSONAS.md` 和 `THIRD_PARTY_NOTICES.md`。

推送前验证：`python -m unittest discover -s tests` 共 143 项通过；TypeScript 客户端严格类型检查通过，OpenAPI 快照已同步。自动测试覆盖连续记忆、引用缺失、伪造回应锚点、并发发送 409、生成失败 502 及部分对话保留，不在 CI 调用付费模型。
