"""Testes da troca de provedor (sem chamadas de rede)."""

import pytest

from football_graphrag.config import Settings
from football_graphrag.llm import provider


def make_settings(**overrides) -> Settings:
    base = {
        "llm_provider": "mistral",
        "llm_api_key": "k",
        "llm_model": "m",
        "embedder_api_key": "k",
        "embedder_model": "e",
        "_env_file": None,
    }
    return Settings(**{**base, **overrides})


@pytest.mark.parametrize(
    ("llm_provider", "expected"),
    [("mistral", "mistral:m"), ("anthropic", "anthropic:m"), ("gemini", "google-gla:m")],
)
def test_pydantic_ai_model_string(llm_provider, expected):
    assert provider.pydantic_ai_model(make_settings(llm_provider=llm_provider)) == expected


def test_graphiti_client_mistral_uses_openai_generic_with_base_url():
    client = provider.graphiti_llm_client(make_settings(llm_provider="mistral"))
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

    assert isinstance(client, OpenAIGenericClient)


def test_graphiti_client_anthropic():
    client = provider.graphiti_llm_client(make_settings(llm_provider="anthropic"))
    from graphiti_core.llm_client.anthropic_client import AnthropicClient

    assert isinstance(client, AnthropicClient)


def test_graphiti_client_gemini():
    client = provider.graphiti_llm_client(make_settings(llm_provider="gemini"))
    from graphiti_core.llm_client.gemini_client import GeminiClient

    assert isinstance(client, GeminiClient)


def test_cross_encoder_only_for_gemini():
    assert provider.graphiti_cross_encoder(make_settings(llm_provider="mistral")) is None
    assert provider.graphiti_cross_encoder(make_settings(llm_provider="gemini")) is not None
