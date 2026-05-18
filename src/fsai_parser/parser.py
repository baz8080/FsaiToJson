from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pdfplumber


def parse_date(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    try:
        return datetime.strptime(stripped, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return stripped


def to_snake_case(name: str | None) -> str:
    if not name:
        return ""
    return name.lower().replace(" ", "_").replace("\n", "_")


def get_order_type(pdf: pdfplumber.PDF) -> str:
    text = pdf.pages[0].extract_text() or ""
    lines = text.splitlines()
    return lines[0].strip() if lines else ""



_TYPE_PREFIXES: list[tuple[str, str]] = [
    ("Closure Orders", "closure_order"),
    ("Improvement Orders", "improvement_order"),
    ("Prohibition Orders", "prohibition_order"),
    ("Prosecutions", "prosecution"),
]

def detect_type(pdf: pdfplumber.PDF) -> str | None:
    text = pdf.pages[0].extract_text() or ""
    for line in text.splitlines():
        for prefix, canonical in _TYPE_PREFIXES:
            if line.strip().startswith(prefix):
                return canonical
    return None


def parse_enforcement_pdf(pdf: pdfplumber.PDF) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for page in pdf.pages:
        uris = [
            a["uri"]
            for a in sorted(page.annots or [], key=lambda a: a["top"])
            if a.get("uri")
        ]

        table = page.extract_table()
        if not table:
            continue

        uri_iter = iter(uris)
        header = table[0]
        # Exclude the last column (Enforcement Order download link)
        keys = [to_snake_case(h) for h in header[:-1]]

        for row in table[1:]:
            if not any(row):
                continue

            last_col = row[-1] or ""
            url = next(uri_iter, None) if "Download" in last_col else None

            entry: dict[str, Any] = {}
            for i, key in enumerate(keys):
                value = (row[i] or "").replace("\n", " ")
                entry[key] = parse_date(value) if key.startswith("date_") else value
            entry["order_url"] = url
            rows.append(entry)

    return rows


def make_dedup_key(row: dict[str, Any]) -> tuple:
    t = row["type"]
    if t == "prosecution":
        return (t, row.get("date_of_hearing", ""), row.get("premises", ""))
    return (t, row.get("date_served", ""), row.get("premises", ""))


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        key = make_dedup_key(row)
        if key not in seen:
            seen[key] = row
    return list(seen.values())


def to_json(rows: list[dict[str, Any]], indent: int = 2) -> str:
    return json.dumps(rows, indent=indent)
