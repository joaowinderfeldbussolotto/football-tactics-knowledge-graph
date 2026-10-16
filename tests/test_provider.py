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


def test_pydantic_ai_model_openrouter_is_openai_chat_model_with_base_url():
    from pydantic_ai.models.openai import OpenAIChatModel

    model = provider.pydantic_ai_model(make_settings(llm_provider="openrouter"))
    assert isinstance(model, OpenAIChatModel)
    assert str(model.client.base_url).rstrip("/") == provider.OPENROUTER_BASE_URL


# --- Rate limits: LLM_MAX_RETRIES chega aos SDKs por baixo (sem rede) ---


def test_anthropic_sdk_clients_carry_max_retries():
    model = provider.pydantic_ai_model(make_settings(llm_provider="anthropic"))
    assert model.client.max_retries == 7


def test_openrouter_sdk_client_carries_max_retries():
    model = provider.pydantic_ai_model(make_settings(llm_provider="openrouter"))
    assert model.client.max_retries == 7


def test_genai_retry_options():
    retry = provider._genai_retry_options(make_settings(llm_provider="gemini"))
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


def test_provider_order_vai_como_extra_body_sem_fallback_no_openrouter():
    s = provider.pydantic_ai_model_settings(
        make_settings(llm_provider="openrouter", llm_provider_order="baidu/fp8")
    )
    assert s["extra_body"] == {"provider": {"order": ["baidu/fp8"], "allow_fallbacks": False}}


def test_provider_order_aceita_varios_e_ignora_espacos():
    s = provider.pydantic_ai_model_settings(
        make_settings(llm_provider="openrouter", llm_provider_order=" baidu/fp8 , deepseek ,")
    )
    assert s["extra_body"]["provider"]["order"] == ["baidu/fp8", "deepseek"]


def test_provider_order_vazio_nao_envia_nada():
    s = provider.pydantic_ai_model_settings(make_settings(llm_provider="openrouter"))
    assert "extra_body" not in s


def test_provider_order_convive_com_reasoning_effort():
    s = provider.pydantic_ai_model_settings(
        make_settings(llm_provider="openrouter", llm_reasoning_effort="low", llm_provider_order="baidu/fp8")
    )
    assert set(s["extra_body"]) == {"reasoning", "provider"}


@pytest.mark.parametrize("llm_provider", ["mistral", "anthropic", "gemini"])
def test_provider_order_em_outro_provedor_e_ignorado_com_aviso(llm_provider, caplog):
    with caplog.at_level("WARNING"):
        s = provider.pydantic_ai_model_settings(
            make_settings(llm_provider=llm_provider, llm_provider_order="baidu/fp8")
        )
    assert "extra_body" not in s
    assert "LLM_PROVIDER_ORDER" in caplog.text


# --------------------------------------------------------------------------- Amazon Bedrock

def bedrock_settings(**overrides) -> Settings:
    return make_settings(llm_provider="bedrock", llm_model="openai.gpt-oss-120b-1:0",
                         llm_aws_region="us-east-1", **overrides)


def test_bedrock_usa_a_api_converse_com_o_id_do_modelo():
    pytest.importorskip("boto3")
    from pydantic_ai.models.bedrock import BedrockConverseModel

    model = provider.pydantic_ai_model(bedrock_settings())
    assert isinstance(model, BedrockConverseModel)
    assert model.model_name == "openai.gpt-oss-120b-1:0"
    assert provider.pydantic_ai_model_name(bedrock_settings()) == "bedrock:openai.gpt-oss-120b-1:0"


def test_bedrock_ignora_o_provedor_fixo_do_openrouter_com_aviso(caplog):
    with caplog.at_level("WARNING"):
        s = provider.pydantic_ai_model_settings(bedrock_settings(llm_provider_order="baidu/fp8"))
    assert "extra_body" not in s
    assert "LLM_PROVIDER_ORDER" in caplog.text


def test_bedrock_envia_a_requisicao_converse_com_ferramenta_e_limite_de_saida():
    """Offline: botocore's Stubber answers, so the request the SDK would send can be read."""
    boto3 = pytest.importorskip("boto3")
    from botocore.stub import Stubber
    from pydantic_ai import Agent
    from pydantic_ai.models.bedrock import BedrockConverseModel
    from pydantic_ai.providers.bedrock import BedrockProvider

    client = boto3.client("bedrock-runtime", region_name="us-east-1",
                          aws_access_key_id="x", aws_secret_access_key="y")
    reply = {"output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
             "stopReason": "end_turn", "usage": {"inputTokens": 3, "outputTokens": 1, "totalTokens": 4},
             "metrics": {"latencyMs": 1}}
    seen = {}
    with Stubber(client) as stub:
        stub.add_response("converse", reply)
        client.meta.events.register("provide-client-params.bedrock-runtime.Converse",
                                    lambda params, **kw: seen.update(params))
        agent = Agent(BedrockConverseModel("openai.gpt-oss-120b-1:0", provider=BedrockProvider(bedrock_client=client)),
                      model_settings=provider.pydantic_ai_model_settings(bedrock_settings(llm_max_tokens=1234)))
        import asyncio
        result = asyncio.run(agent.run("oi"))
    assert result.output == "ok"
    assert seen["modelId"] == "openai.gpt-oss-120b-1:0"
    assert seen["inferenceConfig"]["maxTokens"] == 1234


def test_bedrock_traduz_o_esforco_de_raciocinio_para_thinking_com_temperatura_1():
    s = provider.pydantic_ai_model_settings(bedrock_settings(llm_reasoning_effort="medium"))
    assert s["thinking"] == "medium" and s["temperature"] == 1.0
    assert "extra_body" not in s


def test_bedrock_esforco_none_desliga_o_raciocinio_sem_mudar_a_temperatura():
    s = provider.pydantic_ai_model_settings(bedrock_settings(llm_reasoning_effort="none"))
    assert s["thinking"] is False and "temperature" not in s


def test_bedrock_sem_esforco_nao_envia_thinking():
    s = provider.pydantic_ai_model_settings(bedrock_settings())
    assert "thinking" not in s and "temperature" not in s
