from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from typing import Any

import requests


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedClientError(RuntimeError):
    pass


@dataclass
class PubMedArticle:
    pmid: str
    title: str
    abstract: str
    year: int | None
    journal: str
    authors: list[str]
    doi: str | None = None
    journal_abbreviation: str = ""
    issns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PubMedClient:
    api_key: str = ""
    timeout: int = 20

    def search(self, keyword: str, limit: int = 20) -> tuple[int, list[PubMedArticle]]:
        total_count, pmids = self.esearch(keyword, limit)
        if not pmids:
            return total_count, []
        return total_count, self.efetch(pmids)

    def esearch(self, keyword: str, limit: int) -> tuple[int, list[str]]:
        response = self._request(
            "esearch.fcgi",
            {
                "db": "pubmed",
                "term": keyword,
                "retmode": "json",
                "retmax": limit,
                "sort": "relevance",
            },
        )
        payload = self._json(response, "PubMed esearch returned invalid JSON")
        result = payload.get("esearchresult", {})
        total_count = self._parse_count(result.get("count", 0))
        pmids = [str(item) for item in result.get("idlist", [])]
        return total_count, pmids

    def esummary(self, pmids: list[str]) -> dict[str, Any]:
        if not pmids:
            return {}
        response = self._request(
            "esummary.fcgi",
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
            },
        )
        return self._json(response, "PubMed esummary returned invalid JSON")

    def efetch(self, pmids: list[str]) -> list[PubMedArticle]:
        if not pmids:
            return []
        response = self._request(
            "efetch.fcgi",
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
            },
        )
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise PubMedClientError("PubMed efetch returned invalid XML") from exc

        articles: list[PubMedArticle] = []
        for article_node in root.findall(".//PubmedArticle"):
            article = self._parse_article(article_node)
            if article:
                articles.append(article)
        return articles

    def _request(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        if self.api_key:
            params["api_key"] = self.api_key
        try:
            response = requests.get(
                f"{BASE_URL}/{endpoint}",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise PubMedClientError(f"PubMed {endpoint} request failed: {exc}") from exc
        return response

    @staticmethod
    def _json(response: requests.Response, error_message: str) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise PubMedClientError(error_message) from exc

    @staticmethod
    def _parse_count(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise PubMedClientError("PubMed esearch returned invalid result count") from exc

    def _parse_article(self, node: ET.Element) -> PubMedArticle | None:
        pmid = self._text(node, ".//MedlineCitation/PMID")
        if not pmid:
            return None

        article_node = node.find(".//MedlineCitation/Article")
        title = self._join_text(article_node.find("ArticleTitle") if article_node is not None else None)
        abstract_parts = [
            self._join_text(part)
            for part in node.findall(".//Abstract/AbstractText")
            if self._join_text(part)
        ]
        abstract = "\n".join(abstract_parts)
        journal = self._text(node, ".//Journal/Title") or self._text(node, ".//Journal/ISOAbbreviation")
        year = self._extract_year(node)
        authors = self._extract_authors(node)
        doi = self._extract_doi(node)

        return PubMedArticle(
            pmid=pmid,
            title=title or "(No title)",
            abstract=abstract,
            year=year,
            journal=journal or "(Unknown journal)",
            authors=authors,
            doi=doi,
            journal_abbreviation=self._text(node, ".//Journal/ISOAbbreviation"),
            issns=list(dict.fromkeys(
                value for value in [
                    *(self._join_text(item) for item in node.findall(".//Journal/ISSN")),
                    self._text(node, ".//MedlineJournalInfo/ISSNLinking"),
                ] if value
            )),
        )

    def _extract_year(self, node: ET.Element) -> int | None:
        candidates = [
            self._text(node, ".//JournalIssue/PubDate/Year"),
            self._text(node, ".//ArticleDate/Year"),
            self._text(node, ".//PubMedPubDate/Year"),
            self._text(node, ".//JournalIssue/PubDate/MedlineDate"),
        ]
        for value in candidates:
            if not value:
                continue
            match = re.search(r"\d{4}", value)
            if match:
                return int(match.group(0))
        return None

    def _extract_authors(self, node: ET.Element) -> list[str]:
        authors: list[str] = []
        for author in node.findall(".//AuthorList/Author"):
            collective = self._text(author, "CollectiveName")
            if collective:
                authors.append(collective)
                continue
            last = self._text(author, "LastName")
            initials = self._text(author, "Initials")
            name = " ".join(part for part in [last, initials] if part)
            if name:
                authors.append(name)
        return authors

    def _extract_doi(self, node: ET.Element) -> str | None:
        for article_id in node.findall(".//ArticleIdList/ArticleId"):
            if article_id.attrib.get("IdType") == "doi" and article_id.text:
                return article_id.text.strip()
        for elocation_id in node.findall(".//ELocationID"):
            if elocation_id.attrib.get("EIdType") == "doi" and elocation_id.text:
                return elocation_id.text.strip()
        return None

    @staticmethod
    def _text(node: ET.Element, path: str) -> str:
        item = node.find(path)
        return "".join(item.itertext()).strip() if item is not None else ""

    @staticmethod
    def _join_text(node: ET.Element | None) -> str:
        return "".join(node.itertext()).strip() if node is not None else ""
