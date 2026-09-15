from __future__ import annotations

import json
from pathlib import Path

from app.services.pubmed_client import PubMedArticle


DEFAULT_MOCK_PATH = Path("data/mock_articles.json")


def load_mock_articles(
    keyword: str = "",
    limit: int = 20,
    path: str | Path = DEFAULT_MOCK_PATH,
) -> tuple[int, list[PubMedArticle]]:
    mock_path = Path(path)
    with mock_path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    articles = [PubMedArticle(**record) for record in records]
    matched = _filter_articles(articles, keyword)
    selected = matched[:limit]
    return len(matched), selected


def _filter_articles(articles: list[PubMedArticle], keyword: str) -> list[PubMedArticle]:
    terms = [term.casefold() for term in keyword.split() if term.strip()]
    if not terms:
        return articles

    matched = [
        article
        for article in articles
        if all(term in _search_text(article) for term in terms)
    ]
    return matched or articles


def _search_text(article: PubMedArticle) -> str:
    return f"{article.title} {article.abstract} {article.journal}".casefold()
