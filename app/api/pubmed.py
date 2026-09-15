from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models.schemas import Article, SearchRequest, SearchResponse
from app.services.pubmed_client import PubMedClient, PubMedClientError


router = APIRouter(prefix="/api", tags=["pubmed"])


@router.post("/search", response_model=SearchResponse)
def search_pubmed(payload: SearchRequest) -> SearchResponse:
    settings = get_settings()
    client = PubMedClient(api_key=settings.pubmed_api_key)
    try:
        total_count, articles = client.search(payload.keyword, payload.limit)
    except PubMedClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SearchResponse(
        keyword=payload.keyword,
        total_count=total_count,
        returned_count=len(articles),
        articles=[Article(**article.to_dict()) for article in articles],
    )
