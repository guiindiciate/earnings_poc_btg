"""Pydantic v2 models representing the canonical earnings data schema.

These models are the authoritative source of truth for every metric stored
in the database and exported to Excel.  All fields are ``Optional[float]``
so that partial extractions are valid — completeness is enforced by the
validator, not by model construction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Primitive metric building blocks ──────────────────────────────────────────


class MetricaComVariacao(BaseModel):
    """A metric that carries period-over-period variation data."""

    valor: Optional[float] = None
    """Raw value (R$ millions unless stated otherwise)."""

    var_aa: Optional[float] = None
    """Year-over-year variation in percentage points (e.g. 5.3 = 5.3%)."""

    var_qa: Optional[float] = None
    """Quarter-over-quarter variation in percentage points."""


class MetricaComMargem(BaseModel):
    """A metric that carries a margin alongside year-over-year variation."""

    valor: Optional[float] = None
    margem: Optional[float] = None
    """Margin as a percentage (e.g. 38.7 = 38.7%)."""

    var_aa: Optional[float] = None


class MetricaSimples(BaseModel):
    """A metric expressed by a single numeric value."""

    valor: Optional[float] = None


# ── Core financial statement sections ─────────────────────────────────────────


class Resultado(BaseModel):
    """Income statement metrics."""

    receita_liquida: MetricaComVariacao = Field(default_factory=MetricaComVariacao)
    lucro_bruto: MetricaComMargem = Field(default_factory=MetricaComMargem)
    ebitda: MetricaComMargem = Field(default_factory=MetricaComMargem)
    ebit: MetricaComMargem = Field(default_factory=MetricaComMargem)
    lucro_liquido: MetricaComMargem = Field(default_factory=MetricaComMargem)
    lucro_liquido_controlador: MetricaComMargem = Field(default_factory=MetricaComMargem)


class Rentabilidade(BaseModel):
    """Profitability / return ratios."""

    roe: MetricaComVariacao = Field(default_factory=MetricaComVariacao)
    roic: MetricaComVariacao = Field(default_factory=MetricaComVariacao)
    roa: MetricaComVariacao = Field(default_factory=MetricaComVariacao)
    margem_bruta: MetricaComVariacao = Field(default_factory=MetricaComVariacao)
    margem_ebitda: MetricaComVariacao = Field(default_factory=MetricaComVariacao)
    margem_liquida: MetricaComVariacao = Field(default_factory=MetricaComVariacao)


class Balanco(BaseModel):
    """Balance sheet metrics."""

    ativo_total: MetricaSimples = Field(default_factory=MetricaSimples)
    patrimonio_liquido: MetricaSimples = Field(default_factory=MetricaSimples)
    divida_bruta: MetricaSimples = Field(default_factory=MetricaSimples)
    caixa_equivalentes: MetricaSimples = Field(default_factory=MetricaSimples)
    divida_liquida: MetricaSimples = Field(default_factory=MetricaSimples)
    alavancagem_dl_ebitda: MetricaSimples = Field(default_factory=MetricaSimples)
    alavancagem_dl_pl: MetricaSimples = Field(default_factory=MetricaSimples)


class FluxoCaixa(BaseModel):
    """Cash flow metrics."""

    cfo: MetricaSimples = Field(default_factory=MetricaSimples)
    capex: MetricaComVariacao = Field(default_factory=MetricaComVariacao)
    fcl: MetricaSimples = Field(default_factory=MetricaSimples)
    conversao_caixa: MetricaSimples = Field(default_factory=MetricaSimples)


class CapitalGiro(BaseModel):
    """Working capital metrics."""

    capital_de_giro: MetricaSimples = Field(default_factory=MetricaSimples)
    pmr: MetricaSimples = Field(default_factory=MetricaSimples)
    pmp: MetricaSimples = Field(default_factory=MetricaSimples)
    pmie: MetricaSimples = Field(default_factory=MetricaSimples)


# ── Metadata ──────────────────────────────────────────────────────────────────


class EarningsMetadata(BaseModel):
    """Extraction metadata attached to every record."""

    ticker: str
    empresa: Optional[str] = None
    periodo: str
    ano: int
    trimestre: int
    data_referencia: Optional[str] = None
    data_extracao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    arquivo_origem: Optional[str] = None
    metodo_extracao: str = "automated"
    confianca_score: Optional[float] = None
    revisao_manual: bool = False
    analista: Optional[str] = None


# ── Root model ────────────────────────────────────────────────────────────────


class EarningsData(BaseModel):
    """Root model — the complete earnings record persisted to the database."""

    metadata: EarningsMetadata
    resultado: Resultado = Field(default_factory=Resultado)
    rentabilidade: Rentabilidade = Field(default_factory=Rentabilidade)
    balanco: Balanco = Field(default_factory=Balanco)
    fluxo_caixa: FluxoCaixa = Field(default_factory=FluxoCaixa)
    capital_giro: CapitalGiro = Field(default_factory=CapitalGiro)
    kpis_operacionais: dict[str, Any] = Field(default_factory=dict)
    """Free-form operational KPIs — structure varies by sector."""

    def to_flat_dict(self) -> dict[str, Any]:
        """Return a flat dictionary of all metric values for easy DB storage.

        Each nested field is flattened using double-underscore notation, e.g.
        ``resultado__receita_liquida__valor``.
        """

        def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
            result: dict[str, Any] = {}
            if isinstance(obj, BaseModel):
                for field_name, value in obj.model_dump().items():
                    result.update(_flatten(value, f"{prefix}{field_name}__"))
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    result.update(_flatten(value, f"{prefix}{key}__"))
            else:
                result[prefix.rstrip("__")] = obj
            return result

        return _flatten(self)
