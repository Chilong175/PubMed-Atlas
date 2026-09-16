# Data files

## journal_metrics_publishers.csv（默认启用）

2026-09-16 从出版社公开网页提取的本地快照，共 239 种期刊，统一使用 2025 指标年：

- Frontiers：146 种，https://www.frontiersin.org/about/impact
- Nature Portfolio：88 种，https://www.nature.com/nature-portfolio/about-journals/journal-metrics
- 单刊核验补充：6 种，见 `journal_metrics_curated.csv`，包括 JCEM、Endocrinology、European Journal of Endocrinology、Medicina、Nutrients 和 Diabetes Research and Clinical Practice，逐条保存出版社来源。刷新脚本保留这些补充，但跨年更新须重新核验。

每条记录保留来源 URL 与指标年份。仅使用 Journal Impact Factor 列，不使用 CiteScore、五年 IF 或 SJR 替代。Frontiers 分区采用官网披露的 JIF rank quartile，页面未指明学科类别，因此不解释为所有学科的统一分区；Nature 表未披露分区，保持为空，不推测为 Q1。

这不是全量 JCR 数据库，也不是实时更新服务。未覆盖的出版社、未获得 IF 的新期刊仍可能显示未收录。旧示例表的未核验数值不混入默认统计。用户导入表仍整体优先，不自动拼接不同年份的数据。

更新命令：`python -m scripts.refresh_publisher_metrics`。脚本先检查网页年份与列名，再统一校验数据，全部成功后原子替换快照。年份变化或页面结构不兼容时停止，旧文件不变。更新到新指标年需人工确认 `YEAR` 和测试基准。检索过程仅读本地 CSV，不增加外网请求。

## journal_metrics.csv（旧示例，默认不启用）

`journal_metrics.csv` is a small demo mapping table for journal impact factor and quartile matching.

PubMed does not provide impact factor or journal quartile data. For this interview demo, the CSV is used to prove the local matching, filtering, and sorting workflow. In a real production project, this file should be replaced by an authorized source such as institutional JCR data, Web of Science, Clarivate products, or another licensed journal metrics provider.

Fields:

- `journal_name`: Full journal name used for matching.
- `journal_alias`: Common abbreviation or alias used for matching.
- `impact_factor`: Demo impact factor value.
- `quartile`: Demo journal quartile.
- `source_year`: Metric source year.
- `notes`: Data note.

## mock_articles.json

`mock_articles.json` is used when PubMed is unavailable and `USE_MOCK_ON_ERROR=true`.

It keeps the interview demo runnable even if the network, API key, or upstream PubMed service fails. The mock records are shaped like parsed PubMed articles, so the same analysis, visualization, ranking, and review code paths are exercised.
