from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pdfplumber

from fsai_parser.parser import deduplicate, detect_type, parse_enforcement_pdf, to_json


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fsai-parser",
        description="Convert FSAI enforcement order PDFs to a single JSON array.",
    )
    p.add_argument("directory", type=Path, help="Directory containing PDF files")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write JSON to FILE instead of stdout",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()

    if not args.directory.is_dir():
        sys.exit(f"error: not a directory: {args.directory}")

    pdfs = sorted(args.directory.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"error: no PDF files found in {args.directory}")

    all_rows: list[dict] = []
    skipped = 0

    for pdf_path in pdfs:
        with pdfplumber.open(pdf_path) as pdf:
            order_type = detect_type(pdf)
            if order_type is None:
                print(f"warning: unrecognised type in {pdf_path.name!r}, skipping", file=sys.stderr)
                skipped += 1
                continue

            rows = parse_enforcement_pdf(pdf)
            for row in rows:
                combined = {"type": order_type} | row
                if order_type == "prosecution":
                    combined.pop("order_url", None)
                all_rows.append(combined)

    deduped = deduplicate(all_rows)

    result = to_json(deduped)

    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result)


if __name__ == "__main__":
    main()
