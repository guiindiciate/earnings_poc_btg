"""Node 5 — Human Review escalation.

When automatic reconciliation is exhausted this node saves the full pipeline
state as a JSON file in the ``review_queue/`` directory so a human analyst can
inspect and correct the extraction manually.

In the POC context the node does **not** block the pipeline — it marks the
status as ``"awaiting_human"`` and lets the workflow continue to the Excel
writer with whatever data is available.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from config.settings import REVIEW_QUEUE_PATH
from src.graph.state import EarningsState

logger = logging.getLogger(__name__)


def human_review_node(state: EarningsState) -> EarningsState:
    """Persist the pipeline state for manual review and mark it as awaiting.

    Saves a timestamped JSON file to ``review_queue/`` containing the full
    state snapshot (including validation errors, core metrics, and raw text
    excerpt) for a human analyst to inspect.

    Parameters
    ----------
    state:
        Current pipeline state (usually arriving from the validator with
        ``status="failed"``).

    Returns
    -------
    EarningsState
        Updated state with ``status="awaiting_human"``.
    """
    ticker = state.get("ticker", "UNKNOWN")
    periodo = state.get("periodo", "UNKNOWN")
    errors = state.get("validation_errors", [])

    logger.warning(
        "[human_review] Escalating %s %s to human review — %d error(s)",
        ticker,
        periodo,
        len(errors),
    )
    for err in errors:
        logger.warning("[human_review]   • %s", err)

    # ── Persist review artefact ────────────────────────────────────────────────
    queue_path = Path(REVIEW_QUEUE_PATH)
    queue_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{ticker}_{periodo}_{timestamp}.json"
    filepath = queue_path / filename

    # Build a serialisable snapshot (omit raw_text to keep file size manageable)
    snapshot = {
        "ticker": ticker,
        "periodo": periodo,
        "pdf_path": state.get("pdf_path"),
        "core_metrics": state.get("core_metrics", {}),
        "kpis_operacionais": state.get("kpis_operacionais", {}),
        "validation_errors": errors,
        "confidence_scores": state.get("confidence_scores", {}),
        "retry_count": state.get("retry_count", 0),
        "raw_text_excerpt": (state.get("raw_text") or "")[:2_000],
        "timestamp": timestamp,
    }

    try:
        with filepath.open("w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, ensure_ascii=False, indent=2)
        logger.info("[human_review] Review artefact saved: %s", filepath)
    except OSError as exc:
        logger.error("[human_review] Failed to write review artefact: %s", exc)

    return {**state, "status": "awaiting_human"}
