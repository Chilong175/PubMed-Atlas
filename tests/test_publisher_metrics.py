from pathlib import Path
from unittest import TestCase

from app.services.analyzer import analyze_articles
from app.services.journal_metrics import parse_metrics_csv
from app.services.pubmed_client import PubMedArticle
from scripts.refresh_publisher_metrics import extract_metrics


class PublisherMetricsTest(TestCase):
    def test_snapshot_is_valid_single_year_with_sources(self):
        rows = parse_metrics_csv(Path('data/journal_metrics_publishers.csv').read_text(encoding='utf-8'))
        self.assertGreater(len(rows), 200)
        self.assertEqual({r['source_year'] for r in rows}, {'2025'})
        self.assertTrue(all(r['source'].startswith('https://') for r in rows))

    def test_if_without_quartile_is_still_matched_and_ranked(self):
        articles = [PubMedArticle('1', 'Test', '', 2025, 'Scientific reports', []),
                    PubMedArticle('2', 'Test', '', 2025, 'Frontiers in oncology', []),
                    PubMedArticle('3', 'Test', '', 2025, 'Unlisted test journal', [])]
        result = analyze_articles(articles, metrics_path='data/journal_metrics_publishers.csv', current_year=2025)
        self.assertEqual(result['metric_coverage']['matched'], 2)
        self.assertEqual(result['metric_coverage']['data_source'], 'publisher')
        self.assertEqual(result['articles'][0]['impact_factor'], 4.9)
        self.assertEqual(result['articles'][0]['quartile'], 'Unknown')
        self.assertEqual(len(result['top_impact_articles']), 2)
        self.assertIsNone(result['articles'][2]['impact_factor'])

    def test_extract_uses_jif_not_citescore_and_skips_missing(self):
        html = '''JCR 2025<table><tr><th>Journal</th><th>Journal Impact Factor</th>
        <th>CiteScore</th><th>JIF rank quartile</th><th>CiteScore rank quartile</th></tr>
        <tr><td>Test journal</td><td>2.5</td><td>9.9</td><td>Q3</td><td>Q1</td></tr>
        <tr><td>Unranked</td><td>-</td><td>8.1</td><td>-</td><td>Q1</td></tr></table>'''
        rows = extract_metrics(html, 'frontiers')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['impact_factor'], '2.5')
        self.assertEqual(rows[0]['quartile'], 'Q3')
        with self.assertRaises(ValueError):
            extract_metrics(html.replace('JCR 2025', 'JCR 2026'), 'frontiers')
        with self.assertRaises(ValueError):
            extract_metrics('JCR 2025<table><tr><td>Changed layout</td></tr></table>', 'frontiers')

    def test_nature_ignores_editorial_days_and_five_year_if(self):
        html = '''2025&nbsp;Journal Metrics
        <table><tr><td>Journal</td><td>Submission to Accept</td></tr><tr><td>Test</td><td>300</td></tr></table>
        <table><tr><td>Journal</td><td>Journal Impact Factor</td><td>5-year Journal Impact Factor</td></tr>
        <tr><td>Test</td><td>4.9</td><td>8.7</td></tr><tr></tr></table>'''
        rows = extract_metrics(html, 'nature')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['impact_factor'], '4.9')
        self.assertEqual(rows[0]['quartile'], '')
