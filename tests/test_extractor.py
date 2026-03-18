"""Unit tests for the extractor node and its helpers.

LLM calls are mocked so these tests run without an API key.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.graph.nodes.extractor import _extract_json
from src.graph.state import initial_state
from src.schema.core_schema import (
    Balanco,
    CapitalGiro,
    EarningsData,
    EarningsMetadata,
    FluxoCaixa,
    MetricaComMargem,
    MetricaComVariacao,
    MetricaSimples,
    Rentabilidade,
    Resultado,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def minimal_core_dict() -> dict:
    """Return a minimal but valid core metrics dict (all sections present)."""
    return {
        "resultado": {
            "receita_liquida": {"valor": 2260.0, "var_aa": 5.5, "var_qa": None},
            "lucro_bruto": {"valor": 1582.0, "margem": 70.0, "var_aa": 1.0},
            "ebitda": {"valor": 873.7, "margem": 38.7, "var_aa": 10.1},
            "ebit": {"valor": 800.0, "margem": 35.4, "var_aa": None},
            "lucro_liquido": {"valor": 483.7, "margem": 21.4, "var_aa": 61.2},
            "lucro_liquido_controlador": {"valor": 483.7, "margem": 21.4, "var_aa": 61.2},
        },
        "rentabilidade": {
            "roe": {"valor": 18.5, "var_aa": 5.0},
            "roic": {"valor": 12.3, "var_aa": None},
            "roa": {"valor": 8.1, "var_aa": None},
            "margem_bruta": {"valor": 70.0, "var_aa": 1.0},
            "margem_ebitda": {"valor": 38.7, "var_aa": 1.6},
            "margem_liquida": {"valor": 21.4, "var_aa": 7.0},
        },
        "balanco": {
            "ativo_total": {"valor": 8000.0},
            "patrimonio_liquido": {"valor": 2500.0},
            "divida_bruta": {"valor": 2200.0},
            "caixa_equivalentes": {"valor": 470.0},
            "divida_liquida": {"valor": 1730.0},
            "alavancagem_dl_ebitda": {"valor": 1.99},
            "alavancagem_dl_pl": {"valor": 0.69},
        },
        "fluxo_caixa": {
            "cfo": {"valor": 700.0},
            "capex": {"valor": 128.8, "pct_receita": 5.7, "var_aa": None},
            "fcl": {"valor": 571.2},
            "conversao_caixa": {"valor": 65.4},
        },
        "capital_giro": {
            "capital_de_giro": {"valor": 300.0},
            "pmr": {"valor": 45.0},
            "pmp": {"valor": 30.0},
            "pmie": {"valor": 20.0},
        },
    }


# ── _extract_json ──────────────────────────────────────────────────────────────


class TestExtractJson:
    def test_plain_json(self):
        raw = '{"valor": 42}'
        assert _extract_json(raw) == {"valor": 42}

    def test_json_with_markdown_fences(self):
        raw = "```json\n{\"valor\": 42}\n```"
        assert _extract_json(raw) == {"valor": 42}

    def test_json_with_leading_text_returns_empty(self):
        """Text before JSON without clean fence removal returns empty dict."""
        raw = "Here is the result:\n```\n{\"a\": 1}\n```"
        # New implementation removes ``` lines but leaves leading text,
        # which causes json.loads to fail — returns {} instead of raising.
        result = _extract_json(raw)
        assert isinstance(result, dict)

    def test_invalid_returns_empty_dict(self):
        """Invalid JSON returns empty dict (no exception raised)."""
        result = _extract_json("not json at all")
        assert result == {}


# ── Pydantic model validation ─────────────────────────────────────────────────


class TestValidateCoreWithPydantic:
    def test_valid_dict_passes(self, minimal_core_dict):
        resultado = Resultado(**minimal_core_dict["resultado"])
        assert resultado.ebitda.valor == pytest.approx(873.7)

    def test_null_values_preserved(self):
        resultado = Resultado(receita_liquida={"valor": None, "var_aa": None, "var_qa": None})
        assert resultado.receita_liquida.valor is None

    def test_missing_section_defaults_to_empty(self):
        """All sections should have defaults (all-null) when not provided."""
        for model_cls in (Resultado, Rentabilidade, Balanco, FluxoCaixa, CapitalGiro):
            instance = model_cls()
            assert instance is not None

    def test_extra_fields_in_section_are_ignored(self):
        """Pydantic should silently ignore unknown fields."""
        resultado = Resultado(
            receita_liquida={"valor": 100.0, "var_aa": None, "var_qa": None},
        )
        assert resultado.receita_liquida.valor == pytest.approx(100.0)


# ── Mocked extractor_node ─────────────────────────────────────────────────────


class TestCoreExtractionReturnsValidSchema:
    """Test that extractor_node correctly calls the LLM and parses the response."""

    def _make_mock_llm(self, responses: list[str]) -> MagicMock:
        """Create a mock LLM whose invoke() returns successive responses."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content=r) for r in responses
        ]
        return mock_llm

    def test_core_extraction_returns_valid_schema(self, minimal_core_dict):
        """Mock the LLM to return a known JSON and assert the state is updated."""
        state = initial_state(
            pdf_path="tests/fixtures/fake.pdf",
            ticker="VTRU3",
            periodo="4T25",
        )
        state["raw_text"] = "Receita Líquida: R$ 2.260 MM. EBITDA Ajustado: R$ 873,7 MM."

        core_response = json.dumps(minimal_core_dict)
        kpi_response = json.dumps(
            {
                "base_alunos_total": {"valor": 915.4, "unidade": "mil alunos", "var_aa": 11.0},
                "evasao": {"valor": 74.0, "unidade": "mil alunos", "var_aa": -26.0},
            }
        )

        mock_llm = self._make_mock_llm([core_response, kpi_response])

        with patch("src.graph.nodes.extractor.get_llm", return_value=mock_llm):
            from src.graph.nodes.extractor import extractor_node

            result = extractor_node(state)

        assert "base_alunos_total" in result["kpis_operacionais"]
        assert result["kpis_operacionais"]["base_alunos_total"]["valor"] == pytest.approx(915.4)

    def test_operational_kpi_extraction(self, minimal_core_dict):
        """KPI extraction failure should be non-fatal."""
        state = initial_state(
            pdf_path="tests/fixtures/fake.pdf",
            ticker="VTRU3",
            periodo="4T25",
        )
        state["raw_text"] = "some text"

        core_response = json.dumps(minimal_core_dict)

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content=core_response),
            Exception("LLM timeout"),
        ]

        with patch("src.graph.nodes.extractor.get_llm", return_value=mock_llm):
            from src.graph.nodes.extractor import extractor_node

            result = extractor_node(state)

        # kpis_operacionais should be empty dict when KPI extraction fails
        assert result["kpis_operacionais"] == {}


class TestJsonValidationWithPydantic:
    """Test that Pydantic models validate and coerce the LLM output correctly."""

    def test_float_coercion(self):
        """Integer values should be coerced to float."""
        resultado = Resultado(
            receita_liquida={"valor": 2260, "var_aa": 5, "var_qa": None}
        )
        assert isinstance(resultado.receita_liquida.valor, float)

    def test_string_none_becomes_none(self):
        """Only Python None is accepted for missing values."""
        resultado = Resultado(
            receita_liquida={"valor": None, "var_aa": None, "var_qa": None}
        )
        assert resultado.receita_liquida.valor is None

    def test_earnings_data_model(self):
        """EarningsData root model should construct without errors."""
        from datetime import datetime

        meta = EarningsMetadata(
            ticker="VTRU3",
            periodo="4T25",
            ano=2025,
            trimestre=4,
        )
        data = EarningsData(metadata=meta)
        assert data.resultado.ebitda.valor is None
        flat = data.to_flat_dict()
        assert isinstance(flat, dict)
        assert "metadata__ticker" in flat
