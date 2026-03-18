#!/usr/bin/env python3
"""
Script principal para executar o pipeline de extração de earnings.

Uso:
    python scripts/run_pipeline.py --pdf tests/fixtures/vitru_4t25.pdf --ticker VTRU3 --periodo 4T25
    python scripts/run_pipeline.py --pdf itau_4t25.pdf --ticker ITUB4 --periodo 4T25
    python scripts/run_pipeline.py --help
"""

import argparse
import json
import logging
import os
import sys

# Garante que o root do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pipeline de extração de KPIs de earnings releases via LangGraph + Bedrock"
    )
    parser.add_argument(
        "--pdf", required=True,
        help="Caminho para o arquivo PDF do earnings release"
    )
    parser.add_argument(
        "--ticker", required=True,
        help="Ticker da empresa (ex: VTRU3, ITUB4, PETR4)"
    )
    parser.add_argument(
        "--periodo", required=True,
        help="Período do resultado (ex: 4T25, 1T26)"
    )
    parser.add_argument(
        "--no-excel", action="store_true", default=False,
        help="Não gerar arquivo Excel após extração"
    )
    parser.add_argument(
        "--output-dir", default="output/",
        help="Diretório para salvar o Excel (padrão: output/)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Validações de input
    if not os.path.exists(args.pdf):
        print(f"❌ Arquivo PDF não encontrado: {args.pdf}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Earnings Pipeline — LangGraph + Amazon Bedrock")
    print(f"{'='*60}")
    print(f"  PDF     : {args.pdf}")
    print(f"  Ticker  : {args.ticker}")
    print(f"  Período : {args.periodo}")
    print(f"{'='*60}\n")

    # Importa após validação para não atrasar erros de input
    from src.graph.workflow import app
    from src.graph.state import initial_state
    from config.settings import LLM_PROVIDER, BEDROCK_MODEL_ID, AWS_REGION

    print(f"🤖 LLM Provider : {LLM_PROVIDER.upper()}")
    if LLM_PROVIDER == "bedrock":
        print(f"   Modelo        : {BEDROCK_MODEL_ID}")
        print(f"   Região AWS    : {AWS_REGION}")
    print()

    # Executa o pipeline
    print("🚀 Iniciando pipeline...\n")
    state = initial_state(
        pdf_path=args.pdf,
        ticker=args.ticker.upper(),
        periodo=args.periodo.upper(),
    )

    result = app.invoke(state)

    # Exibe resultado
    print(f"\n{'='*60}")
    print(f"  RESULTADO DA EXTRAÇÃO")
    print(f"{'='*60}")
    print(f"  Status      : {_status_emoji(result['status'])} {result['status'].upper()}")
    print(f"  Confiança   : {_format_confidence(result.get('confidence_scores', {}))}")

    if result.get("validation_errors"):
        print(f"\n  ⚠️  Erros de validação:")
        for err in result["validation_errors"]:
            print(f"     - {err}")

    # Exibe core metrics extraídas
    print(f"\n  📊 Core Metrics extraídas:")
    _print_core_metrics(result.get("core_metrics", {}))

    # Exibe KPIs operacionais
    kpis_op = result.get("kpis_operacionais", {})
    if kpis_op:
        print(f"\n  🔢 KPIs Operacionais ({len(kpis_op)} encontrados):")
        for kpi, data in list(kpis_op.items())[:10]:  # mostra até 10
            valor = data.get("valor", "N/A") if isinstance(data, dict) else data
            unidade = data.get("unidade", "") if isinstance(data, dict) else ""
            print(f"     - {kpi}: {valor} {unidade}")
        if len(kpis_op) > 10:
            print(f"     ... e mais {len(kpis_op) - 10} KPIs")

    # Gera Excel
    if not args.no_excel and result["status"] in ("approved", "awaiting_human"):
        print(f"\n  📁 Gerando Excel...")
        try:
            from src.output.excel_exporter import export_to_excel
            os.makedirs(args.output_dir, exist_ok=True)
            excel_path = export_to_excel(
                ticker=args.ticker.upper(),
                output_path=os.path.join(args.output_dir, f"{args.ticker.upper()}_resultados.xlsx")
            )
            print(f"  ✅ Excel gerado: {excel_path}")
        except Exception as e:
            print(f"  ⚠️  Erro ao gerar Excel: {e}")

    print(f"\n{'='*60}\n")

    return 0 if result["status"] == "approved" else 1


def _status_emoji(status: str) -> str:
    return {
        "approved": "✅",
        "awaiting_human": "⚠️",
        "failed": "❌",
        "processing": "🔄",
    }.get(status, "❓")


def _format_confidence(scores: dict) -> str:
    if not scores:
        return "N/A"
    avg = sum(scores.values()) / len(scores) if scores else 0
    return f"{avg:.0%}"


def _print_core_metrics(core_metrics: dict):
    """Imprime as principais core metrics de forma legível."""
    display_map = {
        "resultado.receita_liquida.valor": "Receita Líquida",
        "resultado.ebitda.valor": "EBITDA",
        "resultado.ebitda.margem": "Margem EBITDA",
        "resultado.lucro_liquido.valor": "Lucro Líquido",
        "balanco.divida_liquida.valor": "Dívida Líquida",
        "balanco.alavancagem_dl_ebitda.valor": "Alavancagem DL/EBITDA",
        "fluxo_caixa.fcl.valor": "Fluxo de Caixa Livre",
    }

    for path, label in display_map.items():
        value = _get_nested(core_metrics, path)
        if value is not None:
            print(f"     - {label}: {value}")


def _get_nested(d: dict, path: str):
    """Acessa valor aninhado via path com pontos (ex: 'resultado.ebitda.valor')."""
    keys = path.split(".")
    for key in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


if __name__ == "__main__":
    sys.exit(main())
