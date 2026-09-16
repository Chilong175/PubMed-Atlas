from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from app.services.pubmed_client import PubMedArticle
from app.services import journal_metrics


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
    metric_source: str = ""
    metric_match_method: str = "unmatched"
    quartile_system: str = ""
    journal_abbreviation: str = ""
    issns: list[str] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def load_journal_metrics(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path is not None else (
        journal_metrics.IMPORTED_METRICS_PATH if journal_metrics.IMPORTED_METRICS_PATH.exists() else DEFAULT_METRICS_PATH
    )
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"journal_name", "journal_alias", "impact_factor", "quartile", "source_year"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"journal metrics missing columns: {', '.join(sorted(missing))}")

    df = df.copy()
    for column in ("issn", "eissn", "source", "quartile_system"):
        if column not in df:
            df[column] = ""
    df["source"] = df["source"].replace("", "Demo 示例表（未经权威来源核验）")
    df["impact_factor"] = pd.to_numeric(df["impact_factor"], errors="coerce")
    df["source_year"] = pd.to_numeric(df["source_year"], errors="coerce").astype("Int64")
    df["journal_key"] = df["journal_name"].map(normalize_journal_name)
    df["alias_key"] = df["journal_alias"].map(normalize_journal_name)
    df.attrs["data_source"] = "demo" if path == DEFAULT_METRICS_PATH else "imported"
    return df


def enrich_articles(
    articles: Iterable[PubMedArticle],
    metrics: pd.DataFrame,
) -> list[EnrichedArticle]:
    metric_lookup = _build_metric_lookup(metrics)
    enriched: list[EnrichedArticle] = []

    for article in articles:
        metric, match_method = _match_metric(article, metric_lookup)
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
                metric_source=str(metric.get("source") or "Demo 示例表（未经权威来源核验）") if metric else "",
                metric_match_method=match_method,
                quartile_system=str(metric.get("quartile_system") or "未注明") if metric else "",
                journal_abbreviation=article.journal_abbreviation,
                issns=article.issns,
            )
        )

    return enriched


def analyze_articles(
    articles: Iterable[PubMedArticle],
    metrics_path: str | Path | None = None,
    current_year: int | None = None,
) -> dict:
    metrics = load_journal_metrics(metrics_path)
    enriched = enrich_articles(articles, metrics)

    return {
        "total_count": len(enriched),
        "metric_coverage": metric_coverage(enriched, metrics),
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
    return journal_metrics.normalize_name(value)


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z-]{2,}", text.casefold())
    return [word for word in words if word not in STOPWORDS]


def _build_metric_lookup(metrics: pd.DataFrame) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    ambiguous: set[str] = set()
    for _, row in metrics.iterrows():
        record = row.where(pd.notna(row), "").to_dict()
        keys = {"name:" + normalize_journal_name(name) for name in [record["journal_name"], *record.get("journal_alias", "").split(";")] if normalize_journal_name(name)}
        keys.update("issn:" + value for column in ("issn", "eissn") if (value := journal_metrics.normalize_issn(record.get(column, ""))))
        for key in keys:
            if key in lookup:
                ambiguous.add(key)
            else:
                lookup[key] = record
    for key in ambiguous:
        lookup.pop(key, None)
    return lookup


def _match_metric(article: PubMedArticle, lookup: dict) -> tuple[dict, str]:
    issns = {journal_metrics.normalize_issn(value) for value in article.issns} - {""}
    matches = [lookup["issn:" + value] for value in issns if "issn:" + value in lookup]
    if matches:
        if any(record != matches[0] for record in matches[1:]):
            return {}, "conflict"
        return matches[0], "issn"
    for name, method in ((article.journal, "name"), (article.journal_abbreviation, "abbreviation")):
        record = lookup.get("name:" + normalize_journal_name(name))
        if record:
            known = {journal_metrics.normalize_issn(record.get(column, "")) for column in ("issn", "eissn")} - {""}
            if issns and known and not issns & known:
                continue
            return record, method
    return {}, "unmatched"


def metric_coverage(articles: list[EnrichedArticle], metrics: pd.DataFrame) -> dict:
    matched = sum(article.impact_factor is not None for article in articles)
    missing = Counter(article.journal for article in articles if article.impact_factor is None)
    return {
        "total": len(articles), "matched": matched, "missing": len(articles) - matched,
        "percent": round(matched / len(articles) * 100, 1) if articles else 0,
        "data_source": metrics.attrs.get("data_source", "demo"),
        "journal_count": len(metrics),
        "source_years": sorted(int(year) for year in metrics["source_year"].dropna().unique()),
        "unmatched_journals": [{"journal": journal, "count": count} for journal, count in missing.most_common()],
    }
