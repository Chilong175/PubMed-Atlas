from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

import requests


DEEPSEEK_CHAT_COMPLETIONS_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
MAX_ARTICLES = 20
MAX_ABSTRACT_CHARS = 800
MAX_CONTEXT_CHARS = 12000


class ArticleForReview(Protocol):
    pmid: str
    title: str
    abstract: str
    year: int | None
    journal: str


class ReviewError(RuntimeError):
    pass


@dataclass
class ReviewSource:
    pmid: str
    title: str
    year: int | None
    journal: str
    abstract: str
    impact_factor: float | None = None


@dataclass
class ReviewContext:
    text: str
    sources: list[ReviewSource]


def build_review_context(
    articles: Iterable[ArticleForReview],
    max_articles: int = MAX_ARTICLES,
    max_abstract_chars: int = MAX_ABSTRACT_CHARS,
    max_context_chars: int = MAX_CONTEXT_CHARS,
) -> ReviewContext:
    candidates = [_to_review_source(article) for article in articles if _safe_text(getattr(article, "abstract", ""))]
    candidates.sort(
        key=lambda article: (
            article.impact_factor is not None,
            article.impact_factor or 0,
            article.year or 0,
        ),
        reverse=True,
    )

    selected: list[ReviewSource] = []
    chunks: list[str] = []
    current_length = 0

    for index, article in enumerate(candidates[:max_articles], start=1):
        abstract = article.abstract[:max_abstract_chars].strip()
        chunk = (
            f"文献{index}\n"
            f"PMID：{article.pmid}\n"
            f"标题：{article.title}\n"
            f"年份：{article.year or '未知'}\n"
            f"期刊：{article.journal}\n"
            f"摘要：{abstract}\n"
        )
        if current_length + len(chunk) > max_context_chars:
            break
        chunks.append(chunk)
        selected.append(article)
        current_length += len(chunk)

    return ReviewContext(text="\n".join(chunks), sources=selected)


def build_review_prompt(context: ReviewContext) -> str:
    if not context.sources:
        raise ReviewError("当前文献缺少摘要，无法生成可靠综述。")

    return (
        "你是医学文献分析助手。请仅根据下面给出的 PubMed 文献标题和摘要，"
        "生成中文综述。\n\n"
        "要求：\n"
        "1. 中文输出。\n"
        "2. 约 500 字。\n"
        "3. 分点呈现。\n"
        "4. 概括主要研究方向、常见方法、趋势和局限。\n"
        "5. 不要编造摘要中没有的信息。\n"
        "6. 不要逐篇翻译。\n\n"
        f"文献材料：\n{context.text}"
    )


def generate_review(
    articles: Iterable[ArticleForReview],
    api_key: str = "",
    provider: str = "deepseek",
    model: str = "",
    use_mock_on_error: bool = True,
) -> dict:
    context = build_review_context(articles)
    try:
        prompt = build_review_prompt(context)
    except ReviewError as exc:
        return {
            "review": str(exc),
            "source_count": 0,
            "used_fallback": True,
        }

    if provider != "deepseek":
        if use_mock_on_error:
            return _fallback_review(context, reason=f"暂不支持的模型供应商：{provider}")
        raise ReviewError(f"Unsupported AI provider: {provider}")

    if not api_key:
        if use_mock_on_error:
            return _fallback_review(context, reason="未配置 AI_API_KEY")
        raise ReviewError("AI_API_KEY is required")

    try:
        review = _call_deepseek(prompt=prompt, api_key=api_key, model=model or DEFAULT_MODEL)
    except ReviewError as exc:
        if use_mock_on_error:
            return _fallback_review(context, reason=str(exc))
        raise

    return {
        "review": review,
        "source_count": len(context.sources),
        "used_fallback": False,
    }


def _call_deepseek(prompt: str, api_key: str, model: str) -> str:
    try:
        response = requests.post(
            DEEPSEEK_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是严谨的医学文献综述助手。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise ReviewError(f"AI 综述生成失败：{exc}") from exc

    content = str(content).strip()
    if not content:
        raise ReviewError("AI 综述生成失败：返回内容为空")
    return content


def _fallback_review(context: ReviewContext, reason: str) -> dict:
    years = sorted({source.year for source in context.sources if source.year})
    journals = []
    for source in context.sources:
        if source.journal not in journals:
            journals.append(source.journal)
    year_text = f"{years[0]}-{years[-1]}" if years else "年份未知"
    journal_text = "、".join(journals[:5]) if journals else "期刊未知"

    review = (
        f"当前为兜底综述示例，原因：{reason}。\n"
        f"1. 本次纳入 {len(context.sources)} 篇带摘要文献，覆盖时间范围为 {year_text}，"
        f"主要来源期刊包括 {journal_text}。\n"
        "2. 从标题和摘要看，研究重点集中在疾病机制、治疗响应、预测标志物和临床转化等方向。\n"
        "3. 常见方法包括队列分析、分子检测、免疫微环境评估和疗效结局比较。\n"
        "4. 未来综述可进一步结合更多高影响力文献，比较不同研究方向的证据强度和局限性。"
    )
    return {
        "review": review,
        "source_count": len(context.sources),
        "used_fallback": True,
    }


def _to_review_source(article: ArticleForReview) -> ReviewSource:
    return ReviewSource(
        pmid=str(getattr(article, "pmid", "")),
        title=_safe_text(getattr(article, "title", "")) or "(No title)",
        abstract=_safe_text(getattr(article, "abstract", "")),
        year=getattr(article, "year", None),
        journal=_safe_text(getattr(article, "journal", "")) or "(Unknown journal)",
        impact_factor=getattr(article, "impact_factor", None),
    )


def _safe_text(value: object) -> str:
    return str(value or "").strip()

