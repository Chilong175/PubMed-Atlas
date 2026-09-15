"""Validated local journal metrics; imported tables never mix with demo values."""
from __future__ import annotations

import csv
import io
import math
import os
import re
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

IMPORTED_METRICS_PATH = Path("data/journal_metrics_imported.csv")
COLUMNS = ["journal_name", "journal_alias", "issn", "eissn", "impact_factor", "quartile", "source_year", "source", "quartile_system"]


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"\w+", text.replace("&", " and ")))


def normalize_issn(value: str) -> str:
    value = re.sub(r"[\s-]", "", str(value or "")).upper()
    if not re.fullmatch(r"\d{7}[\dX]", value):
        return ""
    checksum = sum(int(char) * (8 - index) for index, char in enumerate(value[:7]))
    if (checksum + (10 if value[-1] == "X" else int(value[-1]))) % 11:
        return ""
    return value


def parse_metrics_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    required = {"journal_name", "impact_factor", "source_year", "source"}
    if not reader.fieldnames or required - set(reader.fieldnames):
        raise ValueError("CSV 必须包含 journal_name、impact_factor、source_year、source 列。")
    if len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("CSV 列名不能重复。")
    rows, keys, years = [], set(), set()
    try:
        for line, raw in enumerate(reader, 2):
            if line > 20001:
                raise ValueError("单次最多导入 20000 条期刊记录。")
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"第 {line} 行列数不正确。")
            row = {key: raw.get(key, "").strip() for key in COLUMNS}
            if not normalize_name(row["journal_name"]) or not row["source"]:
                raise ValueError(f"第 {line} 行期刊名称和数据来源不能为空。")
            try:
                value = float(row["impact_factor"])
                year = int(row["source_year"])
            except ValueError:
                raise ValueError(f"第 {line} 行 IF 或年份不是有效数字。") from None
            if not math.isfinite(value) or value < 0 or not 1900 <= year <= date.today().year:
                raise ValueError(f"第 {line} 行 IF 或年份超出有效范围。")
            row["quartile"] = row["quartile"].upper()
            if row["quartile"] not in {"", "Q1", "Q2", "Q3", "Q4"}:
                raise ValueError(f"第 {line} 行分区应为 Q1–Q4 或留空。")
            if row["quartile"] and not row["quartile_system"]:
                raise ValueError(f"第 {line} 行有分区时必须填写 quartile_system（分区体系/类别）。")
            identifiers = {"name:" + normalize_name(name) for name in [row["journal_name"], *row["journal_alias"].split(";")] if normalize_name(name)}
            for column in ("issn", "eissn"):
                if row[column]:
                    normalized = normalize_issn(row[column])
                    if not normalized:
                        raise ValueError(f"第 {line} 行 {column} 格式或校验位无效。")
                    identifiers.add("issn:" + normalized)
            if identifiers & keys:
                raise ValueError(f"第 {line} 行名称、别名或 ISSN 与其他记录重复，请先消除歧义。")
            keys.update(identifiers)
            years.add(year)
            rows.append(row)
    except csv.Error as exc:
        raise ValueError("CSV 格式错误，请检查引号和分隔符。") from exc
    if not rows:
        raise ValueError("CSV 没有期刊数据。")
    if len(years) != 1:
        raise ValueError("一次导入请使用同一指标年份，避免跨年 IF 混合排序。")
    return rows


def import_metrics(text: str) -> dict:
    rows = parse_metrics_csv(text)
    target = IMPORTED_METRICS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    # Validate every row before atomically replacing the active imported table.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return {"journal_count": len(rows), "source_year": int(rows[0]["source_year"]), "data_source": "imported"}
