from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings


app = FastAPI(
    title="PubMed Literature Search Demo",
    description="PubMed 文献检索、统计分析、可视化和 AI 综述 Demo",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "pubmed-demo",
        "pubmed_api_key_configured": bool(settings.pubmed_api_key),
        "ai_provider": settings.ai_provider,
        "database_url": settings.database_url,
    }

