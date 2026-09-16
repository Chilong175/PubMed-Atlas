import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.db import save_search_result, get_search_articles
from app.services.analyzer import analyze_articles
from app.services.journal_metrics import import_metrics, parse_metrics_csv
from app.services.pubmed_client import PubMedArticle, PubMedClient


HEADER = 'journal_name,journal_alias,issn,eissn,impact_factor,quartile,source_year,source,quartile_system\n'
# Synthetic metric values for tests only.
CSV = HEADER + 'Example Journal,Ex J;Example J,0028-0836,1476-4687,3.5,Q2,2023,Test fixture,JCR test category\n'


class JournalMetricsTest(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imported.csv'
        self.patcher = patch('app.services.journal_metrics.IMPORTED_METRICS_PATH', self.path)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.client = TestClient(app)

    def test_issn_precedes_name_and_abbreviation_recovers_match(self):
        import_metrics(CSV)
        articles = [
            PubMedArticle('1', 'Title', '', 2025, 'Different title', [], issns=['14764687']),
            PubMedArticle('2', 'Title', '', 2025, 'Long official title', [], journal_abbreviation='Ex. J.'),
            PubMedArticle('3', 'Title', '', 2025, 'Missing', []),
            PubMedArticle('4', 'Title', '', 2025, 'Example Journal', [], issns=['1532-1983']),
        ]
        result = analyze_articles(articles)
        self.assertEqual([a['metric_match_method'] for a in result['articles']], ['issn', 'abbreviation', 'unmatched', 'unmatched'])
        self.assertEqual(result['metric_coverage']['matched'], 2)
        self.assertEqual(result['metric_coverage']['percent'], 50)
        self.assertEqual(result['articles'][0]['metric_source'], 'Test fixture')
        self.assertEqual(result['articles'][0]['metric_source_year'], 2023)

    def test_import_rejects_bad_data_without_replacing_previous(self):
        import_metrics(CSV)
        original = self.path.read_bytes()
        invalid = [CSV.replace('3.5', 'NaN'), CSV.replace('3.5', '-1'), CSV.replace('0028-0836', '0028-0830'), CSV.replace('Test fixture', ''), CSV + CSV.splitlines()[1], CSV.replace('Q2', 'Zone 1'), CSV.replace('JCR test category', ''), HEADER]
        for text in invalid:
            with self.subTest(text=text):
                response = self.client.post('/api/metrics/import', json={'csv_text': text})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(self.path.read_bytes(), original)

    def test_import_routes_and_analysis_preserve_identifiers(self):
        response = self.client.post('/api/metrics/import', json={'csv_text': '\ufeff' + CSV})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/metrics').json()['data_source'], 'imported')
        article = {'pmid':'1','title':'Title','abstract':'','journal':'Different title','year':2025,'issns':['0028-0836']}
        response = self.client.post('/api/analyze', json={'articles':[article]})
        self.assertEqual(response.json()['articles'][0]['impact_factor'], 3.5)
        self.assertEqual(response.json()['articles'][0]['issns'], ['0028-0836'])
        self.assertEqual(len(self.client.post('/api/top-impact', json={'articles':[article]}).json()['articles']), 1)
        self.assertIn('journal_name', self.client.get('/api/metrics/template').text)

    def test_imported_table_does_not_fall_back_to_demo(self):
        import_metrics(CSV)
        article = PubMedArticle('1', 'Title', '', 2025, 'Frontiers in Oncology', [])
        self.assertIsNone(analyze_articles([article])['articles'][0]['impact_factor'])

    def test_zero_if_empty_quartile_and_mixed_years(self):
        self.assertEqual(len(parse_metrics_csv(CSV.replace('3.5,Q2', '0,'))), 1)
        with self.assertRaises(ValueError):
            parse_metrics_csv(CSV + 'Another Journal,,,,2,,2022,Test fixture,\n')

    def test_xml_and_sqlite_preserve_identifiers_and_old_database(self):
        xml = '''<PubmedArticle><MedlineCitation><PMID>1</PMID><Article><Journal><Title>Example</Title><ISOAbbreviation>Ex J</ISOAbbreviation><ISSN IssnType="Electronic">1476-4687</ISSN></Journal></Article><MedlineJournalInfo><ISSNLinking>0028-0836</ISSNLinking></MedlineJournalInfo></MedlineCitation></PubmedArticle>'''
        article = PubMedClient()._parse_article(ET.fromstring(xml))
        self.assertEqual(article.issns, ['1476-4687', '0028-0836'])
        self.assertEqual(article.journal_abbreviation, 'Ex J')
        database = 'sqlite:///' + (Path(self.temp.name) / 'test.db').as_posix()
        search_id = save_search_result('test', 1, 1, [article], database)
        cached = get_search_articles(search_id, database)[0]
        self.assertEqual(cached.issns, article.issns)
        self.assertEqual(cached.journal_abbreviation, 'Ex J')
