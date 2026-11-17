# 指定作者分身：开源复用与运行记录

## 采用的方案

- [Persona Chatbot](https://github.com/tinasheosewe/persona-chatbot)，MIT，已克隆阅读 `src/prompts/templates.py`、`src/memory/documents.py`。采用“每个人物独立材料库、表达风格卡、检索上下文”的组织方式。`persona_context.py` 改编其 `render_context_blocks`，上游提交 `8b48a8f1ed2c400522caf6edc052cb3d06fc046f`，完整版权许可见 `third_party/persona-chatbot.LICENSE`。没有采用上游要求隐藏 AI 身份的提示词。
- [Second-Me](https://github.com/mindverse/Second-Me)，Apache-2.0，已核对 README 与 LICENSE。参考身份与长期记忆分层思路；本版未安装其训练系统，未声称实现模型微调或完整人格还原。
- [OpenCharacters](https://github.com/josephrocca/OpenCharacters)，MIT，已核对 README 与 LICENSE。其角色卡和旧消息摘要可作为后续会话记忆参考，本版未引入其前端。

## 已实现

`POST /api/v1/personas` 接收 `author_name`、`documents`，每篇材料包含 `author_name`、`url`、`text`，可带 `title`、`published_at`、`is_excerpt`。构建可持久化的观点、价值取舍、判断习惯、表达风格卡，每个维度必须有逐字出处。不同作者材料不能混入同一分身。

`GET /api/v1/personas/{id}` 读取档案；`POST /api/v1/personas/{id}/chat` 接收 `message`，在该作者资料中检索相关段落，结合画像生成回应。中文二元词匹配和重叠分段实现轻量本地检索，无需额外 embedding 服务。输出及引用存入 SQLite，引用必须在本次送给模型的材料中存在。

创建辩论时传入 `opponent_persona_id`，B 方即绑定指定作者的画像、表达风格和专属来源；B 的画像与逐轮引用不能借用其他作者资料。测试覆盖正常三轮流程及跨作者引用拒绝；尚未为这一新增接线重新跑六轮外部模型，真实作者画像与单次问答已实跑。

当前独立问答的互动会存档，但尚未将历史会话重新注入后续独立问答。导入材料的作者身份由调用方标注；同名身份、链接归属未独立核验。最多导入三十篇，画像阶段读取前十二篇的前一千八百字，其余材料可供检索。返回覆盖字段明确说明该范围。

## 真实案例

2026-11-17：使用知乎官方搜索已取得的“解虫”署名文章《从远程办公困境看懂：为什么懂沟通的人永远不会被AI淘汰》的摘要，建立作者分身 `1b47491b0cf942ecb8888f6cecc66e43`。仅一篇材料，提取四个画像维度，不能视为作者全历史。

提问：“我认为把任务都写进文档，远程办公就能成为默认模式。你怎么看？”

真实模型 `zhida-fast-1p5` 回应强调“文档是必要条件而非充分条件”，还需要精准沟通与需求对齐，附三条通过精确引用校验的出处。最初两次画像请求输出了普通说明文字，被解析器拒绝；将 JSON 结构放进任务正文后，画像和回答实际成功，没有使用预写回答。

[查看这次作者分身结果](examples/author-persona.html)。完整原始材料与数据库仅保存在忽略目录 `.local`。
