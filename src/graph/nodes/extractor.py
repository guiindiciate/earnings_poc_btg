"""Node 2 — Core + KPIs Extractor (LLM).

Makes two separate LLM calls:

1. Core financial metrics — using :data:`~src.schema.prompts.CORE_EXTRACTION_PROMPT`.
2. Operational KPIs — using :data:`~src.schema.prompts.OPERATIONAL_KPI_PROMPT`.

Both results are validated with Pydantic before being stored in the state.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.graph.state import EarningsState
from src.schema.core_schema import (
    Balanco,
    CapitalGiro,
    FluxoCaixa,
    Rentabilidade,
    Resultado,
)
from src.schema.prompts import CORE_EXTRACTION_PROMPT, OPERATIONAL_KPI_PROMPT

logger = logging.getLogger(__name__)

# ── Core schema template sent to the LLM ──────────────────────────────────────

_CORE_SCHEMA_JSON = json.dumps(
    {
        "resultado": {
            "receita_liquida": {"valor": None, "var_aa": None, "var_qa": None},
            "lucro_bruto": {"valor": None, "margem": None, "var_aa": None},
            "ebitda": {"valor": None, "margem": None, "var_aa": None},
            "ebit": {"valor": None, "margem": None, "var_aa": None},
            "lucro_liquido": {"valor": None, "margem": None, "var_aa": None},
            "lucro_liquido_controlador": {"valor": None, "margem": None, "var_aa": None},
        },
        "rentabilidade": {
            "roe": {"valor": None, "var_aa": None},
            "roic": {"valor": None, "var_aa": None},
            "roa": {"valor": None, "var_aa": None},
            "margem_bruta": {"valor": None, "var_aa": None},
            "margem_ebitda": {"valor": None, "var_aa": None},
            "margem_liquida": {"valor": None, "var_aa": None},
        },
        "balanco": {
            "ativo_total": {"valor": None},
            "patrimonio_liquido": {"valor": None},
            "divida_bruta": {"valor": None},
            "caixa_equivalentes": {"valor": None},
            "divida_liquida": {"valor": None},
            "alavancagem_dl_ebitda": {"valor": None},
            "alavancagem_dl_pl": {"valor": None},
        },
        "fluxo_caixa": {
            "cfo": {"valor": None},
            "capex": {"valor": None, "pct_receita": None},
            "fcl": {"valor": None},
            "conversao_caixa": {"valor": None},
        },
        "capital_giro": {
            "capital_de_giro": {"valor": None},
            "pmr": {"valor": None},
            "pmp": {"valor": None},
            "pmie": {"valor": None},
        },
    },
    ensure_ascii=False,
    indent=2,
)


# ── JSON extraction helper ─────────────────────────────────────────────────────


def _extract_json(text: str) -> dict[str, Any]:
    """Parse JSON from an LLM response, stripping any markdown code fences.

    Parameters
    ----------
    text:
        Raw LLM response string.

    Returns
    -------
    dict
        Parsed JSON object.

    Raises
    ------
    ValueError
        If no valid JSON object can be found in *text*.
    """
    # Try direct parse first
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Extract first {...} block
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {stripped[:200]!r}")


# ── LLM call helpers ───────────────────────────────────────────────────────────


def _call_llm(prompt: str) -> str:
    """Invoke the configured LLM and return the response content.

    Parameters
    ----------
    prompt:
        Fully rendered prompt string.

    Returns
    -------
    str
        Raw text response from the model.
    """
    from langchain_openai import ChatOpenAI

    from config.settings import LLM_MODEL, LLM_TEMPERATURE

    llm = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    response = llm.invoke(prompt)
    return response.content  # type: ignore[return-value]


def _validate_core_with_pydantic(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and coerce *raw* core metrics through Pydantic models.

    Only the known top-level sections are validated; unknown keys are passed
    through unchanged.

    Parameters
    ----------
    raw:
        Raw dict from LLM JSON parsing.

    Returns
    -------
    dict
        Validated (and coerced) core metrics dict.
    """
    section_models = {
        "resultado": Resultado,
        "rentabilidade": Rentabilidade,
        "balanco": Balanco,
        "fluxo_caixa": FluxoCaixa,
        "capital_giro": CapitalGiro,
    }
    validated: dict[str, Any] = {}
    for section, model_cls in section_models.items():
        section_data = raw.get(section, {})
        validated[section] = model_cls(**section_data).model_dump()
    return validated


# ── Node ──────────────────────────────────────────────────────────────────────


def extractor_node(state: EarningsState) -> EarningsState:
    """Call the LLM to extract core metrics and operational KPIs.

    Makes two separate LLM requests:

    1. Core metrics (fixed schema).
    2. Operational KPIs (free-form).

    Both responses are JSON-parsed and Pydantic-validated before being stored.

    Parameters
    ----------
    state:
        Current pipeline state (must contain ``raw_text``).

    Returns
    -------
    EarningsState
        Updated state with ``core_metrics`` and ``kpis_operacionais`` populated.
    """
    ticker = state["ticker"]
    periodo = state["periodo"]
    documento = state.get("raw_text", "")

    # Truncate document to avoid token limits (~64k chars ≈ ~16k tokens)
    doc_truncated = documento[:64_000]

    errors = list(state.get("validation_errors", []))
    core_metrics: dict[str, Any] = {}
    kpis_operacionais: dict[str, Any] = {}

    # ── 1. Core extraction ────────────────────────────────────────────────────
    try:
        core_prompt = CORE_EXTRACTION_PROMPT.format(
            ticker=ticker,
            periodo=periodo,
            schema_json=_CORE_SCHEMA_JSON,
            documento=doc_truncated,
        )
        logger.info("[extractor] Calling LLM for core metrics (ticker=%s, periodo=%s)", ticker, periodo)
        core_response = _call_llm(core_prompt)
        raw_core = _extract_json(core_response)
        core_metrics = _validate_core_with_pydantic(raw_core)
        logger.info("[extractor] Core metrics extracted and validated")
    except Exception as exc:
        logger.error("[extractor] Core extraction failed: %s", exc)
        errors.append(f"Core extraction failed: {exc}")

    # ── 2. Operational KPI extraction ─────────────────────────────────────────
    try:
        kpi_prompt = OPERATIONAL_KPI_PROMPT.format(
            ticker=ticker,
            periodo=periodo,
            documento=doc_truncated,
        )
        logger.info("[extractor] Calling LLM for operational KPIs")
        kpi_response = _call_llm(kpi_prompt)
        kpis_operacionais = _extract_json(kpi_response)
        logger.info("[extractor] Operational KPIs extracted: %d items", len(kpis_operacionais))
    except Exception as exc:
        logger.warning("[extractor] Operational KPI extraction failed: %s", exc)
        # Non-fatal — operational KPIs are optional
        errors.append(f"KPI extraction failed (non-fatal): {exc}")

    return {
        **state,
        "core_metrics": core_metrics,
        "kpis_operacionais": kpis_operacionais,
        "validation_errors": errors,
    }
