#!/usr/bin/env python3
"""
Script para gerar Excel a partir do banco de dados (sem reprocessar o PDF).

Uso:
    python scripts/export_excel.py history --ticker VTRU3
    python scripts/export_excel.py history --ticker ITUB4 --output output/ITUB4.xlsx
    python scripts/export_excel.py comparative --tickers VTRU3 ITUB4 --periodo 4T25
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Gera Excel com histórico de KPIs a partir do banco de dados"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Comando: histórico de um ticker
    hist = subparsers.add_parser("history", help="Histórico de um ticker")
    hist.add_argument("--ticker", required=True, help="Ticker da empresa (ex: VTRU3)")
    hist.add_argument("--output", default=None, help="Caminho do arquivo Excel de saída")

    # Comando: comparativo entre tickers
    comp = subparsers.add_parser("comparative", help="Comparativo entre múltiplos tickers")
    comp.add_argument("--tickers", nargs="+", required=True, help="Lista de tickers")
    comp.add_argument("--periodo", required=True, help="Período para comparação (ex: 4T25)")
    comp.add_argument("--output", default=None, help="Caminho do arquivo Excel de saída")

    # Comando: listar tickers disponíveis
    subparsers.add_parser("list", help="Lista tickers disponíveis no banco")

    return parser.parse_args()


def main():
    args = parse_args()

    from src.output.excel_exporter import export_to_excel, export_comparative
    from src.storage.repository import get_all_tickers

    if args.command == "list":
        tickers = get_all_tickers()
        if tickers:
            print(f"📊 Tickers disponíveis no banco ({len(tickers)}):")
            for t in tickers:
                print(f"   - {t}")
        else:
            print("❌ Nenhum ticker encontrado. Execute o pipeline primeiro.")

    elif args.command == "history":
        output = args.output or f"output/{args.ticker}_resultados.xlsx"
        os.makedirs(os.path.dirname(output), exist_ok=True)
        print(f"📁 Gerando histórico para {args.ticker}...")
        path = export_to_excel(ticker=args.ticker.upper(), output_path=output)
        print(f"✅ Excel gerado: {path}")

    elif args.command == "comparative":
        output = args.output or f"output/comparativo_{args.periodo}.xlsx"
        os.makedirs(os.path.dirname(output), exist_ok=True)
        tickers = [t.upper() for t in args.tickers]
        print(f"📁 Gerando comparativo {args.periodo} para: {', '.join(tickers)}...")
        path = export_comparative(
            tickers=tickers,
            periodo=args.periodo.upper(),
            output_path=output
        )
        print(f"✅ Excel gerado: {path}")


if __name__ == "__main__":
    main()
