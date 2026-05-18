from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fsai_parser.parser import deduplicate, detect_type, get_order_type, make_dedup_key, parse_date, parse_enforcement_pdf, to_snake_case


# --- detect_type ---

def _pdf_with_first_line(text: str):
    mock_pdf = MagicMock()
    mock_pdf.pages[0].extract_text.return_value = text
    return mock_pdf


@pytest.mark.parametrize("first_line,expected", [
    ("Closure Orders", "closure_order"),
    ("Improvement Orders", "improvement_order"),
    ("Improvement Orders (something extra)", "improvement_order"),
    ("Prohibition Orders", "prohibition_order"),
    ("Prosecutions", "prosecution"),
])
def test_detect_type_known(first_line, expected):
    assert detect_type(_pdf_with_first_line(first_line)) == expected


def test_detect_type_prosecution_with_page_number():
    text = "1/1\nProsecutions\nProsecutions are listed for three months from the date of hearing"
    assert detect_type(_pdf_with_first_line(text)) == "prosecution"



def test_detect_type_unknown():
    assert detect_type(_pdf_with_first_line("Something Else")) is None


def test_detect_type_empty_page():
    assert detect_type(_pdf_with_first_line(None)) is None


# --- make_dedup_key ---

def test_dedup_key_prosecution_uses_hearing_and_premises():
    row = {"type": "prosecution", "date_of_hearing": "2024-01-15", "premises": "Acme Ltd"}
    assert make_dedup_key(row) == ("prosecution", "2024-01-15", "Acme Ltd")


def test_dedup_key_prosecution_ignores_order_url():
    row = {"type": "prosecution", "date_of_hearing": "2024-01-15", "premises": "Acme Ltd", "order_url": "http://x"}
    assert make_dedup_key(row) == ("prosecution", "2024-01-15", "Acme Ltd")


@pytest.mark.parametrize("order_type", ["closure_order", "improvement_order", "prohibition_order"])
def test_dedup_key_non_prosecution_uses_date_and_premises(order_type):
    row = {"type": order_type, "date_served": "2024-01-15", "premises": "Acme Ltd", "order_url": None}
    assert make_dedup_key(row) == (order_type, "2024-01-15", "Acme Ltd")


# --- deduplicate ---

def _row(type_, premises, date_served="2024-01-15", order_url=None):
    return {"type": type_, "premises": premises, "date_served": date_served, "order_url": order_url}


def test_deduplicate_keeps_unique_rows():
    rows = [_row("closure_order", "A"), _row("closure_order", "B")]
    assert len(deduplicate(rows)) == 2


def test_deduplicate_removes_exact_duplicate():
    rows = [_row("closure_order", "A"), _row("closure_order", "A")]
    assert len(deduplicate(rows)) == 1


def test_deduplicate_keeps_first_seen():
    rows = [
        _row("closure_order", "A", order_url="http://original.com"),
        _row("closure_order", "A", order_url="http://different.com"),
    ]
    assert deduplicate(rows)[0]["order_url"] == "http://original.com"


# --- parse_date ---

@pytest.mark.parametrize("value,expected", [
    ("15/01/2024", "2024-01-15"),
    ("01/12/2023", "2023-12-01"),
    ("", ""),
    ("  ", ""),
])
def test_parse_date_valid(value, expected):
    assert parse_date(value) == expected


def test_parse_date_empty_lifted():
    # date_lifted is commonly empty — should return empty string, not raise
    assert parse_date("") == ""


def test_parse_date_invalid_passthrough():
    # Unrecognised format passes through unchanged rather than crashing
    assert parse_date("unknown") == "unknown"


# --- to_snake_case ---

def test_to_snake_case_basic():
    assert to_snake_case("Hello World") == "hello_world"


def test_to_snake_case_newline():
    assert to_snake_case("Hello\nWorld") == "hello_world"


def test_to_snake_case_empty():
    assert to_snake_case("") == ""


def test_to_snake_case_none():
    assert to_snake_case(None) == ""


def test_to_snake_case_already_snake():
    assert to_snake_case("hello_world") == "hello_world"


# --- get_order_type ---

def test_get_order_type_returns_first_line():
    mock_pdf = MagicMock()
    mock_pdf.pages[0].extract_text.return_value = "Closure Orders\nSome other text\n"
    assert get_order_type(mock_pdf) == "Closure Orders"


def test_get_order_type_strips_whitespace():
    mock_pdf = MagicMock()
    mock_pdf.pages[0].extract_text.return_value = "  Prohibition Orders  \nMore text"
    assert get_order_type(mock_pdf) == "Prohibition Orders"


def test_get_order_type_empty_page():
    mock_pdf = MagicMock()
    mock_pdf.pages[0].extract_text.return_value = None
    assert get_order_type(mock_pdf) == ""


# --- parse_enforcement_pdf ---

def _make_page(table, annots=None):
    page = MagicMock()
    page.extract_table.return_value = table
    page.annots = annots or []
    return page


def test_parse_skips_pages_without_table():
    mock_pdf = MagicMock()
    mock_pdf.pages = [_make_page(None)]
    assert parse_enforcement_pdf(mock_pdf) == []


def test_parse_skips_empty_rows():
    mock_pdf = MagicMock()
    header = ["Name", "Date", "Enforcement Order"]
    mock_pdf.pages = [_make_page([header, [None, None, None]])]
    assert parse_enforcement_pdf(mock_pdf) == []


def test_parse_basic_row():
    mock_pdf = MagicMock()
    header = ["Business Name", "Date Served", "Enforcement Order"]
    row = ["Acme Ltd", "15/01/2024", "Download"]
    annot = {"uri": "http://example.com/order.pdf", "top": 0}
    mock_pdf.pages = [_make_page([header, row], annots=[annot])]

    result = parse_enforcement_pdf(mock_pdf)

    assert len(result) == 1
    assert result[0]["business_name"] == "Acme Ltd"
    assert result[0]["date_served"] == "2024-01-15"
    assert result[0]["order_url"] == "http://example.com/order.pdf"


def test_parse_row_without_download_has_no_url():
    mock_pdf = MagicMock()
    header = ["Business Name", "Date", "Enforcement Order"]
    row = ["Acme Ltd", "2024-01-01", ""]
    mock_pdf.pages = [_make_page([header, row])]

    result = parse_enforcement_pdf(mock_pdf)

    assert result[0]["order_url"] is None


def test_parse_newlines_in_cells_are_replaced():
    mock_pdf = MagicMock()
    header = ["Business Name", "Date", "Enforcement Order"]
    row = ["Acme\nLtd", "2024-01-01", ""]
    mock_pdf.pages = [_make_page([header, row])]

    result = parse_enforcement_pdf(mock_pdf)

    assert result[0]["business_name"] == "Acme Ltd"
