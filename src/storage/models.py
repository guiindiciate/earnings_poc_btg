"""SQLAlchemy 2.0 ORM models for the earnings pipeline.

Three tables are defined:

* :class:`EarningsRecord`   — one row per (ticker, period), flat metric columns.
* :class:`OperationalKPI`   — one row per operational KPI per (ticker, period).
* :class:`ExtractionLog`    — audit log for every pipeline run.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ── EarningsRecord ─────────────────────────────────────────────────────────────


class EarningsRecord(Base):
    """One row per (ticker, periodo) — flat columns for all core metrics."""

    __tablename__ = "earnings_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Identity ──────────────────────────────────────────────────────────────
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    periodo: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    ano: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trimestre: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Metadata ──────────────────────────────────────────────────────────────
    empresa: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_referencia: Mapped[str | None] = mapped_column(String(20), nullable=True)
    data_extracao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )
    arquivo_origem: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metodo_extracao: Mapped[str] = mapped_column(String(50), default="automated", nullable=False)
    confianca_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    revisao_manual: Mapped[bool] = mapped_column(Integer, default=False, nullable=False)
    analista: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # ── Resultado ──────────────────────────────────────────────────────────────
    receita_liquida: Mapped[float | None] = mapped_column(Float, nullable=True)
    receita_liquida_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)
    receita_liquida_var_qa: Mapped[float | None] = mapped_column(Float, nullable=True)

    lucro_bruto: Mapped[float | None] = mapped_column(Float, nullable=True)
    lucro_bruto_margem: Mapped[float | None] = mapped_column(Float, nullable=True)
    lucro_bruto_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebitda_margem: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebitda_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    ebit: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebit_margem: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebit_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    lucro_liquido: Mapped[float | None] = mapped_column(Float, nullable=True)
    lucro_liquido_margem: Mapped[float | None] = mapped_column(Float, nullable=True)
    lucro_liquido_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    lucro_liquido_controlador: Mapped[float | None] = mapped_column(Float, nullable=True)
    lucro_liquido_controlador_margem: Mapped[float | None] = mapped_column(Float, nullable=True)
    lucro_liquido_controlador_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Rentabilidade ─────────────────────────────────────────────────────────
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    roe_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    roic: Mapped[float | None] = mapped_column(Float, nullable=True)
    roic_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    roa: Mapped[float | None] = mapped_column(Float, nullable=True)
    roa_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    margem_bruta: Mapped[float | None] = mapped_column(Float, nullable=True)
    margem_bruta_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    margem_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    margem_ebitda_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    margem_liquida: Mapped[float | None] = mapped_column(Float, nullable=True)
    margem_liquida_var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Balanço ───────────────────────────────────────────────────────────────
    ativo_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    patrimonio_liquido: Mapped[float | None] = mapped_column(Float, nullable=True)
    divida_bruta: Mapped[float | None] = mapped_column(Float, nullable=True)
    caixa_equivalentes: Mapped[float | None] = mapped_column(Float, nullable=True)
    divida_liquida: Mapped[float | None] = mapped_column(Float, nullable=True)
    alavancagem_dl_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    alavancagem_dl_pl: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Fluxo de Caixa ────────────────────────────────────────────────────────
    cfo: Mapped[float | None] = mapped_column(Float, nullable=True)
    capex: Mapped[float | None] = mapped_column(Float, nullable=True)
    capex_pct_receita: Mapped[float | None] = mapped_column(Float, nullable=True)
    fcl: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversao_caixa: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Capital de Giro ───────────────────────────────────────────────────────
    capital_de_giro: Mapped[float | None] = mapped_column(Float, nullable=True)
    pmr: Mapped[float | None] = mapped_column(Float, nullable=True)
    pmp: Mapped[float | None] = mapped_column(Float, nullable=True)
    pmie: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        onupdate=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )


# ── OperationalKPI ────────────────────────────────────────────────────────────


class OperationalKPI(Base):
    """One row per operational KPI per (ticker, periodo)."""

    __tablename__ = "operational_kpis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    periodo: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    nome_kpi: Mapped[str] = mapped_column(String(100), nullable=False)
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    unidade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    var_aa: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )


# ── ExtractionLog ─────────────────────────────────────────────────────────────


class ExtractionLog(Base):
    """Audit log for every pipeline run."""

    __tablename__ = "extraction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    periodo: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    erros_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confianca_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    arquivo_origem: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )
