# Data files

## journal_metrics.csv

`journal_metrics.csv` is a small demo mapping table for journal impact factor and quartile matching.

PubMed does not provide impact factor or journal quartile data. For this interview demo, the CSV is used to prove the local matching, filtering, and sorting workflow. In a real production project, this file should be replaced by an authorized source such as institutional JCR data, Web of Science, Clarivate products, or another licensed journal metrics provider.

Fields:

- `journal_name`: Full journal name used for matching.
- `journal_alias`: Common abbreviation or alias used for matching.
- `impact_factor`: Demo impact factor value.
- `quartile`: Demo journal quartile.
- `source_year`: Metric source year.
- `notes`: Data note.

