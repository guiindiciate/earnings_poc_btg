"""Repository layer — CRUD operations for earnings data.

All functions accept / return plain Python dicts or ORM model instances and
handle database session lifecycle internally via :func:`~src.storage.database.session_scope`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from src.graph.state import EarningsState
from src.storage.database import init_db, session_scope
from src.storage.models import EarningsRecord, ExtractionLog, OperationalKPI

logger = logging.getLogger(__name__)


def _state_to_record_kwargs(state: EarningsState) -> dict[str, Any]:
    """Flatten the pipeline state into column kwargs for :class:`EarningsRecord`."""
    core = state.get("core_metrics", {})
    resultado = core.get("resultado", {})
    rentabilidade = core.get("rentabilidade", {})
    balanco = core.get("balanco", {})
    fluxo = core.get("fluxo_caixa", {})
    giro = core.get("capital_giro", {})

    def v(section: dict, metric: str, field: str = "valor") -> Any:
        """Safely retrieve a nested metric value."""
        return (section.get(metric) or {}).get(field)

    conf_scores = state.get("confidence_scores", {})
    overall_conf = conf_scores.get("overall")

    return {
        "ticker": state["ticker"],
        "periodo": state["periodo"],
        "ano": state.get("ano"),
        "trimestre": state.get("trimestre"),
        "arquivo_origem": Path(state.get("pdf_path", "")).name or None,
        "confianca_score": overall_conf,
        "status": state.get("status"),
        # resultado
        "receita_liquida": v(resultado, "receita_liquida"),
        "receita_liquida_var_aa": v(resultado, "receita_liquida", "var_aa"),
        "receita_liquida_var_qa": v(resultado, "receita_liquida", "var_qa"),
        "lucro_bruto": v(resultado, "lucro_bruto"),
        "lucro_bruto_margem": v(resultado, "lucro_bruto", "margem"),
        "lucro_bruto_var_aa": v(resultado, "lucro_bruto", "var_aa"),
        "ebitda": v(resultado, "ebitda"),
        "ebitda_margem": v(resultado, "ebitda", "margem"),
        "ebitda_var_aa": v(resultado, "ebitda", "var_aa"),
        "ebit": v(resultado, "ebit"),
        "ebit_margem": v(resultado, "ebit", "margem"),
        "ebit_var_aa": v(resultado, "ebit", "var_aa"),
        "lucro_liquido": v(resultado, "lucro_liquido"),
        "lucro_liquido_margem": v(resultado, "lucro_liquido", "margem"),
        "lucro_liquido_var_aa": v(resultado, "lucro_liquido", "var_aa"),
        "lucro_liquido_controlador": v(resultado, "lucro_liquido_controlador"),
        "lucro_liquido_controlador_margem": v(resultado, "lucro_liquido_controlador", "margem"),
        "lucro_liquido_controlador_var_aa": v(resultado, "lucro_liquido_controlador", "var_aa"),
        # rentabilidade
        "roe": v(rentabilidade, "roe"),
        "roe_var_aa": v(rentabilidade, "roe", "var_aa"),
        "roic": v(rentabilidade, "roic"),
        "roic_var_aa": v(rentabilidade, "roic", "var_aa"),
        "roa": v(rentabilidade, "roa"),
        "roa_var_aa": v(rentabilidade, "roa", "var_aa"),
        "margem_bruta": v(rentabilidade, "margem_bruta"),
        "margem_bruta_var_aa": v(rentabilidade, "margem_bruta", "var_aa"),
        "margem_ebitda": v(rentabilidade, "margem_ebitda"),
        "margem_ebitda_var_aa": v(rentabilidade, "margem_ebitda", "var_aa"),
        "margem_liquida": v(rentabilidade, "margem_liquida"),
        "margem_liquida_var_aa": v(rentabilidade, "margem_liquida", "var_aa"),
        # balanco
        "ativo_total": v(balanco, "ativo_total"),
        "patrimonio_liquido": v(balanco, "patrimonio_liquido"),
        "divida_bruta": v(balanco, "divida_bruta"),
        "caixa_equivalentes": v(balanco, "caixa_equivalentes"),
        "divida_liquida": v(balanco, "divida_liquida"),
        "alavancagem_dl_ebitda": v(balanco, "alavancagem_dl_ebitda"),
        "alavancagem_dl_pl": v(balanco, "alavancagem_dl_pl"),
        # fluxo_caixa
        "cfo": v(fluxo, "cfo"),
        "capex": v(fluxo, "capex"),
        "capex_pct_receita": v(fluxo, "capex", "pct_receita"),
        "fcl": v(fluxo, "fcl"),
        "conversao_caixa": v(fluxo, "conversao_caixa"),
        # capital_giro
        "capital_de_giro": v(giro, "capital_de_giro"),
        "pmr": v(giro, "pmr"),
        "pmp": v(giro, "pmp"),
        "pmie": v(giro, "pmie"),
    }


# ── Public repository functions ────────────────────────────────────────────────


def save_earnings(state: EarningsState) -> EarningsRecord:
    """Persist a new :class:`EarningsRecord`, its operational KPIs, and an
    :class:`ExtractionLog` entry.

    Parameters
    ----------
    state:
        Completed pipeline state.

    Returns
    -------
    EarningsRecord
        The newly created ORM record.
    """
    init_db()
    kwargs = _state_to_record_kwargs(state)

    with session_scope() as session:
        record = EarningsRecord(**kwargs)
        session.add(record)
        session.flush()  # assign PK

        # Operational KPIs
        for kpi_name, kpi_data in (state.get("kpis_operacionais") or {}).items():
            if not isinstance(kpi_data, dict):
                continue
            kpi = OperationalKPI(
                ticker=state["ticker"],
                periodo=state["periodo"],
                nome_kpi=kpi_name,
                valor=kpi_data.get("valor"),
                unidade=kpi_data.get("unidade"),
                var_aa=kpi_data.get("var_aa"),
            )
            session.add(kpi)

        # Extraction log
        errors = state.get("validation_errors", [])
        conf = (state.get("confidence_scores") or {}).get("overall")
        log = ExtractionLog(
            ticker=state["ticker"],
            periodo=state["periodo"],
            status=state.get("status"),
            erros_json=json.dumps(errors, ensure_ascii=False) if errors else None,
            confianca_score=conf,
            arquivo_origem=Path(state.get("pdf_path", "")).name or None,
        )
        session.add(log)
        session.flush()

        logger.info(
            "Saved earnings record for %s %s (id=%d)", state["ticker"], state["periodo"], record.id
        )
        return record


def get_earnings(ticker: str, periodo: str) -> Optional[EarningsRecord]:
    """Retrieve the most recent :class:`EarningsRecord` for a ticker + period.

    Parameters
    ----------
    ticker:
        Stock ticker symbol.
    periodo:
        Reporting period label.

    Returns
    -------
    EarningsRecord | None
        The matching record or ``None`` if not found.
    """
    init_db()
    with session_scope() as session:
        stmt = (
            select(EarningsRecord)
            .where(
                EarningsRecord.ticker == ticker.upper(),
                EarningsRecord.periodo == periodo.upper(),
            )
            .order_by(EarningsRecord.created_at.desc())
            .limit(1)
        )
        return session.scalar(stmt)


def get_history(ticker: str) -> list[EarningsRecord]:
    """Return all periods for a ticker in chronological order.

    Parameters
    ----------
    ticker:
        Stock ticker symbol.

    Returns
    -------
    list[EarningsRecord]
        Records sorted by (ano, trimestre) ascending.
    """
    init_db()
    with session_scope() as session:
        stmt = (
            select(EarningsRecord)
            .where(EarningsRecord.ticker == ticker.upper())
            .order_by(EarningsRecord.ano, EarningsRecord.trimestre)
        )
        return list(session.scalars(stmt).all())


def get_all_tickers() -> list[str]:
    """List all distinct tickers stored in the database.

    Returns
    -------
    list[str]
        Sorted list of ticker symbols.
    """
    init_db()
    from sqlalchemy import distinct

    with session_scope() as session:
        stmt = select(distinct(EarningsRecord.ticker)).order_by(EarningsRecord.ticker)
        return list(session.scalars(stmt).all())


def upsert_earnings(state: EarningsState) -> EarningsRecord:
    """Insert a new record or update an existing one for the same (ticker, periodo).

    Used when reprocessing a previously ingested period.

    Parameters
    ----------
    state:
        Completed pipeline state.

    Returns
    -------
    EarningsRecord
        The inserted or updated ORM record.
    """
    init_db()
    kwargs = _state_to_record_kwargs(state)
    ticker = state["ticker"]
    periodo = state["periodo"]

    with session_scope() as session:
        stmt = (
            select(EarningsRecord)
            .where(
                EarningsRecord.ticker == ticker,
                EarningsRecord.periodo == periodo,
            )
            .limit(1)
        )
        existing = session.scalar(stmt)

        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.now(tz=timezone.utc)
            record = existing
            logger.info("Updated earnings record for %s %s", ticker, periodo)
        else:
            record = EarningsRecord(**kwargs)
            session.add(record)
            session.flush()
            logger.info("Inserted earnings record for %s %s (id=%d)", ticker, periodo, record.id)

        # Update operational KPIs — delete old, insert new
        from sqlalchemy import delete

        session.execute(
            delete(OperationalKPI).where(
                OperationalKPI.ticker == ticker,
                OperationalKPI.periodo == periodo,
            )
        )
        for kpi_name, kpi_data in (state.get("kpis_operacionais") or {}).items():
            if not isinstance(kpi_data, dict):
                continue
            kpi = OperationalKPI(
                ticker=ticker,
                periodo=periodo,
                nome_kpi=kpi_name,
                valor=kpi_data.get("valor"),
                unidade=kpi_data.get("unidade"),
                var_aa=kpi_data.get("var_aa"),
            )
            session.add(kpi)

        return record
