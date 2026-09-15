# PubMed 文献检索与可视化 Demo

这是一个用于面试演示的 Python + Docker 网页 Demo，目标是跑通：

```text
用户输入关键词 -> PubMed 检索 -> 统计分析 -> 可视化 -> AI 中文综述
```

项目重点不是堆功能，而是把 PubMed 数据、期刊影响因子补充、统计分析、页面展示和模型兜底这条链路讲清楚，并保证现场能演示。

## 技术栈

- 后端：FastAPI + Uvicorn
- 数据获取：NCBI E-utilities API，封装 `esearch`、`efetch`、`esummary`
- 数据分析：pandas + 自定义统计逻辑
- 可视化：原生 HTML/CSS/JavaScript + ECharts
- AI 综述：DeepSeek/OpenAI 风格接口，可失败兜底
- 数据缓存：SQLite
- 运行环境：Docker + docker compose

## 环境变量

复制模板：

```bash
copy .env.example .env
```

按需填写：

```env
PUBMED_API_KEY=your_pubmed_api_key_here
AI_PROVIDER=deepseek
AI_MODEL=deepseek-flash
AI_API_KEY=your_ai_api_key_here
DATABASE_URL=sqlite:///data/pubmed_demo.db
USE_MOCK_ON_ERROR=true
```

说明：

- `PUBMED_API_KEY` 用于提高 PubMed API 请求额度。
- `AI_API_KEY` 用于生成中文综述。
- `USE_MOCK_ON_ERROR=true` 可以保证 PubMed 网络失败或 API Key 异常时仍能演示完整流程。
- `.env` 不提交到 Git。

## Docker 启动

```bash
docker compose up --build
```

访问：

```text
http://localhost:8000
```

健康检查：

```text
http://localhost:8000/health
```

## 本地开发启动

安装依赖后运行：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 推荐演示关键词

```text
cancer immunotherapy
CAR T therapy
Alzheimer disease
```

建议面试现场优先使用 `cancer immunotherapy`。这个关键词医学文献量大，容易匹配到本地 Demo 期刊影响因子表，也适合展示研究方向综述。

## 已完成功能

- PubMed 关键词检索，返回标题、摘要、年份、期刊、作者、DOI、PMID。
- 期刊影响因子和分区本地 CSV 匹配。
- 年份趋势、分区分布、影响因子分布、Top 期刊可视化。
- 词频分析，用标题和摘要提取高频主题词。
- 近 5 年影响因子 Top 文献排序。
- 基于摘要生成中文分点综述。
- AI 失败时返回本地兜底综述。
- PubMed 失败时使用 `data/mock_articles.json` 兜底，保证现场可演示。
- SQLite 保存检索历史、文献缓存和检索-文献关联。

## 接口列表

```text
GET  /
GET  /health
POST /api/search
POST /api/analyze
POST /api/top-impact
POST /api/review
```

`/api/search` 示例：

```json
{
  "keyword": "cancer immunotherapy",
  "limit": 20
}
```

## 关键设计思路

PubMed 官方 API 不直接提供期刊影响因子和分区，所以项目使用 `data/journal_metrics.csv` 做本地映射。匹配不到的期刊不会报错，而是在页面显示 `Unknown`，保证数据链路稳定。

AI 综述不是把所有摘要直接塞给模型，而是先筛选有摘要的文献并控制长度，再要求模型输出中文、约 500 字、分点呈现。如果模型接口失败，后端会返回兜底综述，页面仍可完成演示。

SQLite 不是为了做复杂知识库，而是为了缓存检索历史和文献结果，减少现场重复请求外部 API 的不确定性。

## 后续可扩展方向

- 替换为更完整的 JCR/中科院期刊分区数据源。
- 增加检索历史页面和结果导出。
- 接入更稳定的模型供应商或本地模型。
- 加入摘要分批总结，支持更大规模文献综述。
- 增加 RAG 知识库，用于长期保存某一领域文献并支持追问。
