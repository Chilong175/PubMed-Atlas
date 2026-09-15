from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(20, ge=1, le=100)


class Article(BaseModel):
    pmid: str
    title: str
    abstract: str
    year: int | None = None
    journal: str
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None


class SearchResponse(BaseModel):
    keyword: str
    total_count: int
    returned_count: int
    articles: list[Article]

