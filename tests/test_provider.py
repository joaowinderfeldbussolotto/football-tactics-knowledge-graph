"""Testes da troca de provedor (sem chamadas de rede)."""

import pytest

from football_graphrag.config import Settings
from football_graphrag.llm import provider


def make_settings(**overrides) -> Settings:
    base = {
        "llm_provider": "mistral",
        "llm_api_key": "k",
        "llm_model": "m",
        "llm_max_retries": 7,
        "embedder_api_key": "k",
        "embedder_model": "e",
        "_env_file": None,
    }
    return Settings(**{**base, **overrides})


@pytest.mark.parametrize(
    ("llm_provider", "expected"),
    [("mistral", "mistral:m"), ("anthropic", "anthropic:m"), ("gemini", "google-gla:m")],
)
def test_pydantic_ai_model_name_string(llm_provider, expected):
    assert provider.pydantic_ai_model_name(make_settings(llm_provider=llm_provider)) == expected


@pytest.mark.parametrize("llm_provider", ["mistral", "anthropic", "gemini"])
def test_pydantic_ai_model_carries_explicit_credentials(llm_provider):
    # o Model é construído com Provider explícito (chave do .env), sem depender
    # das env vars nativas de cada provedor (ANTHROPIC_API_KEY etc.)
    model = provider.pydantic_ai_model(make_settings(llm_provider=llm_provider))
    assert model.model_name == "m"


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


def test_cross_encoder_never_none():
    assert provider.graphiti_cross_encoder(make_settings(llm_provider="mistral")) is not None
    assert provider.graphiti_cross_encoder(make_settings(llm_provider="gemini")) is not None


# --- Rate limits: LLM_MAX_RETRIES chega aos SDKs por baixo (sem rede) ---


def test_anthropic_sdk_clients_carry_max_retries():
    settings = make_settings(llm_provider="anthropic")
    model = provider.pydantic_ai_model(settings)
    assert model.client.max_retries == 7
    graphiti_client = provider.graphiti_llm_client(settings)
    assert graphiti_client.client.max_retries == 7


def test_openai_compat_clients_carry_max_retries():
    settings = make_settings(llm_provider="mistral", embedder_provider="mistral")
    graphiti_client = provider.graphiti_llm_client(settings)
    assert graphiti_client.client.max_retries == 7
    embedder = provider.graphiti_embedder(settings)
    assert embedder.client.max_retries == 7
    reranker = provider.graphiti_cross_encoder(settings)
    assert reranker.client.max_retries == 7


def test_genai_clients_carry_retry_options():
    settings = make_settings(llm_provider="gemini", embedder_provider="gemini")
    for obj in (
        provider.graphiti_llm_client(settings),
        provider.graphiti_embedder(settings),
        provider.graphiti_cross_encoder(settings),
    ):
        retry = obj.client._api_client._http_options.retry_options
        assert retry is not None
        assert retry.attempts == 7 + 2
        assert 429 in retry.http_status_codes
        assert retry.max_delay >= 60  # cruza a janela de 1 min das cotas free-tier


def test_mistral_pydantic_ai_model_carries_retry_config():
    model = provider.pydantic_ai_model(make_settings(llm_provider="mistral"))
    retry = model.client.sdk_configuration.retry_config
    assert retry is not None and retry.strategy == "backoff"
