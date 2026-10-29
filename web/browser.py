"""Pyodide entry points: img2table runs here, Tesseract runs in JavaScript.

OCR is split into two calls because tesseract.js is asynchronous and lives on the
page, while img2table expects a synchronous hocr(image) method:
1. ocr_input() decodes and deskews the image and writes the rule-free copy for OCR.
2. extract() hands the resulting hOCR back to img2table to build the tables.
PDFs are rendered to PNG by pdf.js on the page, so each page takes the image path.
"""

import concurrent.futures
import json
import sys
import types
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def sauvola(src, max_value, kind, block_size, k, binarizationMethod=None, r=128):
    """Port of cv2.ximgproc.niBlackThreshold (Sauvola), absent from Pyodide's OpenCV."""
    mean = cv2.boxFilter(src, cv2.CV_32F, (block_size, block_size), borderType=cv2.BORDER_REPLICATE)
    square = cv2.sqrBoxFilter(src, cv2.CV_32F, (block_size, block_size), borderType=cv2.BORDER_REPLICATE)
    with np.errstate(invalid="ignore"):  # Rounding can make flat regions' variance slightly negative.
        std = np.sqrt(square - mean * mean)
    thresh = mean * (np.float32(1) + np.float32(k) * (std / np.float32(r) - np.float32(1)))
    # OpenCV saturates NaN to 0 when converting the threshold back to 8 bits.
    thresh = np.clip(np.rint(np.nan_to_num(thresh, nan=0)), 0, 255).astype(np.uint8)
    mask = src > thresh if kind == cv2.THRESH_BINARY else src <= thresh
    return np.where(mask, np.uint8(max_value), np.uint8(0))


if not hasattr(cv2, "ximgproc"):
    cv2.ximgproc = types.SimpleNamespace(niBlackThreshold=sauvola, BINARIZATION_SAUVOLA=1)


class SerialExecutor:
    """Pyodide cannot start threads; img2table only uses its pool for map()."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, fn, *iterables):
        return list(map(fn, *iterables))


concurrent.futures.ThreadPoolExecutor = SerialExecutor
# pypdfium2 has no WebAssembly build; img2table imports it even for images.
sys.modules["pypdfium2"] = types.SimpleNamespace(PdfDocument=None, PdfTextPage=None)

from img2table.document import Image as TableImage  # noqa: E402
from img2table.ocr import TesseractOCR  # noqa: E402

from converter import convert_table, parse_pages, prepare, remove_rules, workbook  # noqa: E402

OCR_PATH = "/tmp/ocr.png"
XLSX_PATH = "/tmp/tables.xlsx"
state = {}


class BrowserOCR(TesseractOCR):
    def __init__(self, hocr):  # Skips the parent's checks for a tesseract executable.
        self.hocr_text = hocr
        self.n_threads = 1

    def hocr(self, image):
        return self.hocr_text


def pages(text):
    """Zero-based page indexes from text such as "1, 3-5", or None for all pages."""
    return json.dumps(parse_pages(text))


def start(name):
    """Begin a source file; PDF pages arrive one PNG at a time and share one workbook."""
    state.update(name=name, tables=[])
    Path(XLSX_PATH).unlink(missing_ok=True)


def ocr_input(data, name, rotation=0):
    prepared, _ = prepare(data.to_bytes(), name, rotation)  # data is a JS Uint8Array proxy.
    state["doc"] = TableImage(prepared, detect_rotation=True)
    Image.fromarray(remove_rules(state["doc"].images[0])).save(OCR_PATH)
    return OCR_PATH


def extract(hocr, page=1, borderless=False, implicit=False, confidence=50):
    raw = state["doc"].extract_tables(
        ocr=BrowserOCR(hocr),
        implicit_rows=implicit,
        implicit_columns=implicit,
        borderless_tables=borderless,
        min_confidence=confidence,
    )
    stem = Path(state["name"]).stem
    tables = [convert_table(t, f"{stem} p{page} t{i + 1}", page) for i, t in enumerate(raw)]
    state["tables"] += tables
    if state["tables"]:
        Path(XLSX_PATH).write_bytes(workbook(state["tables"]))
    return json.dumps([{"name": t.name, "rows": t.rows} for t in tables])
