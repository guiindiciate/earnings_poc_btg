"""Node 4 — Reconciler (auto-correction via LLM).

When the validator detects errors and the retry budget has not been exhausted,
this node asks the LLM to correct only the problematic fields, then increments
``retry_count`` so the validator can re-evaluate.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.graph.nodes.extractor import _call_llm, _extract_json, _validate_core_with_pydantic
from src.graph.state import EarningsState
from src.schema.prompts import RECONCILER_PROMPT

logger = logging.getLogger(__name__)

# Max chars from raw_text to include as reference context
_CONTEXT_WINDOW = 8_000


def reconciler_node(state: EarningsState) -> EarningsState:
    """Attempt to auto-correct extraction errors using the LLM.

    Uses :data:`~src.schema.prompts.RECONCILER_PROMPT` to provide the model
    with the list of errors and the previously extracted data, then parses and
    re-validates the corrected JSON.

    Increments ``retry_count`` regardless of success so the validator loop
    terminates after ``MAX_RETRIES`` attempts.

    Parameters
    ----------
    state:
        Current pipeline state.

    Returns
    -------
    EarningsState
        Updated state with potentially corrected ``core_metrics`` and
        incremented ``retry_count``.
    """
    errors = state.get("validation_errors", [])
    core_metrics = state.get("core_metrics", {})
    raw_text = state.get("raw_text", "")
    retry_count = state.get("retry_count", 0)

    logger.info("[reconciler] Attempting correction (retry %d)", retry_count + 1)

    # Build a short relevant excerpt (first _CONTEXT_WINDOW chars of raw text)
    trecho_relevante = raw_text[:_CONTEXT_WINDOW]

    updated_core: dict[str, Any] = core_metrics

    try:
        prompt = RECONCILER_PROMPT.format(
            erros="\n".join(f"- {e}" for e in errors),
            dados_anteriores=json.dumps(core_metrics, ensure_ascii=False, indent=2),
            trecho_relevante=trecho_relevante,
        )
        logger.info("[reconciler] Calling LLM for correction")
        response = _call_llm(prompt)

        # The reconciler prompt returns JSON first, then explanations after "##"
        # We only care about the JSON part (everything before the first "##")
        json_part = response.split("##")[0].strip()
        raw_corrected = _extract_json(json_part)
        updated_core = _validate_core_with_pydantic(raw_corrected)
        logger.info("[reconciler] Correction successful")

    except Exception as exc:
        logger.error("[reconciler] Correction failed: %s", exc)
        # Keep original core_metrics; let the validator decide what to do next

    return {
        **state,
        "core_metrics": updated_core,
        "retry_count": retry_count + 1,
        # Reset validation_errors so the validator runs fresh
        "validation_errors": [],
    }
