"""Build a reproducible local JIF snapshot from public publisher tables.

Run from the project root: python -m scripts.refresh_publisher_metrics
No publisher requests are made during a literature search.
"""
from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from html.parser import HTMLParser
from html import unescape
from pathlib import Path

import requests

from app.services.journal_metrics import COLUMNS, parse_metrics_csv, normalize_name

YEAR = 2025
SOURCES = {
    "frontiers": "https://www.frontiersin.org/about/impact",
    "nature": "https://www.nature.com/nature-portfolio/about-journals/journal-metrics",
}
TARGET = Path("data/journal_metrics_publishers.csv")
ALIASES = {
    "Scientific Reports": "Sci Rep",
    "Nature Communications": "Nat Commun",
    "Scientific Data": "Sci Data",
    "Frontiers in Oncology": "Front Oncol",
    "Frontiers in Medicine": "Front Med (Lausanne)",
    "Frontiers in Public Health": "Front Public Health",
    "Frontiers in Psychology": "Front Psychol",
    "Frontiers in Pharmacology": "Front Pharmacol",
    "Frontiers in Neurology": "Front Neurol",
    "Frontiers in Microbiology": "Front Microbiol",
}


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def extract_metrics(html: str, publisher: str) -> list[dict]:
    # Fail closed when the annual page changes; never label next year's data as 2025.
    plain = unescape(re.sub(r"<[^>]*>", " ", html))
    if publisher == "frontiers":
        year_matches = re.findall(r"JCR\s+(20\d{2})", plain)
    else:
        year_matches = re.findall(r"(20\d{2})\s+Journal Metrics", plain)
    if not year_matches or set(year_matches) != {str(YEAR)}:
        raise ValueError(f"{publisher}: metric year changed or could not be verified")
    parser = TableParser()
    parser.feed(html)
    records = []
    for table in parser.tables:
        if not table or "Journal Impact Factor" not in table[0]:
            continue
        header = table[0]
        impact_index = header.index("Journal Impact Factor")
        quartile_index = header.index("JIF rank quartile") if "JIF rank quartile" in header else None
        for cells in table[1:]:
            if not cells or not any(cells):
                continue
            if len(cells) != len(header):
                raise ValueError(f"{publisher}: unexpected table shape")
            value = cells[impact_index]
            if value in {"-", "", "N/A", "n/a", "\u2014"}:
                continue
            float(value)
            quartile = cells[quartile_index] if quartile_index is not None else ""
            if quartile == "-":
                quartile = ""
            records.append(dict.fromkeys(COLUMNS, "") | {
                "journal_name": cells[0],
                "journal_alias": ALIASES.get(cells[0], ""),
                "impact_factor": value,
                "quartile": quartile,
                "source_year": str(YEAR),
                "source": SOURCES[publisher],
                "quartile_system": "JCR JIF quartile (publisher-reported; category unspecified)" if quartile else "",
            })
    if not records:
        raise ValueError(f"{publisher}: no JIF table found")
    return records


def main():
    records = []
    for publisher, url in SOURCES.items():
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        rows = extract_metrics(response.text, publisher)
        print(f"{publisher}: {len(rows)} journals, JIF {YEAR}")
        records.extend(rows)
    # Manually verified publisher pages supplement the two bulk tables.
    curated = parse_metrics_csv(Path("data/journal_metrics_curated.csv").read_text(encoding="utf-8"))
    if any(row["source_year"] != str(YEAR) for row in curated):
        raise ValueError("Curated metrics must be reverified for the requested year")
    records.extend(curated)
    # Reuse only names/aliases from the old demo, never its unverified IF values.
    with Path("data/journal_metrics.csv").open(encoding="utf-8-sig", newline="") as stream:
        aliases = {normalize_name(r["journal_name"]): r["journal_alias"] for r in csv.DictReader(stream)}
    for record in records:
        if not record["journal_alias"]:
            record["journal_alias"] = aliases.get(normalize_name(record["journal_name"]), "")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(sorted(records, key=lambda row: row["journal_name"].casefold()))
    text = buffer.getvalue()
    parse_metrics_csv(text)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=TARGET.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, TARGET)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    print(f"Validated {len(records)} journals -> {TARGET}")


if __name__ == "__main__":
    main()
