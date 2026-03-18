"""PDF parsing module — extracts text and tables from earnings release PDFs.

Three strategies are tried in cascade:

1. **pdfplumber** — best for structured tables.
2. **PyMuPDF (fitz)** — best for continuous text.
3. **unstructured** (optional) — fallback for scanned / image-heavy PDFs.
   Imported with ``try/except`` so the pipeline works without it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Optional unstructured import ──────────────────────────────────────────────

try:
    from unstructured.partition.pdf import partition_pdf as _unstructured_partition  # type: ignore[import-untyped]

    _UNSTRUCTURED_AVAILABLE = True
except ImportError:
    _UNSTRUCTURED_AVAILABLE = False
    logger.debug("unstructured not installed — OCR fallback disabled")


# ── Table normalisation helper ─────────────────────────────────────────────────


def _normalise_table(raw_table: list[list[Any]]) -> dict[str, Any] | None:
    """Convert a raw pdfplumber table (list of lists) to a normalised dict.

    Parameters
    ----------
    raw_table:
        Rows as returned by ``pdfplumber``, where the first non-empty row is
        treated as headers.

    Returns
    -------
    dict | None
        ``{"headers": [...], "rows": [[...], ...]}`` or ``None`` if the table
        is empty / has no content.
    """
    if not raw_table:
        return None

    # Filter completely-None rows
    cleaned = [
        [cell if cell is not None else "" for cell in row]
        for row in raw_table
        if any(cell is not None and str(cell).strip() for cell in row)
    ]
    if not cleaned:
        return None

    headers = [str(h).strip() for h in cleaned[0]]
    rows = [[str(cell).strip() for cell in row] for row in cleaned[1:]]
    return {"headers": headers, "rows": rows}


# ── Strategy 1: pdfplumber ─────────────────────────────────────────────────────


def _extract_with_pdfplumber(pdf_path: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract text and tables using pdfplumber.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.

    Returns
    -------
    tuple[str, list[dict]]
        ``(full_text, tables)``
    """
    import pdfplumber  # type: ignore[import-untyped]

    text_parts: list[str] = []
    tables: list[dict[str, Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

            for raw_table in page.extract_tables() or []:
                normalised = _normalise_table(raw_table)
                if normalised:
                    normalised["page"] = page_num
                    tables.append(normalised)

    return "\n\n".join(text_parts), tables


# ── Strategy 2: PyMuPDF ────────────────────────────────────────────────────────


def _extract_with_pymupdf(pdf_path: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract continuous text using PyMuPDF (fitz).

    Tables are not extracted here — this strategy is used mainly to get
    richer continuous text that pdfplumber may truncate.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.

    Returns
    -------
    tuple[str, list[dict]]
        ``(full_text, [])``
    """
    import fitz  # type: ignore[import-untyped]  # PyMuPDF

    text_parts: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        for page in doc:
            text_parts.append(page.get_text())
    finally:
        doc.close()

    return "\n\n".join(text_parts), []


# ── Strategy 3: unstructured (optional OCR fallback) ──────────────────────────


def _extract_with_unstructured(pdf_path: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract text using *unstructured* (requires optional OCR dependencies).

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.

    Returns
    -------
    tuple[str, list[dict]]
        ``(full_text, [])``
    """
    if not _UNSTRUCTURED_AVAILABLE:
        raise RuntimeError("unstructured is not installed")

    elements = _unstructured_partition(filename=pdf_path)
    text = "\n\n".join(str(el) for el in elements)
    return text, []


# ── Public API ─────────────────────────────────────────────────────────────────


def parse_pdf(pdf_path: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract full text and structured tables from a PDF file.

    Tries three strategies in order of preference:

    1. pdfplumber (tables + text)
    2. PyMuPDF (text — merged with pdfplumber tables)
    3. unstructured (OCR fallback — only if previous strategies yield no text)

    Parameters
    ----------
    pdf_path:
        Absolute or relative path to the PDF file.

    Returns
    -------
    tuple[str, list[dict]]
        ``(full_text, tables)`` where *tables* is a list of dicts with keys
        ``"headers"``, ``"rows"``, and ``"page"``.

    Raises
    ------
    FileNotFoundError
        If *pdf_path* does not exist.
    ValueError
        If the file cannot be parsed by any available strategy.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info("Parsing PDF: %s", pdf_path)

    text = ""
    tables: list[dict[str, Any]] = []

    # Strategy 1 — pdfplumber (primary: tables + text)
    try:
        text, tables = _extract_with_pdfplumber(pdf_path)
        logger.debug("pdfplumber extracted %d chars, %d tables", len(text), len(tables))
    except Exception as exc:
        logger.warning("pdfplumber failed: %s", exc)

    # Strategy 2 — PyMuPDF (augments text quality when pdfplumber text is sparse)
    if len(text.strip()) < 500:
        try:
            pymupdf_text, _ = _extract_with_pymupdf(pdf_path)
            logger.debug("PyMuPDF extracted %d chars", len(pymupdf_text))
            if len(pymupdf_text) > len(text):
                text = pymupdf_text
        except Exception as exc:
            logger.warning("PyMuPDF failed: %s", exc)

    # Strategy 3 — unstructured OCR fallback
    if len(text.strip()) < 100 and _UNSTRUCTURED_AVAILABLE:
        try:
            unstructured_text, _ = _extract_with_unstructured(pdf_path)
            logger.info("unstructured OCR extracted %d chars", len(unstructured_text))
            if len(unstructured_text) > len(text):
                text = unstructured_text
        except Exception as exc:
            logger.warning("unstructured failed: %s", exc)

    if not text.strip() and not tables:
        raise ValueError(f"Could not extract any content from PDF: {pdf_path}")

    logger.info(
        "PDF parsing complete — %d chars, %d tables extracted from %s",
        len(text),
        len(tables),
        pdf_path,
    )
    return text, tables
