"""Settings module — loads configuration from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///earnings.db")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))
MIN_COMPLETUDE_CORE: float = float(os.getenv("MIN_COMPLETUDE_CORE", "0.8"))
REVIEW_QUEUE_PATH: str = os.getenv("REVIEW_QUEUE_PATH", "review_queue/")
OUTPUT_PATH: str = os.getenv("OUTPUT_PATH", "output/")
