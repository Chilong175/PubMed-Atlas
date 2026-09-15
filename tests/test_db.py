from tempfile import TemporaryDirectory
from unittest import TestCase

from app.db import get_search_articles, init_db, list_search_history, save_search_result
from app.services.pubmed_client import PubMedArticle


class DatabaseTest(TestCase):
    def test_save_search_result_and_read_history(self) -> None:
        with TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{tmpdir}/pubmed_demo.db"
            articles = [
                PubMedArticle(
                    pmid="1",
                    title="First article",
                    abstract="First abstract",
                    year=2025,
                    journal="Cancer Cell",
                    authors=["Zhang Y"],
                    doi="10.1000/one",
                ),
                PubMedArticle(
                    pmid="2",
                    title="Second article",
                    abstract="Second abstract",
                    year=2024,
                    journal="Clinical Cancer Research",
                    authors=["Li M", "Wang Q"],
                    doi=None,
                ),
            ]

            init_db(database_url)
            search_id = save_search_result(
                keyword="cancer immunotherapy",
                limit=10,
                total_count=100,
                articles=articles,
                database_url=database_url,
            )

            history = list_search_history(database_url)
            cached_articles = get_search_articles(search_id, database_url)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["keyword"], "cancer immunotherapy")
        self.assertEqual(history[0]["total_count"], 100)
        self.assertEqual(history[0]["returned_count"], 2)
        self.assertEqual([article.pmid for article in cached_articles], ["1", "2"])
        self.assertEqual(cached_articles[1].authors, ["Li M", "Wang Q"])

