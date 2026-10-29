# Table to Excel

A free, local, CPU-only table converter with a browser interface. MIT licensed.
Uses img2table (MIT) and Tesseract (Apache-2.0); dependency licenses remain applicable.

## Get started on Windows

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
2. Install [Tesseract OCR](https://tesseract-ocr.github.io/tessdoc/Installation.html), including English language data. The app detects the standard `C:\Program Files\Tesseract-OCR` location; otherwise put Tesseract on PATH.
3. Double-click **Start-Windows.bat**. The first launch downloads Python packages and requires internet. Later conversion runs locally without network access. Keep the launcher window open; close it to stop the app.
4. Choose images or PDFs, select **Extract tables**, review/edit the cells, then download Excel or CSV.

The app is installed and dependencies are ready on the development computer.

## Linux / macOS

Install uv and Tesseract using your package manager (`sudo apt install tesseract-ocr` on Ubuntu, `brew install tesseract` on macOS), then:

```sh
uv sync --frozen --no-dev --python 3.12
uv run --no-sync streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

## Features

- PNG, JPEG, BMP, WebP, single-frame TIFF, native and scanned PDFs.
- Multiple tables per page and batches of up to 20 files.
- PDF page selection, automatic deskew, image rotation, percentage crop with preview.
- Optional borderless detection and missing-divider detection.
- Editable cells, add/delete rows, name worksheets, exclude tables.
- One worksheet per table; optional merged cells; wrapped text, column sizing, frozen header.
- Combined XLSX or ZIP of CSV files; leading zeros preserved as text.
- No cloud OCR, account, telemetry, or conversion fees. App listens on loopback only.

## Limits and honest expectations

This is a working initial release, not proven parity with every paid converter. OCR is fallible; check amounts and identifiers against originals. Handwriting, nested/irregular tables, dark backgrounds, badly blurred scans and exact font/color reconstruction are not supported reliably. Formulas are not inferred. All Excel values are text; CSV formula-like values are prefixed with an apostrophe for safe opening. Unmerge before editing covered cells: merged Excel ranges retain only the top-left value. After adding/deleting rows, disable merged-cell preservation because source coordinates no longer match.

Each file is limited to 30 MB, images to 40 megapixels, PDFs to 50 pages. Encrypted PDFs and multi-frame TIFF are rejected with guidance. Processing is sequential to limit CPU pressure; large batches can take minutes. There is no mid-extraction cancellation button; stop the launcher to abort. Uploaded files/results live in the local app session; clear results and close the app when done. Downloads remain wherever your browser saves them. This is a single-user local app; do not expose its port publicly.

For other languages install Tesseract language packs and set the language code (e.g. `eng+fra`). If no table appears, try cropping to one table, enabling borderless detection, lowering confidence, or scanning at a higher resolution. Borderless tables generally need at least three rows. First OCR invocation can be slower while numerical routines initialize.

## Development and tests

```sh
uv sync --frozen --python 3.12
uv run pytest -q
uv run ruff check .
```

Tests include real CPU OCR on a generated labeled table, app review rendering, workbook reopening/merges/formula safety, CSV safety, page ranges, crop/rotation and invalid input. GitHub Actions runs them on Linux. The lockfile records exact package versions. More real-world multilingual, borderless and merged-cell accuracy benchmarks are needed before a stable public release. Native installers, automatic language-pack setup and a larger document corpus are future work.

Contributions: open an issue with a synthetic or redacted example, expected cells, OS and Tesseract version. Never submit private documents. Run the suite before submitting changes. Report security issues privately to the repository maintainer rather than including sensitive files in public issues.

## Why this engine?

[img2table](https://github.com/xavctn/img2table) uses OpenCV for CPU-friendly structure detection and supports Tesseract without model downloads. PaddleOCR/PP-Structure can be evaluated as a future alternative for complex layouts; it is not silently installed or required here.
