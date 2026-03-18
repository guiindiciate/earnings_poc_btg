"""Conditional edges — routing logic for the LangGraph workflow.

The only branching point in the current pipeline is after the validator node,
which can direct flow to:

* ``"excel_writer"``  — if extraction was approved.
* ``"reconciler"``    — if errors exist and retry budget remains.
* ``"human_review"``  — if errors exist and retry budget is exhausted.
"""

from __future__ import annotations

from src.graph.state import EarningsState


def route_after_validation(state: EarningsState) -> str:
    """Determine the next node after the validator.

    Parameters
    ----------
    state:
        Current pipeline state containing the ``"status"`` field set by the
        validator node.

    Returns
    -------
    str
        One of ``"excel_writer"``, ``"reconciler"``, or ``"human_review"``.
    """
    status = state.get("status", "failed")

    if status == "approved":
        return "excel_writer"
    elif status == "review":
        return "reconciler"
    else:
        # "failed", "awaiting_human", or anything unexpected
        return "human_review"
