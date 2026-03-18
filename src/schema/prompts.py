"""Centralised LLM prompt templates for the earnings extraction pipeline.

Every prompt is versioned (``_V1`` suffix) to make iterative improvement
traceable.  Import the un-versioned aliases (e.g. :data:`CORE_EXTRACTION_PROMPT`)
for normal use; pin to a specific version only when reproducibility matters.
"""

# ── Core financial metrics extraction ─────────────────────────────────────────

CORE_EXTRACTION_PROMPT_V1 = """\
Você é um analista financeiro especializado em extração de dados de earnings releases brasileiros.

Extraia EXATAMENTE as métricas financeiras do documento fornecido.
Retorne APENAS JSON válido, sem texto adicional, sem markdown, sem explicações.

REGRAS CRÍTICAS:
- Use null se a métrica não estiver disponível no documento
- Valores monetários em R$ milhões, salvo indicação contrária
- Para variações percentuais, use número decimal (ex: 5.3 para 5,3%)
- Se houver valores "ajustado" e "contábil/societário", priorize "ajustado"
- Para bancos: use Margem Financeira Líquida (NII) como receita_liquida quando aplicável
- Para empresas sem EBITDA explícito: calcule se possível (EBIT + D&A)
- Período de referência: {periodo}
- Ticker: {ticker}

SCHEMA OBRIGATÓRIO (retorne exatamente esta estrutura):
{schema_json}

DOCUMENTO:
{documento}
"""

CORE_EXTRACTION_PROMPT = CORE_EXTRACTION_PROMPT_V1

# ── Operational KPI extraction ─────────────────────────────────────────────────

OPERATIONAL_KPI_PROMPT_V1 = """\
Você é um analista financeiro especializado em KPIs operacionais.

Além das métricas financeiras padrão, identifique e extraia TODOS os KPIs operacionais
relevantes presentes neste documento de earnings release.

Exemplos (não limitado a estes):
- Educação: base_alunos, ticket_medio, evasao, captacao, num_polos
- Bancos: nii, inadimplencia_90d, basileia, numero_clientes, agencias
- Varejo: sssg, gmv, total_lojas, estoque_dias, ticket_medio
- Telecom: arpu, churn_rate, num_assinantes
- Mineração: volume_producao, custo_caixa, teor_medio

Retorne JSON no formato:
{{
  "nome_do_kpi_snake_case": {{
    "valor": <número>,
    "unidade": "<string: ex: 'mil alunos', 'R$ bilhões', '%', 'unidades'>",
    "var_aa": <número ou null>
  }}
}}

Retorne APENAS JSON válido, sem texto adicional.
Período: {periodo}
Ticker: {ticker}

DOCUMENTO:
{documento}
"""

OPERATIONAL_KPI_PROMPT = OPERATIONAL_KPI_PROMPT_V1

# ── Reconciler (auto-correction) ──────────────────────────────────────────────

RECONCILER_PROMPT_V1 = """\
Você é um analista financeiro realizando correção de dados extraídos.

Os seguintes erros de validação foram identificados na extração:
{erros}

Dados extraídos anteriormente (JSON):
{dados_anteriores}

Trecho relevante do documento original para referência:
{trecho_relevante}

INSTRUÇÕES:
1. Corrija APENAS os campos que apresentaram erro
2. Mantenha exatamente o mesmo schema JSON
3. Após o JSON corrigido, adicione uma seção "## Correções realizadas:" explicando cada mudança

Retorne o JSON completo corrigido primeiro, depois as explicações.
"""

RECONCILER_PROMPT = RECONCILER_PROMPT_V1
