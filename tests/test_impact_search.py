from datetime import date
from unittest import TestCase
from unittest.mock import Mock, patch

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.analyzer import enrich_articles, top_impact_articles
from app.services.impact_search import search_top_impact
from app.services.pubmed_client import PubMedArticle, PubMedClientError


def article(pmid, year=2026, journal='High journal'):
    return PubMedArticle(str(pmid), 'Test title', '', year, journal, [])


class ImpactSearchTest(TestCase):
    def setUp(self):
        self.metrics = pd.DataFrame([
            dict(journal_name='High journal', journal_alias='', impact_factor=10, source_year=2025),
            dict(journal_name='Low journal', journal_alias='', impact_factor=2, source_year=2025),
        ])

    def test_calendar_window_rejects_old_future_and_unknown(self):
        enriched = enrich_articles([article(1, 2010), article(2, 2021), article(3, 2022), article(4, 2026), article(5, 2027), article(6, None)], self.metrics)
        self.assertEqual({a['pmid'] for a in top_impact_articles(enriched, current_year=2026)}, {'3', '4'})
        with patch('app.services.analyzer.date') as clock:
            clock.today.return_value = date(2026, 9, 16)
            self.assertEqual(top_impact_articles(enriched[:1]), [])

    def test_independent_search_returns_100_and_stops_before_lower_if(self):
        client = Mock()
        client.esearch.return_value = (1000, [str(i) for i in range(100)])
        client.efetch.return_value = [article(i) for i in range(100)]
        result = search_top_impact('cancer', self.metrics, client, today=date(2026,9,16), pause=lambda _: None)
        self.assertEqual(len(result['articles']), 100)
        self.assertEqual(result['journals_checked'], 1)
        self.assertFalse(result['global_complete'])
        self.assertTrue(result['ranking_complete_within_table'])
        query = client.esearch.call_args.args[0]
        self.assertIn('"2022/01/01"', query)
        self.assertIn('"2026/09/16"', query)
        self.assertIn('"High journal"[Journal]', query)

    def test_missing_metrics_and_duplicate_pmids_do_not_fill_ranking(self):
        client = Mock()
        client.esearch.side_effect = [(2, ['1','2']), (2, ['1','3'])]
        client.efetch.side_effect = [[article(1), article(2, journal='Unknown')], [article(1), article(3,journal='Low journal')]]
        result = search_top_impact('test', self.metrics, client, today=date(2026,9,16), pause=lambda _: None)
        self.assertEqual([a['pmid'] for a in result['articles']], ['1','3'])
        self.assertEqual(result['unresolved_records'], 1)
        self.assertFalse(result['ranking_complete_within_table'])

    def test_ranking_errors_do_not_fall_back_to_mock(self):
        with patch('app.api.pubmed.search_top_impact', side_effect=PubMedClientError('unavailable')):
            response = TestClient(app).post('/api/top-impact/search',json={'keyword':'test'})
        self.assertEqual(response.status_code, 502)
