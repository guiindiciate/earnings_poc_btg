"""File handler — registration, validation and deduplication of PDF uploads."""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_VALID_MIME_MAGIC = b"%PDF"


def validate_file(pdf_path: str) -> bool:
    """Check that the file exists, is non-empty, and starts with a PDF magic header.

    Parameters
    ----------
    pdf_path:
        Path to the file to validate.

    Returns
    -------
    bool
        ``True`` if the file is a valid, non-empty PDF; ``False`` otherwise.
    """
    path = Path(pdf_path)
    if not path.exists():
        logger.warning("File does not exist: %s", pdf_path)
        return False
    if path.stat().st_size == 0:
        logger.warning("File is empty: %s", pdf_path)
        return False
    with path.open("rb") as fh:
        magic = fh.read(4)
    if magic != _VALID_MIME_MAGIC:
        logger.warning("File does not appear to be a PDF (magic=%r): %s", magic, pdf_path)
        return False
    return True


def get_file_hash(pdf_path: str) -> str:
    """Compute the SHA-256 hash of the file for deduplication.

    Parameters
    ----------
    pdf_path:
        Path to the file.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {pdf_path}")

    sha256 = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def register_file(pdf_path: str, ticker: str, periodo: str) -> dict:
    """Collect metadata about the uploaded earnings release PDF.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.
    ticker:
        Stock ticker symbol.
    periodo:
        Reporting period label (e.g. ``"4T25"``).

    Returns
    -------
    dict
        Metadata dictionary with keys: ``ticker``, ``periodo``,
        ``arquivo_origem``, ``arquivo_path``, ``tamanho_bytes``,
        ``hash_sha256``, ``data_registro``, ``valido``.
    """
    path = Path(pdf_path)
    valido = validate_file(pdf_path)

    metadata: dict = {
        "ticker": ticker.upper(),
        "periodo": periodo.upper(),
        "arquivo_origem": path.name,
        "arquivo_path": str(path.resolve()),
        "tamanho_bytes": path.stat().st_size if path.exists() else 0,
        "hash_sha256": get_file_hash(pdf_path) if valido else None,
        "data_registro": datetime.now(tz=timezone.utc).isoformat(),
        "valido": valido,
    }
    logger.info(
        "File registered: %s (ticker=%s, periodo=%s, valid=%s)",
        path.name,
        ticker,
        periodo,
        valido,
    )
    return metadata
