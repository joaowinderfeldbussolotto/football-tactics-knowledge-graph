import pytest
from graphiti_core.llm_client.anthropic_client import AnthropicClient
from graphiti_core.llm_client.gemini_client import GeminiClient
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel

from football_graphrag.config import Settings
from football_graphrag.llm.provider import (
    build_graphiti_llm_client,
    build_pydantic_ai_model,
    pydantic_ai_model_string,
)


def _settings(**overrides) -> Settings:
    defaults = dict(llm_api_key="sk-test", embedder_api_key="sk-test")
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.parametrize(
    "provider,expected_client,expected_model",
    [
        ("anthropic", AnthropicClient, AnthropicModel),
        ("openai", OpenAIClient, OpenAIChatModel),
        ("gemini", GeminiClient, GoogleModel),
    ],
)
def test_provider_selection_builds_matching_classes(provider, expected_client, expected_model):
    settings = _settings(llm_provider=provider)

    client = build_graphiti_llm_client(settings)
    assert isinstance(client, expected_client)

    model = build_pydantic_ai_model(settings)
    assert isinstance(model, expected_model)


def test_openai_compatible_requires_base_url():
    settings = _settings(llm_provider="openai_compatible", llm_base_url=None)
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        build_graphiti_llm_client(settings)
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        build_pydantic_ai_model(settings)


def test_openai_compatible_with_base_url_uses_generic_client():
    settings = _settings(llm_provider="openai_compatible", llm_base_url="https://api.deepseek.com")
    client = build_graphiti_llm_client(settings)
    assert isinstance(client, OpenAIGenericClient)
    model = build_pydantic_ai_model(settings)
    assert isinstance(model, OpenAIChatModel)


def test_pydantic_ai_model_string_maps_gemini_to_google_prefix():
    settings = _settings(llm_provider="gemini", llm_model="gemini-2.0-flash")
    assert pydantic_ai_model_string(settings) == "google:gemini-2.0-flash"


def test_pydantic_ai_model_string_passthrough_for_anthropic():
    settings = _settings(llm_provider="anthropic", llm_model="claude-sonnet-5")
    assert pydantic_ai_model_string(settings) == "anthropic:claude-sonnet-5"
