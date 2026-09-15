from __future__ import annotations

import re
import string
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from app.services.pubmed_client import PubMedArticle


DEFAULT_METRICS_PATH = Path("data/journal_metrics.csv")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
    "we",
    "was",
    "were",
    "using",
    "study",
    "patients",
    "results",
    "conclusion",
    "background",
    "methods",
}


@dataclass
class EnrichedArticle:
    pmid: str
    title: str
    abstract: str
    year: int | None
    journal: str
    authors: list[str]
    doi: str | None
    impact_factor: float | None
    quartile: str
    metric_source_year: int | None

    def to_dict(self) -> dict:
        return asdict(self)


def load_journal_metrics(path: str | Path = DEFAULT_METRICS_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"journal_name", "journal_alias", "impact_factor", "quartile", "source_year"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"journal metrics missing columns: {', '.join(sorted(missing))}")

    df = df.copy()
    df["impact_factor"] = pd.to_numeric(df["impact_factor"], errors="coerce")
    df["source_year"] = pd.to_numeric(df["source_year"], errors="coerce").astype("Int64")
    df["journal_key"] = df["journal_name"].map(normalize_journal_name)
    df["alias_key"] = df["journal_alias"].map(normalize_journal_name)
    return df


def enrich_articles(
    articles: Iterable[PubMedArticle],
    metrics: pd.DataFrame,
) -> list[EnrichedArticle]:
    metric_lookup = _build_metric_lookup(metrics)
    enriched: list[EnrichedArticle] = []

    for article in articles:
        metric = metric_lookup.get(normalize_journal_name(article.journal), {})
        impact_factor = metric.get("impact_factor")
        source_year = metric.get("source_year")
        enriched.append(
            EnrichedArticle(
                pmid=article.pmid,
                title=article.title,
                abstract=article.abstract,
                year=article.year,
                journal=article.journal,
                authors=article.authors,
                doi=article.doi,
                impact_factor=float(impact_factor) if pd.notna(impact_factor) else None,
                quartile=str(metric.get("quartile") or "Unknown"),
                metric_source_year=int(source_year) if pd.notna(source_year) else None,
            )
        )

    return enriched


def analyze_articles(
    articles: Iterable[PubMedArticle],
    metrics_path: str | Path = DEFAULT_METRICS_PATH,
    current_year: int | None = None,
) -> dict:
    metrics = load_journal_metrics(metrics_path)
    enriched = enrich_articles(articles, metrics)

    return {
        "total_count": len(enriched),
        "year_distribution": year_distribution(enriched),
        "quartile_distribution": quartile_distribution(enriched),
        "impact_factor_distribution": impact_factor_distribution(enriched),
        "top_journals": top_journals(enriched),
        "top_impact_articles": top_impact_articles(enriched, current_year=current_year),
        "word_frequencies": word_frequencies(enriched),
        "articles": [article.to_dict() for article in enriched],
    }


def year_distribution(articles: Iterable[EnrichedArticle]) -> list[dict]:
    counter = Counter(article.year for article in articles if article.year)
    return [{"year": year, "count": counter[year]} for year in sorted(counter)]


def quartile_distribution(articles: Iterable[EnrichedArticle]) -> list[dict]:
    counter = Counter(article.quartile or "Unknown" for article in articles)
    order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "Unknown": 99}
    return [
        {"quartile": quartile, "count": count}
        for quartile, count in sorted(counter.items(), key=lambda item: order.get(item[0], 98))
    ]


def impact_factor_distribution(articles: Iterable[EnrichedArticle]) -> list[dict]:
    bins = [
        ("Unknown", None, None),
        ("0-5", 0, 5),
        ("5-10", 5, 10),
        ("10-20", 10, 20),
        ("20-50", 20, 50),
        ("50+", 50, None),
    ]
    counter = Counter({label: 0 for label, *_ in bins})
    for article in articles:
        value = article.impact_factor
        if value is None:
            counter["Unknown"] += 1
            continue
        for label, lower, upper in bins[1:]:
            if value >= lower and (upper is None or value < upper):
                counter[label] += 1
                break
    return [{"range": label, "count": counter[label]} for label, *_ in bins]


def top_journals(articles: Iterable[EnrichedArticle], limit: int = 10) -> list[dict]:
    summary: dict[str, dict] = {}
    for article in articles:
        journal = article.journal or "(Unknown journal)"
        record = summary.setdefault(
            journal,
            {
                "journal": journal,
                "count": 0,
                "impact_factor": article.impact_factor,
                "quartile": article.quartile or "Unknown",
            },
        )
        record["count"] += 1
        if record["impact_factor"] is None and article.impact_factor is not None:
            record["impact_factor"] = article.impact_factor
            record["quartile"] = article.quartile or "Unknown"

    journals = list(summary.values())
    journals.sort(
        key=lambda item: (
            -item["count"],
            -(item["impact_factor"] if item["impact_factor"] is not None else -1),
            item["journal"].casefold(),
        ),
    )
    return journals[:limit]


def top_impact_articles(
    articles: Iterable[EnrichedArticle],
    current_year: int | None = None,
    years: int = 5,
    limit: int = 100,
) -> list[dict]:
    articles = list(articles)
    known_years = [article.year for article in articles if article.year]
    anchor_year = current_year or (max(known_years) if known_years else None)
    if anchor_year is None:
        return []
    min_year = anchor_year - years + 1

    candidates = [
        article
        for article in articles
        if article.year is not None
        and article.year >= min_year
        and article.impact_factor is not None
    ]
    candidates.sort(key=lambda article: (article.impact_factor or 0, article.year or 0), reverse=True)
    return [article.to_dict() for article in candidates[:limit]]


def word_frequencies(
    articles: Iterable[EnrichedArticle],
    limit: int = 50,
) -> list[dict]:
    counter: Counter[str] = Counter()
    for article in articles:
        text = f"{article.title} {article.abstract}"
        counter.update(_tokenize(text))
    return [{"word": word, "count": count} for word, count in counter.most_common(limit)]


def normalize_journal_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.casefold().strip()
    normalized = normalized.translate(str.maketrans("", "", string.punctuation))
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z-]{2,}", text.casefold())
    return [word for word in words if word not in STOPWORDS]


def _build_metric_lookup(metrics: pd.DataFrame) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for _, row in metrics.iterrows():
        record = row.to_dict()
        for key_column in ("journal_key", "alias_key"):
            key = record.get(key_column)
            if key:
                lookup[str(key)] = record
    return lookup
