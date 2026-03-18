"""Node 1 — PDF Parser.

Extracts raw text and tables from the input PDF and stores them in the global
:class:`~src.graph.state.EarningsState`.
"""

from __future__ import annotations

import logging

from src.graph.state import EarningsState
from src.ingestion.pdf_parser import parse_pdf

logger = logging.getLogger(__name__)


def parser_node(state: EarningsState) -> EarningsState:
    """Extract text and tables from the PDF specified in the state.

    Reads ``state["pdf_path"]`` and populates ``state["raw_text"]`` and
    ``state["raw_tables"]``.  On failure the state is updated with an error
    entry in ``validation_errors`` and processing continues (graceful
    degradation).

    Parameters
    ----------
    state:
        Current pipeline state.

    Returns
    -------
    EarningsState
        Updated state with ``raw_text`` and ``raw_tables`` populated.
    """
    pdf_path = state["pdf_path"]
    logger.info("[parser] Starting PDF extraction: %s", pdf_path)

    try:
        raw_text, raw_tables = parse_pdf(pdf_path)
        logger.info(
            "[parser] Extracted %d chars and %d tables from %s",
            len(raw_text),
            len(raw_tables),
            pdf_path,
        )
        return {
            **state,
            "raw_text": raw_text,
            "raw_tables": raw_tables,
        }
    except Exception as exc:
        logger.error("[parser] Failed to parse PDF %s: %s", pdf_path, exc)
        errors = list(state.get("validation_errors", []))
        errors.append(f"PDF parsing failed: {exc}")
        return {
            **state,
            "raw_text": "",
            "raw_tables": [],
            "validation_errors": errors,
            "status": "failed",
        }
