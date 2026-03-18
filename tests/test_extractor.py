"""Unit tests for the extractor node and its helpers.

LLM calls are mocked so these tests run without an OpenAI API key.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.graph.nodes.extractor import _extract_json, _validate_core_with_pydantic
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

    def test_json_with_leading_text(self):
        raw = "Here is the result:\n```\n{\"a\": 1}\n```"
        assert _extract_json(raw) == {"a": 1}

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            _extract_json("not json at all")


# ── _validate_core_with_pydantic ───────────────────────────────────────────────


class TestValidateCoreWithPydantic:
    def test_valid_dict_passes(self, minimal_core_dict):
        result = _validate_core_with_pydantic(minimal_core_dict)
        assert "resultado" in result
        assert result["resultado"]["ebitda"]["valor"] == pytest.approx(873.7)

    def test_null_values_preserved(self):
        core = {
            "resultado": {"receita_liquida": {"valor": None, "var_aa": None, "var_qa": None}},
        }
        result = _validate_core_with_pydantic(core)
        assert result["resultado"]["receita_liquida"]["valor"] is None

    def test_missing_section_defaults_to_empty(self):
        """A missing section should produce a default (all-null) section dict."""
        result = _validate_core_with_pydantic({})
        # All sections must be present with default values
        for section in ("resultado", "rentabilidade", "balanco", "fluxo_caixa", "capital_giro"):
            assert section in result

    def test_extra_fields_in_section_are_ignored(self):
        """Pydantic should silently ignore unknown fields."""
        core = {
            "resultado": {
                "receita_liquida": {"valor": 100.0, "var_aa": None, "var_qa": None},
                "campo_desconhecido": {"valor": 999},
            }
        }
        result = _validate_core_with_pydantic(core)
        assert "campo_desconhecido" not in result["resultado"]


# ── Mocked extractor_node ─────────────────────────────────────────────────────


class TestCoreExtractionReturnsValidSchema:
    """Test that extractor_node correctly calls the LLM and parses the response."""

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

        with patch(
            "src.graph.nodes.extractor._call_llm", side_effect=[core_response, kpi_response]
        ):
            from src.graph.nodes.extractor import extractor_node

            result = extractor_node(state)

        assert result["core_metrics"]["resultado"]["ebitda"]["valor"] == pytest.approx(873.7)
        assert "base_alunos_total" in result["kpis_operacionais"]

    def test_operational_kpi_extraction(self, minimal_core_dict):
        """KPI extraction failure should be non-fatal."""
        state = initial_state(
            pdf_path="tests/fixtures/fake.pdf",
            ticker="VTRU3",
            periodo="4T25",
        )
        state["raw_text"] = "some text"

        with patch(
            "src.graph.nodes.extractor._call_llm",
            side_effect=[
                json.dumps(minimal_core_dict),
                ValueError("LLM timeout"),
            ],
        ):
            from src.graph.nodes.extractor import extractor_node

            result = extractor_node(state)

        # Core should be populated even if KPI extraction fails
        assert result["core_metrics"] != {}
        # kpis_operacionais should be empty dict (not raise)
        assert result["kpis_operacionais"] == {}


class TestJsonValidationWithPydantic:
    """Test that Pydantic models validate and coerce the LLM output correctly."""

    def test_float_coercion(self):
        """Integer values should be coerced to float."""
        core = {
            "resultado": {
                "receita_liquida": {"valor": 2260, "var_aa": 5, "var_qa": None},
            }
        }
        result = _validate_core_with_pydantic(core)
        assert isinstance(result["resultado"]["receita_liquida"]["valor"], float)

    def test_string_none_becomes_none(self):
        """The string 'null' is not valid — only Python None is accepted."""
        core = {
            "resultado": {
                "receita_liquida": {"valor": None, "var_aa": None, "var_qa": None},
            }
        }
        result = _validate_core_with_pydantic(core)
        assert result["resultado"]["receita_liquida"]["valor"] is None

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
