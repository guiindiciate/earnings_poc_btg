"""Node 6 — Excel Writer.

Persists the completed state to the database and generates the Excel output
file.  This is the terminal node in the happy path and in the human-review
path.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config.settings import OUTPUT_PATH
from src.graph.state import EarningsState
from src.output.excel_exporter import export_to_excel
from src.storage.repository import upsert_earnings

logger = logging.getLogger(__name__)


def excel_writer_node(state: EarningsState) -> EarningsState:
    """Persist data to the database and generate the Excel output file.

    Steps performed:

    1. Upsert the :class:`~src.storage.models.EarningsRecord` (and related KPIs
       / log) via :func:`~src.storage.repository.upsert_earnings`.
    2. Call :func:`~src.output.excel_exporter.export_to_excel` to regenerate
       the full historical workbook for the ticker.

    Parameters
    ----------
    state:
        Current pipeline state.

    Returns
    -------
    EarningsState
        Updated state with ``excel_path`` populated.
    """
    ticker = state["ticker"]
    logger.info("[excel_writer] Persisting data for %s %s", ticker, state["periodo"])

    # ── Persist to DB ─────────────────────────────────────────────────────────
    try:
        upsert_earnings(state)
        logger.info("[excel_writer] Database upsert complete")
    except Exception as exc:
        logger.error("[excel_writer] Database upsert failed: %s", exc)

    # ── Generate Excel ─────────────────────────────────────────────────────────
    excel_path = ""
    try:
        out_dir = Path(OUTPUT_PATH)
        out_dir.mkdir(parents=True, exist_ok=True)
        excel_path = export_to_excel(ticker)
        logger.info("[excel_writer] Excel generated: %s", excel_path)
    except Exception as exc:
        logger.error("[excel_writer] Excel generation failed: %s", exc)

    return {**state, "excel_path": excel_path}
