"""Node 3 — Validator.

Runs all accounting validation rules against ``core_metrics`` and decides the
pipeline routing based on the results.
"""

from __future__ import annotations

import logging

from config.settings import MAX_RETRIES, MIN_COMPLETUDE_CORE
from src.graph.state import EarningsState
from src.schema.validators import run_all_validations

logger = logging.getLogger(__name__)


def validator_node(state: EarningsState) -> EarningsState:
    """Validate extracted core metrics and set the pipeline status.

    Status assignment rules:

    * ``"approved"`` — no validation errors.
    * ``"review"``   — errors present AND ``retry_count < MAX_RETRIES``.
    * ``"failed"``   — errors present AND ``retry_count >= MAX_RETRIES``.

    Parameters
    ----------
    state:
        Current pipeline state (must contain ``core_metrics``).

    Returns
    -------
    EarningsState
        Updated state with ``validation_errors``, ``confidence_scores``,
        and ``status``.
    """
    core = state.get("core_metrics", {})
    retry_count = state.get("retry_count", 0)

    logger.info(
        "[validator] Running validations (retry_count=%d, max=%d)", retry_count, MAX_RETRIES
    )

    errors, confidence_scores = run_all_validations(core, min_completude=MIN_COMPLETUDE_CORE)

    # Merge with any pre-existing errors from earlier nodes (e.g. parser)
    existing_errors = list(state.get("validation_errors", []))
    all_errors = existing_errors + errors

    if not errors:
        status = "approved"
        logger.info("[validator] All validations passed — status=approved")
    elif retry_count < MAX_RETRIES:
        status = "review"
        logger.warning(
            "[validator] %d validation error(s) — status=review (will retry)", len(errors)
        )
    else:
        status = "failed"
        logger.error(
            "[validator] %d validation error(s) — status=failed (max retries reached)", len(errors)
        )

    return {
        **state,
        "validation_errors": all_errors,
        "confidence_scores": confidence_scores,
        "status": status,
    }
