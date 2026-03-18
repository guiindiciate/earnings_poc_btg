"""EarningsState TypedDict — global state shared across all LangGraph nodes."""

from __future__ import annotations

from typing import Any, TypedDict


class EarningsState(TypedDict):
    """Global state object propagated through every node of the LangGraph workflow.

    Input fields are set by the caller via :func:`initial_state`.
    Intermediate and output fields are populated progressively by each node.
    """

    # ── Input ──────────────────────────────────────────────────────────────────
    pdf_path: str
    """Absolute or relative path to the earnings release PDF."""

    ticker: str
    """Stock ticker symbol, e.g. ``"ITUB4"``."""

    periodo: str
    """Reporting period label, e.g. ``"4T25"``."""

    ano: int
    """Reporting year, e.g. ``2025``."""

    trimestre: int
    """Reporting quarter (1–4), e.g. ``4``."""

    # ── Intermediate processing ────────────────────────────────────────────────
    raw_text: str
    """Full extracted text from the PDF."""

    raw_tables: list[dict[str, Any]]
    """List of tables extracted from the PDF, each normalised to
    ``{"headers": [...], "rows": [[...], ...]}``.
    """

    # ── Extracted metrics ──────────────────────────────────────────────────────
    core_metrics: dict[str, Any]
    """Fixed-schema financial metrics (resultado, rentabilidade, balanco,
    fluxo_caixa, capital_giro).
    """

    kpis_operacionais: dict[str, Any]
    """Free-form operational KPIs extracted dynamically by the LLM."""

    # ── Quality control ────────────────────────────────────────────────────────
    validation_errors: list[str]
    """List of validation error messages produced by the validator node."""

    confidence_scores: dict[str, Any]
    """Per-metric or per-section confidence scores (0.0 – 1.0)."""

    retry_count: int
    """Number of reconciliation attempts so far (starts at 0, max = MAX_RETRIES)."""

    # ── Output ─────────────────────────────────────────────────────────────────
    status: str
    """Pipeline status: ``"processing"`` | ``"approved"`` | ``"review"`` |
    ``"failed"`` | ``"awaiting_human"``.
    """

    excel_path: str
    """Path to the generated Excel file (populated by the excel_writer node)."""


def _parse_periodo(periodo: str) -> tuple[int, int]:
    """Parse a period string like ``"4T25"`` into ``(trimestre, ano)``.

    Supports formats ``"<Q>T<YY>"`` and ``"<Q>T<YYYY>"``.

    Parameters
    ----------
    periodo:
        Period label, e.g. ``"4T25"`` or ``"1T2024"``.

    Returns
    -------
    tuple[int, int]
        ``(trimestre, ano)`` where *ano* is the full 4-digit year.
    """
    try:
        quarter_str, year_str = periodo.upper().split("T")
        trimestre = int(quarter_str)
        ano_raw = int(year_str)
        ano = ano_raw + 2000 if ano_raw < 100 else ano_raw
        return trimestre, ano
    except (ValueError, AttributeError):
        return 0, 0


def initial_state(pdf_path: str, ticker: str, periodo: str) -> EarningsState:
    """Build an :class:`EarningsState` with sensible defaults.

    Parameters
    ----------
    pdf_path:
        Path to the earnings release PDF.
    ticker:
        Stock ticker symbol.
    periodo:
        Reporting period label (e.g. ``"4T25"``).

    Returns
    -------
    EarningsState
        Fully initialised state ready to be passed to the workflow.
    """
    trimestre, ano = _parse_periodo(periodo)

    return EarningsState(
        pdf_path=pdf_path,
        ticker=ticker.upper(),
        periodo=periodo.upper(),
        ano=ano,
        trimestre=trimestre,
        raw_text="",
        raw_tables=[],
        core_metrics={},
        kpis_operacionais={},
        validation_errors=[],
        confidence_scores={},
        retry_count=0,
        status="processing",
        excel_path="",
    )
