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
    settings = {**base, **overrides}
    # OpenRouterProvider valida "vendor/model"; "m" sozinho não é um nome válido
    # de modelo do OpenRouter (é o SDK, não regra do projeto).
    if settings["llm_provider"] == "openrouter" and "llm_model" not in overrides:
        settings["llm_model"] = "stealth/m"
    return Settings(**settings)


@pytest.mark.parametrize(
    ("llm_provider", "expected"),
    [
        ("mistral", "mistral:m"),
        ("anthropic", "anthropic:m"),
        ("gemini", "google-gla:m"),
        ("openrouter", "openrouter:stealth/m"),
    ],
)
def test_pydantic_ai_model_name_string(llm_provider, expected):
    assert provider.pydantic_ai_model_name(make_settings(llm_provider=llm_provider)) == expected


@pytest.mark.parametrize("llm_provider", ["mistral", "anthropic", "gemini"])
def test_pydantic_ai_model_carries_explicit_credentials(llm_provider):
    # o Model é construído com Provider explícito (chave do .env), sem depender
    # das env vars nativas de cada provedor (ANTHROPIC_API_KEY etc.)
    model = provider.pydantic_ai_model(make_settings(llm_provider=llm_provider))
    assert model.model_name == "m"


def test_pydantic_ai_model_carries_explicit_credentials_openrouter():
    # OpenRouter exige nome "vendor/model" (validado pelo próprio SDK) — testado
    # à parte dos demais provedores, que aceitam qualquer string de modelo.
    model = provider.pydantic_ai_model(make_settings(llm_provider="openrouter"))
    assert model.model_name == "stealth/m"


def test_graphiti_client_mistral_uses_openai_generic_with_base_url():
    client = provider.graphiti_llm_client(make_settings(llm_provider="mistral"))
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

    assert isinstance(client, OpenAIGenericClient)
    assert client.config.base_url == provider.MISTRAL_BASE_URL


def test_graphiti_client_openrouter_uses_openai_generic_with_base_url():
    client = provider.graphiti_llm_client(make_settings(llm_provider="openrouter"))
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

    assert isinstance(client, OpenAIGenericClient)
    assert client.config.base_url == provider.OPENROUTER_BASE_URL


def test_pydantic_ai_model_openrouter_is_openai_chat_model_with_base_url():
    from pydantic_ai.models.openai import OpenAIChatModel

    model = provider.pydantic_ai_model(make_settings(llm_provider="openrouter"))
    assert isinstance(model, OpenAIChatModel)
    assert str(model.client.base_url).rstrip("/") == provider.OPENROUTER_BASE_URL


def test_cross_encoder_openrouter_falls_back_to_openai_reranker_with_base_url():
    """Sem embedder gemini, o reranker do OpenRouter usa o endpoint compatível
    (não o endpoint OpenAI real, que é o bug que este teste evita reintroduzir)."""
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

    settings = make_settings(llm_provider="openrouter", embedder_provider="")
    ce = provider.graphiti_cross_encoder(settings)
    assert isinstance(ce, OpenAIRerankerClient)
    assert ce.config.base_url == provider.OPENROUTER_BASE_URL


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


# ---------------------------------------------------------------------------
# Teto de tokens e esforço de raciocínio (LLM_MAX_TOKENS / LLM_REASONING_EFFORT)
# ---------------------------------------------------------------------------

def test_model_settings_default_preserva_o_comportamento_antigo():
    """Antes era a constante {"max_tokens": 16000}. Sem tocar no .env, o mesmo."""
    assert provider.pydantic_ai_model_settings(make_settings()) == {"max_tokens": 16000}


def test_model_settings_max_tokens_vem_do_env():
    assert provider.pydantic_ai_model_settings(make_settings(llm_max_tokens=32000)) == {
        "max_tokens": 32000
    }


def test_reasoning_effort_vai_como_extra_body_no_openrouter():
    s = provider.pydantic_ai_model_settings(
        make_settings(llm_provider="openrouter", llm_reasoning_effort="low")
    )
    assert s["extra_body"] == {"reasoning": {"effort": "low"}}
    assert s["max_tokens"] == 16000


@pytest.mark.parametrize("llm_provider", ["mistral", "anthropic", "gemini"])
def test_reasoning_effort_em_outro_provedor_e_ignorado_com_aviso(llm_provider, caplog):
    """Ignorar em silêncio faria o botão parecer funcionar."""
    with caplog.at_level("WARNING"):
        s = provider.pydantic_ai_model_settings(
            make_settings(llm_provider=llm_provider, llm_reasoning_effort="low")
        )
    assert "extra_body" not in s
    assert "LLM_REASONING_EFFORT" in caplog.text


def test_reasoning_effort_valor_invalido_e_rejeitado_na_configuracao():
    with pytest.raises(Exception):
        make_settings(llm_provider="openrouter", llm_reasoning_effort="muito-alto")


def test_o_agente_recebe_as_settings_montadas_pelo_provider(monkeypatch):
    """Garante a fiação: um .env com LLM_MAX_TOKENS tem que chegar ao Agent."""
    from football_graphrag.api import agents

    chegou = {}

    class AgenteFalso:
        def __init__(self, *a, **kw):
            chegou.update(kw)

        def system_prompt(self, fn):
            return fn

        def tool(self, fn):
            return fn

    monkeypatch.setattr(agents, "Agent", AgenteFalso)
    monkeypatch.setattr(agents, "pydantic_ai_model", lambda s: "modelo")
    monkeypatch.setattr(
        agents, "get_settings",
        lambda: make_settings(llm_provider="openrouter", llm_max_tokens=24000, llm_reasoning_effort="low"),
    )
    agents.qa_agent.cache_clear()
    try:
        agents.qa_agent()
    finally:
        agents.qa_agent.cache_clear()
    assert chegou["model_settings"] == {
        "max_tokens": 24000,
        "extra_body": {"reasoning": {"effort": "low"}},
    }
