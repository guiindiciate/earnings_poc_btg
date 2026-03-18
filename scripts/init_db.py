#!/usr/bin/env python3
"""
Script de inicialização do banco de dados.
Cria todas as tabelas necessárias se não existirem.

Uso:
    python scripts/init_db.py
"""

import sys
import os

# Garante que o root do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import init_db
from config.settings import DATABASE_URL


def main():
    print(f"🗄️  Inicializando banco de dados...")
    print(f"   URL: {DATABASE_URL}")
    init_db()
    print("✅ Banco de dados inicializado com sucesso.")
    print("\nPróximo passo:")
    print("   python scripts/run_pipeline.py --pdf <caminho_do_pdf> --ticker <TICKER> --periodo <4T25>")


if __name__ == "__main__":
    main()
