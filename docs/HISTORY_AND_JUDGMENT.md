# 两个问题：取得历史，忠实复盘

本轮研究与实测：2026-11-16。主场景调整为股票、宏观与国际关系中的历史判断；不再把科普知识问答当作产品示范。

## 开源选型

| 项目 | 已核对的能力 | 取舍 |
|---|---|---|
| [ZhiArchive](https://github.com/amchii/ZhiArchive) | 实读 README、LICENSE、`archive/core/profile.py`、`reader.py`、`mcp_server.py`；提供作者回答/文章/想法分页、正文分页、Markdown/HTML/截图归档，MIT | 作为独立历史采集服务，通过只读 MCP 接入；最贴近现有 Python/SQLite 架构 |
| [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/zhihu/core.py) | 实读知乎采集实现；有 creator 路径，默认采集回答，文章/视频调用被注释 | 不作为本轮依赖；当前文件标注 NON-COMMERCIAL LEARNING LICENSE 1.1，不能当作 MIT 项目随意复制 |
| [投资大V合订本](https://github.com/wzj998/fluencer-predict-track) | 实读 README；浏览器采集、创建/编辑时间、外部结果、人物复盘，MIT | 参考合订本流程，不采用“按语气推仓位”或把未明确概率的表达硬转换成交易策略 |
| [Hindsight](https://github.com/envisioning/hindsight) | 实读 README、`docs/grading/grader.md`、`docs/DECISIONS.md`、LICENSE；区分预测/趋势/情景，先写忠实读法再对照结果 | 参考原意优先及类型分开。代码 MIT、数据 CC BY 4.0；本项目没有导入其数据，也没有套用技术普及率和数值容差阈值 |

本轮没有找到、也没有实测到一个能直接替代以上流程的“判断知乎专家靠不靠谱”专用模型。这里需要的是分析流程和数据接入，现有 OpenAI 兼容模型可执行；模型名称本身不能保证不曲解原话。

## 分析口径

先保留作者当时真正说了什么，再看后来发生什么。

1. **事实优先。** 关键事实前提单独核查。事实错误不会因表达漂亮或逻辑自洽被抵消。
2. **逻辑自洽另加分。** 必须给出至少两段作者原文作为前提/结论依据。后端确认引用存在；相容性仍是模型分析，不能描述为机器证明。加分按每个命题最多 1 点单列，不混成准确率或个人总分。
3. **保留直觉。** “我直觉看好”不因没有严密推导被扣分。有结果依据时可以记录截至核查时的方向支持/反向表现；不是自动宣称预测成功。
4. **不补承诺。** 作者没说必然、翻倍、年底、所有情况，AI 就不能加上这些标准来判他错。
5. **条件与情景分开。** “如果降息，我看好成长股”要先看原条件；未确认发生则不按无条件预测判错。“可能谈判，也可能僵持”保留为情景，不能改成保证停火。
6. **未知不算失败。** 缺少证据、未到期和没有期限的开放判断不进入失败数。没有合理推导不等于逻辑矛盾。

后端可机械阻止不存在的引文和条件，不能仅靠字符串校验保证模型的语义理解正确。新提示词与分类是减少误读的措施，后续仍需真实人物样本验证。

## 已实现的接口变化

现有 `POST /api/v1/research-jobs` 不变。采集服务由后端环境变量选择：

```dotenv
ZHIHU_BACKEND=zhiarchive
ZHIARCHIVE_MCP_URL=http://127.0.0.1:9090/mcp/
ZHIARCHIVE_TOKEN=
```

客户端可选依赖：`python -m pip install -r requirements-zhiarchive.txt`。ZhiArchive 本体单独运行，不是安装这个依赖文件就会自动启动。

分析工作器的每个命题增加可选字段（兼容旧工作器）：

```json
{
  "mode": "conditional",
  "reading": "以降息发生为条件的方向判断",
  "condition_quotes": ["如果明年开始降息"],
  "condition_state": "unknown",
  "logic": {"status": "not_assessed", "reason": null, "quotes": []}
}
```

`mode` 支持 `assertion / directional_view / conditional / scenario / intuition`。原有 `kind=fact/prediction/opinion` 保留。`condition_quotes` 和 `logic.quotes` 必须连续存在于原材料，否则在网络取证之前拒绝分析。

人物任务结果新增 `policy_version`、`judgments`、`reasoning`、`observations`。命题详情增加 `interpretation`、`judgment_review`。事实、判断与逻辑分开，前端可以直接展示对应记录，不需要编一个综合“靠谱分”。

## 真实运行结果

- 拉取 ZhiArchive 固定提交 `0db740b96b7e8e5ab1130d9f4560720824f241f7`，在 `.local/ZhiArchive` 隔离部署。
- 上游锁定依赖最初下载超时；重试后遇到 `RuntimeError: uvloop does not support Windows at the moment`。Windows 安装列表去掉 uvloop 后成功。
- 本机试跑使用标准 Playwright，去掉上游 Stealth 包装和自定义 User-Agent；变更保存为 `scripts/zhiarchive-standard-runtime.patch`，保留上游许可见 `docs/licenses/ZhiArchive-MIT.txt`。没有启用代理轮换、验证码绕过或访问拒绝后自动重试。
- 使用已有的本机登录文件准备采集服务的本机状态，凭证未发给分析模型或写进仓库。
- 本地服务成功运行于 `127.0.0.1:9090`，MCP 初始化及登录摘要读取成功。注意：该摘要的 `valid` 是上游对本机状态文件格式的检查，不能单独证明知乎服务器接受登录。
- 对从已登录页面确认过链接的 `liulangdehama` 进行有限回答列表读取。未取得历史正文；采集器返回知乎拒绝访问。Backcast 首次将 MCP 异常组误报为服务不可用，本轮已补回归测试并修复为保留原始拒绝及已采材料。诊断后没有继续采集该目标。
- 所以：**已接入现成采集接口，尚未跑通本机真实作者历史采集。** 不能说换了项目就能无限抓历史。
- Luna 对四条明确标注为虚构的股票/谈判表述做了分析模式测试，正确区分直觉、条件、情景、方向判断；这不是任何真人的历史成绩。保留输出于 `docs/examples/interpretation-luna.json`。
- 完整后端套件 102 个测试通过（4.160 秒），覆盖采集分页、正文分页、错误作者、摘要不冒充正文、拒绝停止、MCP 异常组保留材料、补造条件防护、逻辑加分不抵消事实错误、情景不算失败等。TypeScript API 客户端检查通过；本轮未新增或重跑前端浏览器 E2E。

## 重现部署

当前机器已安装并启动上游服务。新机器可参考上游 README，或按固定版本重建本次测试环境：

```powershell
git clone https://github.com/amchii/ZhiArchive.git .local/ZhiArchive
git -C .local/ZhiArchive checkout 0db740b96b7e8e5ab1130d9f4560720824f241f7
git -C .local/ZhiArchive apply (Resolve-Path scripts/zhiarchive-standard-runtime.patch)
python -m venv .venv/zhiarchive
# Windows 的 requirements 安装列表需要排除 uvloop；Linux 可使用原锁定列表。
Get-Content .local/ZhiArchive/requirements.txt | Where-Object { $_ -notmatch '^uvloop==' } | Set-Content .local/zhiarchive-windows-requirements.txt
.venv/zhiarchive/Scripts/python.exe -m pip install -r .local/zhiarchive-windows-requirements.txt
.venv/zhiarchive/Scripts/python.exe -m playwright install chromium
```

在上游目录运行隔离环境的 Python：`python -m uvicorn archive.api.app:app --host 127.0.0.1 --port 9090`。首次在本机控制台 `http://127.0.0.1:9090/zhi/core/config` 完成正常登录。只开所需的 Reader；不要为本轮测试恢复后台连续监控。

Backcast 有界探测：

```powershell
python scripts/zhihu-probe.py TARGET --backend zhiarchive --limit 2
```

403/429 或登录拒绝后停止；先解决正常访问问题，不把拒绝当成作者空历史或作者不靠谱。
