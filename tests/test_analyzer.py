from unittest import TestCase

import pandas as pd

from app.services.analyzer import (
    analyze_articles,
    enrich_articles,
    impact_factor_distribution,
    quartile_distribution,
    top_impact_articles,
    word_frequencies,
    year_distribution,
)
from app.services.pubmed_client import PubMedArticle


class AnalyzerTest(TestCase):
    def setUp(self) -> None:
        self.metrics = pd.DataFrame(
            [
                {
                    "journal_name": "Cancer Cell",
                    "journal_alias": "Cancer Cell",
                    "impact_factor": 50.3,
                    "quartile": "Q1",
                    "source_year": 2023,
                    "journal_key": "cancer cell",
                    "alias_key": "cancer cell",
                },
                {
                    "journal_name": "Clinical Cancer Research",
                    "journal_alias": "Clin Cancer Res",
                    "impact_factor": 11.5,
                    "quartile": "Q1",
                    "source_year": 2023,
                    "journal_key": "clinical cancer research",
                    "alias_key": "clin cancer res",
                },
            ]
        )
        self.articles = [
            PubMedArticle(
                pmid="1",
                title="Cancer immunotherapy response biomarkers",
                abstract="Immunotherapy biomarkers predict durable cancer response.",
                year=2025,
                journal="Cancer Cell",
                authors=["Zhang Y"],
                doi="10.1000/one",
            ),
            PubMedArticle(
                pmid="2",
                title="Tumor microenvironment and resistance",
                abstract="Tumor immune resistance limits immunotherapy response.",
                year=2023,
                journal="Clin Cancer Res",
                authors=["Li M"],
                doi="10.1000/two",
            ),
            PubMedArticle(
                pmid="3",
                title="Older oncology treatment study",
                abstract="Chemotherapy treatment context.",
                year=2017,
                journal="Unknown Journal",
                authors=[],
                doi=None,
            ),
        ]

    def test_enrich_articles_matches_full_name_and_alias(self) -> None:
        enriched = enrich_articles(self.articles, self.metrics)

        self.assertEqual(enriched[0].impact_factor, 50.3)
        self.assertEqual(enriched[0].quartile, "Q1")
        self.assertEqual(enriched[1].impact_factor, 11.5)
        self.assertEqual(enriched[2].impact_factor, None)
        self.assertEqual(enriched[2].quartile, "Unknown")

    def test_distribution_and_top_impact_outputs(self) -> None:
        enriched = enrich_articles(self.articles, self.metrics)

        self.assertEqual(
            year_distribution(enriched),
            [
                {"year": 2017, "count": 1},
                {"year": 2023, "count": 1},
                {"year": 2025, "count": 1},
            ],
        )
        self.assertEqual(quartile_distribution(enriched), [{"quartile": "Q1", "count": 2}, {"quartile": "Unknown", "count": 1}])
        self.assertEqual(impact_factor_distribution(enriched)[-1], {"range": "50+", "count": 1})

        top_articles = top_impact_articles(enriched, current_year=2025)
        self.assertEqual([article["pmid"] for article in top_articles], ["1", "2"])

    def test_word_frequencies_and_full_analysis(self) -> None:
        enriched = enrich_articles(self.articles, self.metrics)

        words = word_frequencies(enriched, limit=3)
        self.assertEqual(words[0]["word"], "immunotherapy")

        analysis = analyze_articles(self.articles, metrics_path="data/journal_metrics.csv", current_year=2025)
        self.assertEqual(analysis["total_count"], 3)
        self.assertIn("year_distribution", analysis)
        self.assertIn("top_impact_articles", analysis)

