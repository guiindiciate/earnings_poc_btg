"""
Factory de LLM — retorna instância configurada de Bedrock ou OpenAI.
Todos os nós do grafo devem importar get_llm() daqui.

Uso:
    from src.llm_client import get_llm
    llm = get_llm()
    response = llm.invoke([HumanMessage(content="...")])
"""

from langchain_core.language_models import BaseChatModel


def get_llm() -> BaseChatModel:
    """
    Retorna o LLM configurado via variável de ambiente LLM_PROVIDER.

    Providers suportados:
    - "bedrock" (padrão): Amazon Bedrock com Claude 3 Sonnet
    - "openai": OpenAI GPT-4o (fallback)

    Raises:
        ValueError: se LLM_PROVIDER não for reconhecido
        ImportError: se dependência do provider não estiver instalada
    """
    from config.settings import LLM_PROVIDER

    if LLM_PROVIDER == "bedrock":
        return _get_bedrock_llm()
    elif LLM_PROVIDER == "openai":
        return _get_openai_llm()
    else:
        raise ValueError(
            f"LLM_PROVIDER inválido: '{LLM_PROVIDER}'. Use 'bedrock' ou 'openai'."
        )


def _get_bedrock_llm() -> BaseChatModel:
    """
    Instancia Claude 3 via Amazon Bedrock usando langchain-aws.

    Requer:
    - boto3 instalado e credenciais AWS configuradas
    - Modelo habilitado no Bedrock Console (Model Access)
    """
    try:
        from langchain_aws import ChatBedrock
    except ImportError:
        raise ImportError(
            "Dependências do Bedrock não encontradas. Instale com:\n"
            "  pip install langchain-aws boto3"
        )

    from config.settings import AWS_REGION, BEDROCK_MODEL_ID, LLM_TEMPERATURE

    return ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        model_kwargs={
            "temperature": LLM_TEMPERATURE,
            "max_tokens": 4096,
        },
    )


def _get_openai_llm() -> BaseChatModel:
    """
    Instancia GPT-4o via OpenAI (fallback/alternativa).

    Requer:
    - langchain-openai instalado
    - OPENAI_API_KEY configurada no .env
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ImportError(
            "Dependência OpenAI não encontrada. Instale com:\n"
            "  pip install langchain-openai"
        )

    from config.settings import LLM_TEMPERATURE, OPENAI_API_KEY, OPENAI_MODEL

    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY não configurada. Adicione ao .env:\n"
            "  OPENAI_API_KEY=sk-..."
        )

    return ChatOpenAI(
        model=OPENAI_MODEL,
        temperature=LLM_TEMPERATURE,
        api_key=OPENAI_API_KEY,
    )
