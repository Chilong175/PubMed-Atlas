from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models.schemas import AnalyzeRequest, Article, ReviewRequest, SearchRequest, SearchResponse, TopImpactRequest
from app.services.analyzer import analyze_articles, load_journal_metrics, enrich_articles, top_impact_articles
from app.services.mock_data import load_mock_articles
from app.services.pubmed_client import PubMedArticle, PubMedClient, PubMedClientError
from app.services.reviewer import ReviewError, generate_review


router = APIRouter(prefix="/api", tags=["pubmed"])


@router.post("/search", response_model=SearchResponse)
def search_pubmed(payload: SearchRequest) -> SearchResponse:
    settings = get_settings()
    client = PubMedClient(api_key=settings.pubmed_api_key)
    data_source = "pubmed"
    source_message = None
    try:
        total_count, articles = client.search(payload.keyword, payload.limit)
    except PubMedClientError as exc:
        if not settings.use_mock_on_error:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        total_count, articles = load_mock_articles(payload.keyword, payload.limit)
        data_source = "mock"
        source_message = "PubMed 调用失败，已使用本地 Mock 数据兜底。"

    return SearchResponse(
        keyword=payload.keyword,
        total_count=total_count,
        returned_count=len(articles),
        articles=[Article(**article.to_dict()) for article in articles],
        data_source=data_source,
        source_message=source_message,
    )


@router.post("/analyze")
def analyze_pubmed_articles(payload: AnalyzeRequest) -> dict:
    articles = [_to_pubmed_article(article) for article in payload.articles]
    try:
        return analyze_articles(articles, current_year=payload.current_year)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/top-impact")
def top_impact_pubmed_articles(payload: TopImpactRequest) -> dict:
    articles = [_to_pubmed_article(article) for article in payload.articles]
    try:
        metrics = load_journal_metrics()
        enriched_articles = enrich_articles(articles, metrics)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "years": payload.years,
        "limit": payload.limit,
        "articles": top_impact_articles(
            enriched_articles,
            current_year=payload.current_year,
            years=payload.years,
            limit=payload.limit,
        ),
    }


@router.post("/review")
def review_pubmed_articles(payload: ReviewRequest) -> dict:
    settings = get_settings()
    articles = [_to_pubmed_article(article) for article in payload.articles]
    try:
        return generate_review(
            articles,
            api_key=settings.ai_api_key,
            provider=settings.ai_provider,
            model=settings.ai_model,
            use_mock_on_error=settings.use_mock_on_error,
        )
    except ReviewError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _to_pubmed_article(article: Article) -> PubMedArticle:
    return PubMedArticle(
        pmid=article.pmid,
        title=article.title,
        abstract=article.abstract,
        year=article.year,
        journal=article.journal,
        authors=article.authors,
        doi=article.doi,
    )
