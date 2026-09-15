from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.services.pubmed_client import PubMedArticle


DEFAULT_DATABASE_URL = "sqlite:///data/pubmed_demo.db"


def sqlite_path_from_url(database_url: str = DEFAULT_DATABASE_URL) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Only sqlite:/// database URLs are supported for this demo")
    return Path(database_url.removeprefix(prefix))


@contextmanager
def connect(database_url: str = DEFAULT_DATABASE_URL) -> Iterator[sqlite3.Connection]:
    db_path = sqlite_path_from_url(database_url)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(database_url: str = DEFAULT_DATABASE_URL) -> None:
    with connect(database_url) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                limit_count INTEGER NOT NULL,
                total_count INTEGER NOT NULL,
                returned_count INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS articles (
                pmid TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                abstract TEXT NOT NULL,
                year INTEGER,
                journal TEXT NOT NULL,
                authors_json TEXT NOT NULL,
                doi TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS search_articles (
                search_id INTEGER NOT NULL,
                pmid TEXT NOT NULL,
                rank INTEGER NOT NULL,
                PRIMARY KEY (search_id, pmid),
                FOREIGN KEY (search_id) REFERENCES search_history(id) ON DELETE CASCADE,
                FOREIGN KEY (pmid) REFERENCES articles(pmid) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_search_history_keyword
                ON search_history(keyword);

            CREATE INDEX IF NOT EXISTS idx_search_articles_pmid
                ON search_articles(pmid);
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(articles)")}
        if "journal_abbreviation" not in columns:
            conn.execute("ALTER TABLE articles ADD COLUMN journal_abbreviation TEXT NOT NULL DEFAULT ''")
        if "issns_json" not in columns:
            conn.execute("ALTER TABLE articles ADD COLUMN issns_json TEXT NOT NULL DEFAULT '[]'")


def save_search_result(
    keyword: str,
    limit: int,
    total_count: int,
    articles: list[PubMedArticle],
    database_url: str = DEFAULT_DATABASE_URL,
) -> int:
    init_db(database_url)
    with connect(database_url) as conn:
        cursor = conn.execute(
            """
            INSERT INTO search_history (keyword, limit_count, total_count, returned_count)
            VALUES (?, ?, ?, ?)
            """,
            (keyword, limit, total_count, len(articles)),
        )
        search_id = int(cursor.lastrowid)

        for index, article in enumerate(articles, start=1):
            upsert_article(conn, article)
            conn.execute(
                """
                INSERT OR REPLACE INTO search_articles (search_id, pmid, rank)
                VALUES (?, ?, ?)
                """,
                (search_id, article.pmid, index),
            )

        return search_id


def upsert_article(conn: sqlite3.Connection, article: PubMedArticle) -> None:
    conn.execute(
        """
        INSERT INTO articles (
            pmid, title, abstract, year, journal, authors_json, doi, journal_abbreviation, issns_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pmid) DO UPDATE SET
            title = excluded.title,
            abstract = excluded.abstract,
            year = excluded.year,
            journal = excluded.journal,
            authors_json = excluded.authors_json,
            doi = excluded.doi,
            journal_abbreviation = excluded.journal_abbreviation,
            issns_json = excluded.issns_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            article.pmid,
            article.title,
            article.abstract,
            article.year,
            article.journal,
            json.dumps(article.authors, ensure_ascii=False),
            article.doi,
            article.journal_abbreviation,
            json.dumps(article.issns),
        ),
    )


def list_search_history(
    database_url: str = DEFAULT_DATABASE_URL,
    limit: int = 20,
) -> list[dict]:
    init_db(database_url)
    with connect(database_url) as conn:
        rows = conn.execute(
            """
            SELECT id, keyword, limit_count, total_count, returned_count, created_at
            FROM search_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_search_articles(search_id: int, database_url: str = DEFAULT_DATABASE_URL) -> list[PubMedArticle]:
    init_db(database_url)
    with connect(database_url) as conn:
        rows = conn.execute(
            """
            SELECT a.pmid, a.title, a.abstract, a.year, a.journal, a.authors_json, a.doi, a.journal_abbreviation, a.issns_json
            FROM search_articles sa
            JOIN articles a ON a.pmid = sa.pmid
            WHERE sa.search_id = ?
            ORDER BY sa.rank ASC
            """,
            (search_id,),
        ).fetchall()

    return [
        PubMedArticle(
            pmid=row["pmid"],
            title=row["title"],
            abstract=row["abstract"],
            year=row["year"],
            journal=row["journal"],
            authors=json.loads(row["authors_json"]),
            doi=row["doi"],
            journal_abbreviation=row["journal_abbreviation"],
            issns=json.loads(row["issns_json"]),
        )
        for row in rows
    ]
