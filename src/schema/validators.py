"""Accounting validation functions for extracted earnings data.

All functions are pure (no side-effects) and return either ``None`` (no error)
or a descriptive error string.  The aggregate :func:`run_all_validations`
function is the main entry point used by the validator node.
"""

from __future__ import annotations

from typing import Optional


# ── Individual validation rules ────────────────────────────────────────────────


def validate_divida_liquida(core: dict, tolerance: float = 0.02) -> Optional[str]:
    """Verify that net debt equals gross debt minus cash (within tolerance).

    Parameters
    ----------
    core:
        ``core_metrics`` dict with a ``"balanco"`` sub-key.
    tolerance:
        Relative tolerance (default 2%).

    Returns
    -------
    Optional[str]
        Error message if the check fails, ``None`` otherwise.
    """
    balanco = core.get("balanco", {})
    db = (balanco.get("divida_bruta") or {}).get("valor")
    caixa = (balanco.get("caixa_equivalentes") or {}).get("valor")
    dl = (balanco.get("divida_liquida") or {}).get("valor")

    if db is None or caixa is None or dl is None:
        return None  # can't validate missing data

    expected = db - caixa
    if expected == 0:
        if dl != 0:
            return f"Dívida Líquida inconsistente: esperado {expected:.2f}, encontrado {dl:.2f}"
        return None

    relative_diff = abs(dl - expected) / abs(expected)
    if relative_diff > tolerance:
        return (
            f"Dívida Líquida inconsistente: DB({db:.2f}) - Caixa({caixa:.2f}) "
            f"= {expected:.2f}, mas registrado {dl:.2f} "
            f"(diferença de {relative_diff * 100:.1f}%, tolerância {tolerance * 100:.0f}%)"
        )
    return None


def validate_margem_ebitda(core: dict, tolerance: float = 0.01) -> Optional[str]:
    """Validate the reported EBITDA margin against a calculated one.

    Parameters
    ----------
    core:
        ``core_metrics`` dict.
    tolerance:
        Absolute tolerance in percentage points (default 1 p.p.).

    Returns
    -------
    Optional[str]
        Error message if the check fails, ``None`` otherwise.
    """
    resultado = core.get("resultado", {})
    receita = (resultado.get("receita_liquida") or {}).get("valor")
    ebitda_val = (resultado.get("ebitda") or {}).get("valor")
    ebitda_margem = (resultado.get("ebitda") or {}).get("margem")

    if receita is None or ebitda_val is None or ebitda_margem is None:
        return None

    if receita == 0:
        return "Receita Líquida é zero — impossível calcular margem EBITDA"

    calc_margem = (ebitda_val / receita) * 100
    diff = abs(calc_margem - ebitda_margem)
    if diff > tolerance * 100:
        return (
            f"Margem EBITDA inconsistente: calculada {calc_margem:.2f}%, "
            f"declarada {ebitda_margem:.2f}% (diferença {diff:.2f} p.p.)"
        )
    return None


def validate_completude(core: dict, min_pct: float = 0.8) -> Optional[str]:
    """Check that at least *min_pct* of core metric values are non-null.

    Parameters
    ----------
    core:
        ``core_metrics`` dict.
    min_pct:
        Minimum fraction of fields that must be populated (default 0.80).

    Returns
    -------
    Optional[str]
        Error message if completeness is below threshold, ``None`` otherwise.
    """
    sections = ["resultado", "rentabilidade", "balanco", "fluxo_caixa", "capital_giro"]
    total = 0
    filled = 0

    for section in sections:
        section_data = core.get(section, {})
        for _metric, metric_data in section_data.items():
            if not isinstance(metric_data, dict):
                continue
            for _field, value in metric_data.items():
                total += 1
                if value is not None:
                    filled += 1

    if total == 0:
        return "Nenhuma métrica core extraída"

    pct = filled / total
    if pct < min_pct:
        return (
            f"Completude insuficiente: {filled}/{total} campos preenchidos "
            f"({pct * 100:.1f}%, mínimo {min_pct * 100:.0f}%)"
        )
    return None


def validate_sanity_margins(core: dict) -> list[str]:
    """Check that margin values lie within a plausible range [-50%, 100%].

    Returns
    -------
    list[str]
        List of error messages (empty if all checks pass).
    """
    errors: list[str] = []
    resultado = core.get("resultado", {})
    margem_fields = [
        ("ebitda", "margem"),
        ("ebit", "margem"),
        ("lucro_bruto", "margem"),
        ("lucro_liquido", "margem"),
    ]
    for metric_name, field in margem_fields:
        value = (resultado.get(metric_name) or {}).get(field)
        if value is not None and not (-50.0 <= value <= 100.0):
            errors.append(
                f"Margem {metric_name} fora do intervalo plausível: {value:.2f}% "
                "(esperado entre -50% e 100%)"
            )
    return errors


def validate_sanity_leverage(core: dict) -> Optional[str]:
    """Check that DL/EBITDA leverage is within a plausible range [-5x, 30x].

    Returns
    -------
    Optional[str]
        Error message if the check fails, ``None`` otherwise.
    """
    balanco = core.get("balanco", {})
    alavancagem = (balanco.get("alavancagem_dl_ebitda") or {}).get("valor")
    if alavancagem is not None and not (-5.0 <= alavancagem <= 30.0):
        return (
            f"Alavancagem DL/EBITDA fora do intervalo plausível: {alavancagem:.2f}x "
            "(esperado entre -5x e 30x)"
        )
    return None


def validate_variations(core: dict) -> list[str]:
    """Check that year-over-year variations lie within [-100%, +500%].

    Returns
    -------
    list[str]
        List of error messages (empty if all checks pass).
    """
    errors: list[str] = []
    sections = ["resultado", "rentabilidade", "balanco", "fluxo_caixa", "capital_giro"]

    for section in sections:
        section_data = core.get(section, {})
        for metric_name, metric_data in section_data.items():
            if not isinstance(metric_data, dict):
                continue
            var_aa = metric_data.get("var_aa")
            if var_aa is not None and not (-100.0 <= var_aa <= 500.0):
                errors.append(
                    f"Variação a/a de {section}.{metric_name} fora do intervalo plausível: "
                    f"{var_aa:.2f}% (esperado entre -100% e +500%)"
                )
    return errors


# ── Aggregate runner ───────────────────────────────────────────────────────────


def run_all_validations(
    core: dict, min_completude: float = 0.8
) -> tuple[list[str], dict]:
    """Run all validation rules and compute confidence scores.

    Parameters
    ----------
    core:
        ``core_metrics`` dict (as returned by the extractor node).
    min_completude:
        Minimum completeness threshold passed to :func:`validate_completude`.

    Returns
    -------
    tuple[list[str], dict]
        ``(errors, confidence_scores)`` where *errors* is a (possibly empty)
        list of human-readable error strings and *confidence_scores* is a dict
        with per-check boolean flags and an overall score.
    """
    errors: list[str] = []

    checks = {
        "divida_liquida_ok": True,
        "margem_ebitda_ok": True,
        "completude_ok": True,
        "sanity_margins_ok": True,
        "sanity_leverage_ok": True,
        "variations_ok": True,
    }

    err = validate_divida_liquida(core)
    if err:
        errors.append(err)
        checks["divida_liquida_ok"] = False

    err = validate_margem_ebitda(core)
    if err:
        errors.append(err)
        checks["margem_ebitda_ok"] = False

    err = validate_completude(core, min_pct=min_completude)
    if err:
        errors.append(err)
        checks["completude_ok"] = False

    margin_errs = validate_sanity_margins(core)
    if margin_errs:
        errors.extend(margin_errs)
        checks["sanity_margins_ok"] = False

    err = validate_sanity_leverage(core)
    if err:
        errors.append(err)
        checks["sanity_leverage_ok"] = False

    variation_errs = validate_variations(core)
    if variation_errs:
        errors.extend(variation_errs)
        checks["variations_ok"] = False

    # Simple overall confidence: fraction of checks that passed
    passed = sum(1 for v in checks.values() if v)
    overall = passed / len(checks)
    confidence_scores = {**checks, "overall": round(overall, 4)}

    return errors, confidence_scores
