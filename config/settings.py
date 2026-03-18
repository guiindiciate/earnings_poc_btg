"""Settings module — suporta Amazon Bedrock como LLM provider."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM Provider ──────────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "bedrock")  # "bedrock" | "openai"

# Amazon Bedrock
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID: str = os.getenv(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-sonnet-20240229-v1:0"
    # Alternativas:
    # "anthropic.claude-3-haiku-20240307-v1:0"    <- mais rápido e barato
    # "anthropic.claude-3-5-sonnet-20241022-v2:0" <- mais capaz
)

# OpenAI (fallback opcional)
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── Pipeline ──────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///earnings.db")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))
MIN_COMPLETUDE_CORE: float = float(os.getenv("MIN_COMPLETUDE_CORE", "0.8"))
REVIEW_QUEUE_PATH: str = os.getenv("REVIEW_QUEUE_PATH", "review_queue/")
OUTPUT_PATH: str = os.getenv("OUTPUT_PATH", "output/")
