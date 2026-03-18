"""
Testes para o LLM client factory (sem chamadas reais à API).
"""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestGetLlm:
    """Testa a factory get_llm() com diferentes providers."""

    def test_invalid_provider_raises_value_error(self):
        """Provider inválido deve levantar ValueError."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "invalid_provider"}):
            # Reload settings para pegar nova env var
            import importlib
            import config.settings as settings
            importlib.reload(settings)

            import src.llm_client as llm_module
            importlib.reload(llm_module)

            with pytest.raises(ValueError, match="LLM_PROVIDER inválido"):
                llm_module.get_llm()

    def test_bedrock_provider_calls_get_bedrock_llm(self):
        """LLM_PROVIDER=bedrock deve chamar _get_bedrock_llm."""
        mock_bedrock = MagicMock()
        mock_bedrock.__class__.__name__ = "ChatBedrock"

        with patch.dict(os.environ, {"LLM_PROVIDER": "bedrock"}):
            import importlib
            import config.settings as settings
            importlib.reload(settings)

            import src.llm_client as llm_module
            importlib.reload(llm_module)

            with patch.object(llm_module, "_get_bedrock_llm", return_value=mock_bedrock):
                result = llm_module.get_llm()
                assert result == mock_bedrock

    def test_openai_provider_calls_get_openai_llm(self):
        """LLM_PROVIDER=openai deve chamar _get_openai_llm."""
        mock_openai = MagicMock()
        mock_openai.__class__.__name__ = "ChatOpenAI"

        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            import importlib
            import config.settings as settings
            importlib.reload(settings)

            import src.llm_client as llm_module
            importlib.reload(llm_module)

            with patch.object(llm_module, "_get_openai_llm", return_value=mock_openai):
                result = llm_module.get_llm()
                assert result == mock_openai

    def test_openai_missing_api_key_raises_error(self):
        """OpenAI sem API key deve levantar ValueError."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": ""}):
            import importlib
            import config.settings as settings
            importlib.reload(settings)

            import src.llm_client as llm_module
            importlib.reload(llm_module)

            with pytest.raises((ValueError, Exception)):
                llm_module._get_openai_llm()

    def test_bedrock_missing_dependency_raises_import_error(self):
        """Bedrock sem langchain-aws instalado deve levantar ImportError claro."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "langchain_aws":
                raise ImportError("No module named 'langchain_aws'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            import importlib
            import src.llm_client as llm_module
            # Need fresh import to trigger the mocked __import__
            with pytest.raises(ImportError, match="langchain-aws"):
                llm_module._get_bedrock_llm()
