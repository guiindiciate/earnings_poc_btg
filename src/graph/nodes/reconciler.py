"""
Nó 4 — Reconciler

Tenta corrigir automaticamente os erros apontados pelo validator.
Usa o mesmo LLM provider configurado (Bedrock por padrão).
Máximo de MAX_RETRIES tentativas antes de escalar para human_review.
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import MAX_RETRIES
from src.graph.state import EarningsState
from src.llm_client import get_llm
from src.schema.prompts import RECONCILER_PROMPT_V1

logger = logging.getLogger(__name__)


def reconciler_node(state: EarningsState) -> EarningsState:
    """
    Recebe o estado com erros de validação e tenta corrigir via LLM.
    Incrementa retry_count a cada chamada.
    """
    retry_count = state.get("retry_count", 0) + 1
    logger.info(
        f"[{state['ticker']}] Reconciler — tentativa {retry_count}/{MAX_RETRIES}. "
        f"Erros: {state['validation_errors']}"
    )

    llm = get_llm()

    # Extrai trecho relevante do documento para contexto
    trecho_relevante = _extract_relevant_excerpt(
        state.get("raw_text", ""),
        state["validation_errors"]
    )

    prompt = RECONCILER_PROMPT_V1.format(
        erros="\n".join(f"- {e}" for e in state["validation_errors"]),
        dados_anteriores=json.dumps(state.get("core_metrics", {}), ensure_ascii=False, indent=2),
        trecho_relevante=trecho_relevante[:3000],
    )

    response = llm.invoke([
        SystemMessage(
            content="Você é um analista financeiro realizando correção de dados "
                    "extraídos de earnings releases brasileiros."
        ),
        HumanMessage(content=prompt),
    ])

    # Extrai JSON corrigido da resposta
    corrected_metrics = _extract_corrected_json(response.content)

    if corrected_metrics:
        logger.info(f"[{state['ticker']}] Reconciler corrigiu {len(corrected_metrics)} campos.")
        # Merge das correções nos core_metrics existentes
        updated_metrics = {**state.get("core_metrics", {}), **corrected_metrics}
    else:
        logger.warning(f"[{state['ticker']}] Reconciler não produziu JSON válido.")
        updated_metrics = state.get("core_metrics", {})

    return {
        **state,
        "core_metrics": updated_metrics,
        "retry_count": retry_count,
        "validation_errors": [],  # reseta para o validator rodar novamente
    }


def _extract_relevant_excerpt(text: str, errors: list[str]) -> str:
    """
    Extrai trecho relevante do documento com base nas keywords dos erros.
    Retorna até 3000 chars do trecho mais relevante.
    """
    if not text or not errors:
        return text[:3000] if text else ""

    # Keywords dos erros para busca no documento
    keywords = []
    for error in errors:
        error_lower = error.lower()
        if "dívida" in error_lower or "divida" in error_lower:
            keywords.extend(["dívida", "endividamento", "debt"])
        if "ebitda" in error_lower:
            keywords.extend(["ebitda", "resultado"])
        if "margem" in error_lower:
            keywords.extend(["margem", "margin"])

    # Encontra parágrafo mais relevante
    paragraphs = text.split("\n\n")
    for paragraph in paragraphs:
        if any(kw.lower() in paragraph.lower() for kw in keywords):
            return paragraph[:3000]

    return text[:3000]


def _extract_corrected_json(response_text: str) -> dict:
    """Extrai o JSON corrigido da resposta do reconciler."""
    text = response_text.strip()

    # Remove markdown se presente
    if "```" in text:
        # Pega apenas a parte antes das explicações
        json_part = text.split("## Correções")[0]
        lines = json_part.split("\n")
        json_lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(json_lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Não foi possível extrair JSON da resposta do reconciler.")
        return {}
