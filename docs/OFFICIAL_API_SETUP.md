# 官方知乎 API 与 MCP 接入

实测日期：2026-11-16。正式数据路线使用 `developer.zhihu.com` 的开发者凭证，不再要求浏览器 Cookie。

官方资料：

- [统一 MCP 配置](https://developer.zhihu.com/docs?key=unified_mcp)
- [知乎搜索](https://developer.zhihu.com/docs?key=zhihu_search)
- [官方 CLI 技能包](https://developer-cdn.zhihu.com/zhihu-cli/releases/stable/skill/zhihu-cli-skill.zip)

本次直接取得官网前端实际加载的公开文档索引 `/console/api/v3/docs`，核对最新鉴权、统一 MCP、搜索参数和用户内容权限。公开文档与本机原始响应保存在被忽略的 `.local/`，不包含在公开库中。

## 本机配置

用户提供的凭证保存在 `.local/zhihu-official.env`，没有写入仓库、前端或报告。部署时设置服务端 `ZHIHU_ACCESS_SECRET`，或通过 `ZHIHU_CREDENTIAL_FILE` 指向本机 dotenv 文件。

本机 `.env` 已设置 `SEARCH_PROVIDER=zhihu_official`，原有证据搜索 provider 会调用官方全网搜索。模型仍使用原有 `OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL` 配置；本轮没有配置或宣称跑通模型 API。

Codex 用户配置中已增加 `mcp_servers.zhihu`，地址为 `https://developer.zhihu.com/api/mcp/v1`，凭证仅存在用户本机配置。需要重启 Codex 后在新对话加载；本次通过独立 MCP 客户端验证，不等于当前对话已动态增加了工具。

## 实际运行结果

| 测试 | 结果 |
|---|---|
| 官方额度 REST API | HTTP 200，Code=0 |
| 知乎搜索，英伟达相关查询 | HTTP 200，Code=0，返回3条作者、来源链接与摘要 |
| 全网搜索 | 成功返回2条结果；仅代表接口可用，不代表这些结果足以支持任何判断 |
| 2023年创建时间范围搜索 | 成功返回3条结果，CreateTime均在2023年；EditTime较晚，不能把当前内容当作2023年原始存证 |
| 统一 MCP 初始化、工具发现 | 成功，返回 zhihu_search、global_search、hot_list、zhida |
| MCP 调用 zhihu_search | 成功，isError=false，返回3351字符结果 |
| 官方技能 ZIP 下载 | 本机到 CDN 的 TLS 连接失败，未安装成功；没有关闭证书校验。已用官方公开文档完成 REST/MCP 接入 |

真实后端路由联通测试：`GET /api/v1/official/status` 返回200且 configured=true；经 `POST /api/v1/official/search` 调用官方接口，返回200及2条真实结果。将本次提交版本隔离导出后运行，110个测试通过（4.717秒）；本机完整工作区119项通过。TypeScript客户端检查通过；本轮未重跑前端浏览器E2E。

## 可用工具

```powershell
python scripts/zhihu-official.py quota
python scripts/zhihu-official.py search "英伟达 股价 判断" --count 3 --output .local/results.json
python scripts/zhihu-official.py search "英伟达" --count 3 --sort-by "CreateTime:asc:(1672531200,1704067199)"
python scripts/zhihu-official.py search "NVIDIA quarterly results" --scope web --count 3
```

默认每次独立请求，不自动重试。鉴权、限流与网络错误使用固定错误信息，不向调用方转发可能含敏感信息的上游错误正文；不跟随携带鉴权的跳转。

## 后端接口

- `GET /api/v1/official/status`：配置摘要，不返回凭证。
- `POST /api/v1/official/search`：`{"query":"英伟达","scope":"zhihu","count":3,"sort_by":"CreateTime:asc:(1672531200,1704067199)"}`。
- `scope=web`：调用官方全网搜索。
- Typed client：`officialStatus()`、`officialSearch(body)`；无需在前端保存官方凭证。

返回项保留作者昵称、原始链接（含官方溯源参数）、摘要、创建时间和含义不确定的 `EditTime`。明确 `is_excerpt=true`、`author_identity_verified=false`、`complete_author_history=false`。同名不代表同一人，摘要不冒充全文，搜索排名和官方权威度也不直接变成人物判断能力分数。

正式用户创作 API 在不传 OAuth 时读取凭证所属账号；代表其他用户需要目标用户授权。本轮没有用当前凭证查询任意博主的全部历史，也没有自动遍历本人的关注与收藏。
