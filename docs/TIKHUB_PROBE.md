# TikHub 作者历史探测

2026-11-17 已下载并读取 [TikHub 实际 OpenAPI](https://api.tikhub.io/openapi.json)，确认以下接口及参数存在：

- `GET /api/v1/zhihu/web/fetch_user_info`：`user_url_token`。
- `GET /api/v1/zhihu/web/fetch_user_answers`：`user_url_token / offset / limit / sort_type`。
- `GET /api/v1/zhihu/web/fetch_user_articles`：同上。

这是第三方托管服务，独立于知乎官方开发者平台。需要 TikHub 自己的 API Key；不会复用 `ZHIHU_ACCESS_SECRET` 或知乎 Cookie。

## 使用

在 [TikHub 用户中心](https://user.tikhub.io/login) 注册或登录，取得 API Key，在本机未跟踪的 `.env` 中加入：

```dotenv
TIKHUB_API_KEY=你的TikHub密钥
```

无需把密钥发到聊天。无需安装 TikHub SDK；当前探测器使用现有 httpx，避免 SDK 默认的自动重试。

```powershell
python scripts/tikhub-probe.py zhang-jia-wei --pages 2 --limit 3
python scripts/tikhub-probe.py excited-vczh --kind article --pages 2 --limit 3
```

一次命令最多3次请求（作者资料1次，列表最多2次），不自动重试、不充值。一次测试只运行一条命令；不默认连续执行两个示例。请求可能消耗该服务的额度，以账户实际价格为准。

输出保存在 `.local/tikhub-probe.json`，包括作者、条目正文、日期、去重结果与是否读到末尾。控制台只显示统计与固定错误信息，不显示凭证或原始错误响应。服务返回的翻页链接只用于读取 offset，不携带密钥跟随链接。

`has_body_content` 只说明返回了非空 content，`completeness_verified=false` 表示尚未与原文验证全文完整性。小规模试读不直接宣称基本覆盖作者历史，也不生成人物评分。

## 实际验证状态

- 公开 OpenAPI 读取成功，确认了接口、分页参数和独立 Bearer 鉴权。
- 4项离线测试通过：作者ID与分页、3请求上限、鉴权失败不重试和不泄露密钥、不复用官方凭证、中途失败保留材料。
- 本机数据探测返回 `not_configured`，实际数据请求0次：尚缺 TikHub API Key。
- 因此作者历史正文、分页成功率、时间跨度和覆盖率均未实测，不宣称接入成功。

取得本机密钥后，先测试一个已知作者，核对返回作者身份、每页新条目、正文长度、最早日期和是否能正常继续分页，再决定是否接入正式人物调查。
