import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from converter import Table, csv_bytes, extract, parse_pages, prepare, setup_tesseract, workbook

st.set_page_config(page_title="Table to Excel", page_icon="▦", layout="wide")
st.title("Table to Excel")
st.write("Turn pictures and PDFs into editable spreadsheets. Free, private, and processed on your CPU.")
st.caption("Files stay on this computer. No account, uploads to a cloud, or subscription.")
try:
    setup_tesseract()
except ValueError as error:
    st.error(str(error))
    st.stop()
files = st.file_uploader(
    "1 · Choose images or PDFs",
    type=["png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff", "pdf"],
    accept_multiple_files=True,
)
with st.expander("Extraction options · use these if the first result needs improvement"):
    borderless = st.checkbox("Find tables without borders (slower)")
    implicit = st.checkbox("Find rows and columns with missing dividing lines")
    confidence = st.slider(
        "Minimum OCR confidence",
        0,
        99,
        50,
        help="Lower this to include faint text. This is a filter, not a guarantee of accuracy.",
    )
    language = st.text_input(
        "Tesseract language code",
        "eng",
        help="For example eng, fra, deu, or eng+fra. Matching language packs must be installed.",
    )
    page_text = st.text_input("PDF pages (blank means all)", placeholder="1, 3-5")
    rotation = st.selectbox("Rotate images counterclockwise", [0, 90, 180, 270])
    crop_on = st.checkbox("Crop images to a table region (after rotation)")
    crop = None
    if crop_on:
        cols = st.columns(4)
        crop = tuple(
            col.number_input(label, 0, 100, value)
            for col, label, value in zip(cols, ["Left %", "Top %", "Right %", "Bottom %"], [0, 0, 100, 100])
        )
if files:
    with st.expander("Preview first source", expanded=True):
        if Path(files[0].name).suffix.lower() != ".pdf":
            try:
                preview, _ = prepare(files[0].getvalue(), files[0].name, rotation, crop)
                st.image(preview, width=650)
            except ValueError as error:
                st.error(str(error))
        else:
            st.caption("PDF pages are processed locally. Use the page selector above for a smaller batch.")
if st.button("2 · Extract tables", type="primary", disabled=not files):
    try:
        pages = parse_pages(page_text)
        if len(files) > 20:
            raise ValueError("Choose at most 20 files per batch.")
        st.session_state.tables = []
        progress = st.progress(0)
        for i, file in enumerate(files):
            with st.spinner(f"Reading {file.name} · large scans can take several minutes…"):
                try:
                    found = extract(
                        file.getvalue(),
                        file.name,
                        pages=pages,
                        language=language.strip(),
                        borderless=borderless,
                        confidence=confidence,
                        implicit=implicit,
                        rotation=rotation,
                        crop=crop,
                    )
                    st.session_state.tables.extend(found)
                    if not found:
                        st.warning(
                            f"{file.name}: no tables found. Try cropping, borderless detection, or a clearer scan."
                        )
                except Exception as error:
                    st.error(f"{file.name}: {error}")
            progress.progress((i + 1) / len(files))
        st.session_state.revision = st.session_state.get("revision", 0) + 1
    except ValueError as error:
        st.error(str(error))
if st.session_state.get("tables"):
    st.subheader("3 · Review and correct")
    st.info(
        "Check every table against the source. OCR can misread numbers. Values export as text to preserve leading zeros and avoid accidental formulas."
    )
    preserve = st.checkbox(
        "Preserve detected merged cells",
        True,
        help="Turn off if you edit individual cells inside a merged region or change table structure.",
    )
    reviewed = []
    revision = st.session_state.get("revision", 0)
    for i, table in enumerate(st.session_state.tables):
        with st.expander(f"{table.name} · {len(table.rows)} rows", expanded=True):
            include = st.checkbox("Include in download", True, key=f"include-{revision}-{i}")
            name = st.text_input("Worksheet name", table.name, key=f"name-{revision}-{i}")
            frame = pd.DataFrame(table.rows).fillna("").astype(str)
            frame.columns = [f"Column {c + 1}" for c in range(len(frame.columns))]
            edited = st.data_editor(frame, num_rows="dynamic", key=f"edit-{revision}-{i}", width="stretch")
            if include:
                reviewed.append(
                    Table(name, edited.fillna("").astype(str).values.tolist(), table.page, table.merges)
                )
    if reviewed:
        st.download_button(
            "Download Excel workbook",
            workbook(reviewed, preserve),
            "tables.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for i, table in enumerate(reviewed, 1):
                z.writestr(f"table-{i}.csv", csv_bytes(table))
        st.download_button(
            "Download CSV files (.zip)", archive.getvalue(), "tables-csv.zip", "application/zip"
        )
    if st.button("Clear results and corrections"):
        del st.session_state.tables
        st.rerun()
st.caption(
    "Best results: sharp, upright scans on a light background. Handwriting, nested tables, and complex layouts may require manual correction. Multi-frame TIFF: convert to PDF first."
)
