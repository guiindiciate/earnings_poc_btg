"""LangGraph workflow — composes and compiles the earnings extraction pipeline.

Graph topology
--------------

::

    [parser] → [extractor] → [validator] ──(approved)──→ [excel_writer] → END
                                    │
                       ┌────────────┼────────────┐
                  (review)      (failed)   (awaiting_human)
                       │              │
                 [reconciler]  [human_review]
                       │              │
                  [validator]   [excel_writer]
                  (loop ≤ 2)

Usage
-----

::

    from src.graph.workflow import app
    from src.graph.state import initial_state

    result = app.invoke(initial_state(
        pdf_path="tests/fixtures/example.pdf",
        ticker="VTRU3",
        periodo="4T25",
    ))
    print(result["status"])   # "approved" | "awaiting_human" | "failed"
    print(result["excel_path"])
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.graph.edges import route_after_validation
from src.graph.nodes.excel_writer import excel_writer_node
from src.graph.nodes.extractor import extractor_node
from src.graph.nodes.human_review import human_review_node
from src.graph.nodes.parser import parser_node
from src.graph.nodes.reconciler import reconciler_node
from src.graph.nodes.validator import validator_node
from src.graph.state import EarningsState


def create_workflow() -> StateGraph:
    """Build and compile the earnings extraction LangGraph.

    Returns
    -------
    CompiledGraph
        A compiled LangGraph application ready to be invoked.
    """
    workflow = StateGraph(EarningsState)

    # ── Register nodes ────────────────────────────────────────────────────────
    workflow.add_node("parser", parser_node)
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("reconciler", reconciler_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("excel_writer", excel_writer_node)

    # ── Entry point ────────────────────────────────────────────────────────────
    workflow.set_entry_point("parser")

    # ── Sequential edges ──────────────────────────────────────────────────────
    workflow.add_edge("parser", "extractor")
    workflow.add_edge("extractor", "validator")

    # ── Conditional routing after validation ──────────────────────────────────
    workflow.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "excel_writer": "excel_writer",
            "reconciler": "reconciler",
            "human_review": "human_review",
        },
    )

    # ── Reconciler loops back to validator ────────────────────────────────────
    workflow.add_edge("reconciler", "validator")

    # ── Human review feeds into excel_writer (non-blocking in POC) ───────────
    workflow.add_edge("human_review", "excel_writer")

    # ── Terminal edge ─────────────────────────────────────────────────────────
    workflow.add_edge("excel_writer", END)

    return workflow.compile()


# Module-level compiled application — import directly for quick use.
app = create_workflow()
