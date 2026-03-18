"""
Nó 2 — Core Extractor

Chama o LLM configurado (Bedrock por padrão, OpenAI como fallback) para extrair:
  1. core_metrics      → schema fixo (resultado, rentabilidade, balanço, FCL, capital de giro)
  2. kpis_operacionais → schema livre (qualquer KPI operacional presente no PDF)

O nó é agnóstico de setor — funciona para bancos, educação, varejo, etc.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.state import EarningsState
from src.llm_client import get_llm
from src.schema.prompts import (
    CORE_EXTRACTION_PROMPT_V1,
    OPERATIONAL_KPI_PROMPT_V1,
)

logger = logging.getLogger(__name__)

# Limite de caracteres para o contexto do LLM (evita exceder context window)
MAX_DOCUMENT_CHARS = 80_000


def extractor_node(state: EarningsState) -> EarningsState:
    """
    Extrai métricas financeiras e KPIs operacionais do texto do PDF.

    Realiza duas chamadas LLM separadas:
    1. Core metrics (schema fixo, validado por Pydantic)
    2. KPIs operacionais (schema livre, dinâmico por setor)
    """
    llm = get_llm()
    documento = _truncate_document(state["raw_text"], max_chars=MAX_DOCUMENT_CHARS)

    # 1. Extração das core metrics
    logger.info(f"[{state['ticker']}] Extraindo core metrics via LLM ({type(llm).__name__})...")
    core_metrics = _extract_core_metrics(llm, documento, state)

    # 2. Extração dos KPIs operacionais (campo livre)
    logger.info(f"[{state['ticker']}] Extraindo KPIs operacionais via LLM...")
    try:
        kpis_operacionais = _extract_operational_kpis(llm, documento, state)
    except Exception as exc:
        logger.warning(f"[{state['ticker']}] KPI extraction failed (non-fatal): {exc}")
        kpis_operacionais = {}

    return {
        **state,
        "core_metrics": core_metrics,
        "kpis_operacionais": kpis_operacionais,
    }


def _extract_core_metrics(llm, documento: str, state: EarningsState) -> dict:
    """Chama LLM com prompt estruturado e valida resultado com Pydantic."""
    # Import inline para evitar circular imports
    try:
        from src.schema.core_schema import CORE_SCHEMA_JSON
        schema_json = CORE_SCHEMA_JSON
    except (ImportError, AttributeError):
        schema_json = "{}"

    prompt = CORE_EXTRACTION_PROMPT_V1.format(
        periodo=state["periodo"],
        ticker=state["ticker"],
        schema_json=schema_json,
        documento=documento,
    )

    response = llm.invoke([
        SystemMessage(
            content="Você é um analista financeiro sênior especializado em "
                    "earnings releases de empresas brasileiras de capital aberto."
        ),
        HumanMessage(content=prompt),
    ])

    raw_json = _extract_json(response.content)

    # Validação Pydantic — garante tipos e estrutura correta
    try:
        from src.schema.core_schema import EarningsData
        validated = EarningsData.model_validate(raw_json)
        return validated.model_dump()
    except Exception as e:
        logger.warning(
            f"[{state['ticker']}] Validação Pydantic falhou: {e}. "
            "Usando JSON bruto do LLM."
        )
        return raw_json


def _extract_operational_kpis(llm, documento: str, state: EarningsState) -> dict:
    """
    Extrai KPIs operacionais em formato livre.
    O LLM decide quais KPIs são relevantes com base no conteúdo do PDF.
    Exemplos: base_alunos (educação), nii (bancos), sssg (varejo), arpu (telecom).
    """
    prompt = OPERATIONAL_KPI_PROMPT_V1.format(
        periodo=state["periodo"],
        ticker=state["ticker"],
        documento=documento,
    )

    response = llm.invoke([
        SystemMessage(
            content="Você é um analista financeiro especializado em "
                    "KPIs operacionais de empresas de capital aberto."
        ),
        HumanMessage(content=prompt),
    ])

    return _extract_json(response.content)


def _extract_json(text: str) -> dict[str, Any]:
    """
    Extrai JSON válido da resposta do LLM.
    Remove blocos markdown (```json ... ```) se presentes.
    """
    text = text.strip()

    # Remove blocos de código markdown
    if "```" in text:
        lines = text.split("\n")
        json_lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(json_lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(
            f"Falha ao parsear JSON do LLM: {e}\n"
            f"Primeiros 500 chars: {text[:500]}"
        )
        return {}


def _truncate_document(text: str, max_chars: int = MAX_DOCUMENT_CHARS) -> str:
    """
    Trunca o documento para não exceder a context window do LLM.
    Claude 3 Sonnet suporta ~200k tokens, mas limitamos para controle de custo.
    """
    if len(text) > max_chars:
        logger.warning(
            f"Documento truncado: {len(text)} → {max_chars} caracteres."
        )
        return text[:max_chars] + "\n\n[DOCUMENTO TRUNCADO — CONTEÚDO RESTANTE OMITIDO]"
    return text
