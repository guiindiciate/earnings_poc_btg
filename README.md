# Earnings Pipeline — LangGraph + LLM

> **Pipeline de extração de dados financeiros de earnings releases brasileiros usando LangGraph + GPT-4o, com persistência em banco de dados e geração de Excel sob demanda.**

---

## Visão Geral

O pipeline ingere PDFs de resultados trimestrais de empresas abertas brasileiras, extrai métricas financeiras estruturadas via LLM, valida as extrações com regras contábeis e persiste os dados em banco de dados relacional. O Excel é gerado sob demanda a partir do banco — nunca é a fonte de verdade.

### Princípios Fundamentais

| Princípio | Descrição |
|-----------|-----------|
| **Agnóstico de setor** | Funciona para qualquer empresa de capital aberto sem modificações de código |
| **DB como fonte de verdade** | Excel é camada de output; o banco persiste o histórico |
| **Escalável** | Preparado para centenas de empresas e múltiplos trimestres |
| **Rastreável** | Cada extração tem metadados completos (confiança, erros, analista) |
| **Incremental** | Cada novo trimestre adiciona dados ao histórico existente |

---

## Arquitetura LangGraph

```
[pdf_parser] → [extractor] → [validator] ──(approved)──→ [excel_writer] → END
                                   │
                      ┌────────────┼────────────┐
                 (review)     (failed)    (awaiting_human)
                      │            │
               [reconciler]  [human_review]
                      │            │
               [validator]   [excel_writer]
               (loop ≤ 2)
```

### Nós do Grafo

| Nó | Responsabilidade |
|----|-----------------|
| `parser` | Extrai texto e tabelas do PDF (pdfplumber + PyMuPDF + unstructured opcional) |
| `extractor` | Duas chamadas LLM: core metrics (schema fixo) + KPIs operacionais (livre) |
| `validator` | Validações contábeis: dívida líquida, margens, completude, sanity checks |
| `reconciler` | Auto-correção via LLM quando há erros (até `MAX_RETRIES` tentativas) |
| `human_review` | Escalona para revisão manual, salva JSON em `review_queue/` |
| `excel_writer` | Persiste no banco e gera o Excel histórico |

---

## Schema de Dados

```json
{
  "metadata": {
    "ticker": "VTRU3",
    "empresa": "Vitru Educação S.A.",
    "periodo": "4T25",
    "ano": 2025,
    "trimestre": 4,
    "confianca_score": 0.94,
    "revisao_manual": false
  },
  "resultado": {
    "receita_liquida":    {"valor": 2260.0, "var_aa": 5.5,  "var_qa": null},
    "ebitda":             {"valor": 873.7,  "margem": 38.7, "var_aa": 10.1},
    "lucro_liquido":      {"valor": 483.7,  "margem": 21.4, "var_aa": 61.2}
  },
  "balanco": {
    "divida_liquida":        {"valor": 1730.0},
    "alavancagem_dl_ebitda": {"valor": 1.99}
  },
  "kpis_operacionais": {
    "base_alunos_total": {"valor": 915.4, "unidade": "mil alunos", "var_aa": 11.0}
  }
}
```

> `kpis_operacionais` é **livre** — o LLM extrai dinamicamente qualquer KPI operacional encontrado no PDF.

---

## Instalação

```bash
# 1. Clonar o repositório
git clone <repo-url>
cd earnings-poc-btg

# 2. Instalar dependências
pip install -e ".[dev]"

# 3. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com sua OPENAI_API_KEY
```

### Dependências Opcionais (OCR para PDFs escaneados)

```bash
pip install -e ".[ocr]"
```

---

## Uso Básico

### Processar um PDF end-to-end

```python
from src.graph.workflow import app
from src.graph.state import initial_state

state = initial_state(
    pdf_path="tests/fixtures/vitru_4t25_earnings.pdf",
    ticker="VTRU3",
    periodo="4T25",
)
result = app.invoke(state)

print(result["status"])        # "approved" | "awaiting_human" | "failed"
print(result["excel_path"])    # caminho do Excel gerado
```

### Gerar Excel histórico

```python
from src.output.excel_exporter import export_to_excel

path = export_to_excel("VTRU3")
print(f"Excel gerado: {path}")
# output/VTRU3_resultados.xlsx
# Abas: KPIs_Core | KPIs_Operacionais | Metadados
```

### Gerar Excel comparativo entre tickers

```python
from src.output.excel_exporter import export_comparative

path = export_comparative(["VTRU3", "COGN3", "YDUQ3"], periodo="4T25")
print(f"Comparativo: {path}")
```

### Consultar histórico no banco

```python
from src.storage.repository import get_history, get_all_tickers

tickers = get_all_tickers()           # ['COGN3', 'VTRU3', ...]
history = get_history("VTRU3")        # lista de EarningsRecord ordenada por período
for record in history:
    print(f"{record.periodo}: EBITDA={record.ebitda}, Margem={record.ebitda_margem}%")
```

---

## Estrutura de Arquivos

```
earnings-poc-btg/
├── README.md
├── .env.example
├── pyproject.toml
├── config/
│   └── settings.py              ← variáveis de configuração
├── src/
│   ├── ingestion/
│   │   ├── pdf_parser.py        ← extração texto + tabelas (3 estratégias)
│   │   └── file_handler.py      ← hash, validação e registro de arquivos
│   ├── graph/
│   │   ├── state.py             ← EarningsState TypedDict + initial_state()
│   │   ├── workflow.py          ← composição e compilação do grafo LangGraph
│   │   ├── edges.py             ← conditional edges + routing
│   │   └── nodes/
│   │       ├── parser.py        ← Nó 1: PDF Parser
│   │       ├── extractor.py     ← Nó 2: LLM Extractor
│   │       ├── validator.py     ← Nó 3: Validator contábil
│   │       ├── reconciler.py    ← Nó 4: Auto-correção LLM
│   │       ├── human_review.py  ← Nó 5: Escalamento manual
│   │       └── excel_writer.py  ← Nó 6: DB + Excel
│   ├── schema/
│   │   ├── core_schema.py       ← Pydantic v2 models
│   │   ├── prompts.py           ← todos os prompts centralizados
│   │   └── validators.py        ← funções de validação contábil
│   ├── storage/
│   │   ├── database.py          ← SQLAlchemy engine + session
│   │   ├── models.py            ← ORM models (EarningsRecord, OperationalKPI, ExtractionLog)
│   │   └── repository.py        ← CRUD: save, get, history, upsert
│   └── output/
│       ├── excel_exporter.py    ← geração de Excel (4 abas)
│       └── excel_template.py    ← estilos, cores e formatação
├── tests/
│   ├── test_extractor.py
│   ├── test_validator.py
│   └── fixtures/                ← PDFs de teste (não commitados)
└── review_queue/                ← JSONs de revisão manual
```

---

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `OPENAI_API_KEY` | — | Chave da API OpenAI (obrigatória) |
| `DATABASE_URL` | `sqlite:///earnings.db` | URL do banco (SQLite para POC, Postgres para prod) |
| `LLM_MODEL` | `gpt-4o` | Modelo LLM a usar |
| `LLM_TEMPERATURE` | `0` | Temperatura do LLM (0 = determinístico) |
| `MAX_RETRIES` | `2` | Máximo de tentativas de reconciliação |
| `MIN_COMPLETUDE_CORE` | `0.8` | Completude mínima dos campos core (80%) |
| `REVIEW_QUEUE_PATH` | `review_queue/` | Diretório para artefatos de revisão manual |
| `OUTPUT_PATH` | `output/` | Diretório de output dos arquivos Excel |

---

## Executar Testes

```bash
pytest tests/ -v
```

---

## Roadmap

- **Fase 1 (POC)**: Upload manual → extração → Excel por empresa ✅
- **Fase 2**: Processamento em batch, dashboard de status das extrações
- **Fase 3**: Web scraping de sites de RI, ingestão automática por ticker

---

## Decisões de Design

### Por que DB como fonte de verdade?
O Excel é regenerado sob demanda a partir do banco, permitindo corrigir extrações retroativamente sem perder histórico e garantindo consistência entre reports.

### Por que agnóstico de setor?
O schema de `kpis_operacionais` é livre — o LLM extrai o que encontrar no documento. Não há hardcoding de métricas específicas de educação, bancos ou varejo.

### Por que SQLite na POC?
Zero configuração. Para produção, basta alterar `DATABASE_URL` para uma string de conexão PostgreSQL — o código não muda.

### Por que prompts versionados?
Cada prompt tem um sufixo `_V1` para facilitar A/B testing e rastreabilidade de mudanças de qualidade de extração.
