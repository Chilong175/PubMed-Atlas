from unittest import TestCase

from fastapi.testclient import TestClient

from app.main import app


class PubMedApiAnalysisTest(TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.articles = [
            {
                "pmid": "1",
                "title": "Cancer immunotherapy response",
                "abstract": "Immunotherapy response biomarker.",
                "year": 2025,
                "journal": "Cancer Cell",
                "authors": ["Zhang Y"],
                "doi": "10.1000/one",
            },
            {
                "pmid": "2",
                "title": "Small journal oncology paper",
                "abstract": "Oncology treatment response.",
                "year": 2025,
                "journal": "Unmapped Demo Journal",
                "authors": ["Li M"],
                "doi": None,
            },
        ]

    def test_analyze_returns_unknown_for_unmatched_journal(self) -> None:
        response = self.client.post(
            "/api/analyze",
            json={"articles": self.articles, "current_year": 2025},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_count"], 2)
        self.assertIn({"quartile": "Unknown", "count": 1}, payload["quartile_distribution"])
        self.assertEqual(payload["articles"][1]["impact_factor"], None)
        self.assertEqual(payload["articles"][1]["quartile"], "Unknown")

    def test_top_impact_skips_articles_without_impact_factor(self) -> None:
        response = self.client.post(
            "/api/top-impact",
            json={"articles": self.articles, "current_year": 2025, "years": 5, "limit": 100},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([article["pmid"] for article in payload["articles"]], ["1"])
        self.assertEqual(payload["articles"][0]["journal"], "Cancer Cell")

