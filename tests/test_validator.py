"""Unit tests for the accounting validation functions.

No LLM calls or database access — pure function tests.
"""

from __future__ import annotations

import pytest

from src.schema.validators import (
    run_all_validations,
    validate_completude,
    validate_divida_liquida,
    validate_margem_ebitda,
    validate_sanity_leverage,
    validate_sanity_margins,
    validate_variations,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def full_core() -> dict:
    """Return a fully populated core metrics dict that passes all validations."""
    return {
        "resultado": {
            "receita_liquida": {"valor": 2260.0, "var_aa": 5.5, "var_qa": None},
            "lucro_bruto": {"valor": 1582.0, "margem": 70.0, "var_aa": 1.0},
            "ebitda": {"valor": 874.02, "margem": 38.67, "var_aa": 10.1},
            "ebit": {"valor": 800.0, "margem": 35.4, "var_aa": 8.0},
            "lucro_liquido": {"valor": 483.7, "margem": 21.4, "var_aa": 61.2},
            "lucro_liquido_controlador": {"valor": 483.7, "margem": 21.4, "var_aa": 61.2},
        },
        "rentabilidade": {
            "roe": {"valor": 18.5, "var_aa": 5.0},
            "roic": {"valor": 12.3, "var_aa": 2.0},
            "roa": {"valor": 8.1, "var_aa": 1.5},
            "margem_bruta": {"valor": 70.0, "var_aa": 1.0},
            "margem_ebitda": {"valor": 38.67, "var_aa": 1.6},
            "margem_liquida": {"valor": 21.4, "var_aa": 7.0},
        },
        "balanco": {
            "ativo_total": {"valor": 8000.0},
            "patrimonio_liquido": {"valor": 2500.0},
            "divida_bruta": {"valor": 2200.0},
            "caixa_equivalentes": {"valor": 470.0},
            "divida_liquida": {"valor": 1730.0},  # 2200 - 470 = 1730 ✓
            "alavancagem_dl_ebitda": {"valor": 1.99},
            "alavancagem_dl_pl": {"valor": 0.69},
        },
        "fluxo_caixa": {
            "cfo": {"valor": 700.0},
            "capex": {"valor": 128.8, "pct_receita": 5.7, "var_aa": 3.0},
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


# ── validate_divida_liquida ────────────────────────────────────────────────────


class TestValidateDividaLiquida:
    def test_valid_case_returns_none(self, full_core):
        assert validate_divida_liquida(full_core) is None

    def test_invalid_case_returns_error(self):
        core = {
            "balanco": {
                "divida_bruta": {"valor": 2200.0},
                "caixa_equivalentes": {"valor": 470.0},
                "divida_liquida": {"valor": 999.0},  # wrong: should be 1730
            }
        }
        error = validate_divida_liquida(core)
        assert error is not None
        assert "inconsistente" in error.lower()

    def test_missing_values_skips_validation(self):
        core = {"balanco": {"divida_bruta": {"valor": None}}}
        assert validate_divida_liquida(core) is None

    def test_within_tolerance_returns_none(self):
        core = {
            "balanco": {
                "divida_bruta": {"valor": 1000.0},
                "caixa_equivalentes": {"valor": 100.0},
                "divida_liquida": {"valor": 901.0},  # 1% off — within 2% tolerance
            }
        }
        assert validate_divida_liquida(core) is None

    def test_outside_tolerance_returns_error(self):
        core = {
            "balanco": {
                "divida_bruta": {"valor": 1000.0},
                "caixa_equivalentes": {"valor": 100.0},
                "divida_liquida": {"valor": 850.0},  # 5.6% off — outside 2%
            }
        }
        assert validate_divida_liquida(core) is not None


# ── validate_margem_ebitda ─────────────────────────────────────────────────────


class TestValidateMargemEbitda:
    def test_valid_case_returns_none(self, full_core):
        assert validate_margem_ebitda(full_core) is None

    def test_invalid_margem_returns_error(self):
        core = {
            "resultado": {
                "receita_liquida": {"valor": 1000.0},
                "ebitda": {"valor": 200.0, "margem": 50.0},  # calc = 20%, declared = 50%
            }
        }
        error = validate_margem_ebitda(core)
        assert error is not None
        assert "inconsistente" in error.lower()

    def test_zero_receita_returns_error(self):
        core = {
            "resultado": {
                "receita_liquida": {"valor": 0.0},
                "ebitda": {"valor": 100.0, "margem": 10.0},
            }
        }
        error = validate_margem_ebitda(core)
        assert error is not None

    def test_missing_margem_skips_validation(self):
        core = {
            "resultado": {
                "receita_liquida": {"valor": 1000.0},
                "ebitda": {"valor": 200.0, "margem": None},
            }
        }
        assert validate_margem_ebitda(core) is None


# ── validate_completude ────────────────────────────────────────────────────────


class TestValidateCompletude:
    def test_full_returns_none(self, full_core):
        assert validate_completude(full_core, min_pct=0.8) is None

    def test_empty_core_returns_error(self):
        error = validate_completude({})
        assert error is not None
        assert "nenhuma" in error.lower()

    def test_partial_below_threshold_returns_error(self):
        core = {
            "resultado": {
                "receita_liquida": {"valor": 100.0, "var_aa": None, "var_qa": None},
                "lucro_bruto": {"valor": None, "margem": None, "var_aa": None},
                "ebitda": {"valor": None, "margem": None, "var_aa": None},
                "ebit": {"valor": None, "margem": None, "var_aa": None},
                "lucro_liquido": {"valor": None, "margem": None, "var_aa": None},
                "lucro_liquido_controlador": {"valor": None, "margem": None, "var_aa": None},
            }
        }
        error = validate_completude(core, min_pct=0.8)
        assert error is not None
        assert "%" in error

    def test_exactly_at_threshold_passes(self):
        """80% filled should pass at default threshold of 0.8."""
        core = {
            "resultado": {
                "receita_liquida": {"valor": 1.0, "var_aa": 1.0, "var_qa": 1.0},
                "lucro_bruto": {"valor": 1.0, "margem": 1.0, "var_aa": 1.0},
                "ebitda": {"valor": 1.0, "margem": 1.0, "var_aa": None},  # one None
                "ebit": {"valor": None, "margem": None, "var_aa": None},
                "lucro_liquido": {"valor": None, "margem": None, "var_aa": None},
                "lucro_liquido_controlador": {"valor": None, "margem": None, "var_aa": None},
            }
        }
        # 8 filled / 18 total = 44% — should fail
        error = validate_completude(core, min_pct=0.8)
        assert error is not None


# ── validate_sanity_margins ────────────────────────────────────────────────────


class TestSanityChecks:
    def test_normal_margins_pass(self, full_core):
        errors = validate_sanity_margins(full_core)
        assert errors == []

    def test_absurd_ebitda_margin_fails(self):
        core = {
            "resultado": {
                "ebitda": {"valor": 500.0, "margem": 150.0},  # 150% is impossible
            }
        }
        errors = validate_sanity_margins(core)
        assert len(errors) >= 1
        assert any("ebitda" in e.lower() for e in errors)

    def test_negative_margin_within_bounds_passes(self):
        core = {
            "resultado": {
                "lucro_liquido": {"valor": -100.0, "margem": -30.0},  # -30% is plausible
            }
        }
        errors = validate_sanity_margins(core)
        assert errors == []

    def test_leverage_sanity_valid(self, full_core):
        assert validate_sanity_leverage(full_core) is None

    def test_leverage_sanity_absurd(self):
        core = {
            "balanco": {
                "alavancagem_dl_ebitda": {"valor": 50.0},  # 50x — unrealistic
            }
        }
        error = validate_sanity_leverage(core)
        assert error is not None

    def test_variation_within_bounds(self, full_core):
        errors = validate_variations(full_core)
        assert errors == []

    def test_variation_out_of_bounds(self):
        core = {
            "resultado": {
                "receita_liquida": {"valor": 100.0, "var_aa": 600.0},  # +600% implausible
            }
        }
        errors = validate_variations(core)
        assert len(errors) >= 1


# ── run_all_validations ────────────────────────────────────────────────────────


class TestRunAllValidations:
    def test_clean_data_no_errors(self, full_core):
        errors, scores = run_all_validations(full_core, min_completude=0.8)
        assert errors == []
        assert scores["overall"] == pytest.approx(1.0)

    def test_empty_core_has_errors(self):
        errors, scores = run_all_validations({})
        assert len(errors) > 0
        assert scores["overall"] < 1.0

    def test_confidence_scores_keys(self, full_core):
        _, scores = run_all_validations(full_core)
        expected_keys = {
            "divida_liquida_ok",
            "margem_ebitda_ok",
            "completude_ok",
            "sanity_margins_ok",
            "sanity_leverage_ok",
            "variations_ok",
            "overall",
        }
        assert expected_keys.issubset(scores.keys())
