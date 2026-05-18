# FsaiToJson

Converts FSAI enforcement order PDFs to JSON.

## Usage

```sh
uv run fsai-parser ./pdfs/              # all PDFs in dir → stdout
uv run fsai-parser ./pdfs/ -o out.json  # write to file
```

Detects order type from each PDF's content (`closure_order`, `improvement_order`, `prohibition_order`, `prosecutions`). Files that can't be identified are skipped with a warning on stderr.

## Development

```sh
uv sync --group dev
uv run pytest
```

## Known limitations / TODO

- **Performance:** `pdfplumber` (via `pdfminer`) does full layout analysis per page and runs ~350ms/file. For larger batches, the per-file loop in `cli.py` could be parallelised with `ProcessPoolExecutor` for a 4–8x speedup without changing the parsing logic.
