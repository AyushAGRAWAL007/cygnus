from .auth_support import sign_in_demo
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI
from pydantic import SecretStr

from app import main
from app.ai import nvidia
from app.config import Settings, get_settings


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "cygnus-ai.db"))
    monkeypatch.setattr(main.settings, "app_env", "development")
    with TestClient(main.app) as test_client:
        sign_in_demo(test_client)
        yield test_client


def configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        nvidia_api_key=SecretStr("unit-test-key-not-a-real-credential"),
        nvidia_model="nvidia/nemotron-3.5-lightning-30b-a3b",
        nvidia_base_url="https://integrate.api.nvidia.com/v1",
    )


def test_nvidia_configuration_defaults_and_backend_env_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)
    monkeypatch.delenv("NVIDIA_BASE_URL", raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.nvidia_configured is False
    assert defaults.nvidia_model == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert defaults.nvidia_base_url == "https://integrate.api.nvidia.com/v1"

    root_env = tmp_path / "root.env"
    backend_env = tmp_path / "backend.env"
    root_env.write_text(
        "NVIDIA_API_KEY=root-fake-credential\nNVIDIA_MODEL=root-fake-model\n",
        encoding="utf-8",
    )
    backend_env.write_text(
        "NVIDIA_API_KEY=backend-fake-credential\nNVIDIA_MODEL=backend-fake-model\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=(root_env, backend_env))

    assert settings.nvidia_configured is True
    assert settings.nvidia_api_key is not None
    assert settings.nvidia_api_key.get_secret_value() == "backend-fake-credential"
    assert settings.nvidia_model == "backend-fake-model"

    monkeypatch.setenv("NVIDIA_MODEL", "process-fake-model")
    process_settings = Settings(_env_file=(root_env, backend_env))
    assert process_settings.nvidia_model == "process-fake-model"


def mocked_openai(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return OpenAI(
        api_key="mock-key",
        base_url="https://integrate.api.nvidia.com/v1",
        timeout=1.0,
        max_retries=0,
        http_client=http_client,
    )


def completion_response(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": 1,
            "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def test_missing_nvidia_configuration_is_controlled(monkeypatch):
    monkeypatch.setattr(nvidia, "get_settings", lambda: Settings(_env_file=None))

    with pytest.raises(nvidia.AssistantError) as error:
        nvidia.answer("Explain this return", nvidia.AssistantContext(("No record selected.",)))

    assert error.value.status_code == 503
    assert error.value.code == "ai_unavailable"
    assert "NVIDIA_API_KEY" not in error.value.message


def test_whitespace_nvidia_key_is_treated_as_missing(monkeypatch):
    settings = Settings(_env_file=None, nvidia_api_key=SecretStr("   "))
    monkeypatch.setattr(nvidia, "get_settings", lambda: settings)

    with pytest.raises(nvidia.AssistantError) as error:
        nvidia.answer("Explain this return", nvidia.AssistantContext(("No record selected.",)))

    assert settings.nvidia_configured is False
    assert error.value.code == "ai_unavailable"


@pytest.mark.parametrize(
    ("model", "base_url"),
    [
        ("", "https://integrate.api.nvidia.com/v1"),
        ("   ", "https://integrate.api.nvidia.com/v1"),
        ("model name", "https://integrate.api.nvidia.com/v1"),
        ("model-name", ""),
        ("model-name", "   "),
        ("model-name", "not-a-valid-url"),
        ("model-name", "https://integrate.api.nvidia.com:99999/v1"),
    ],
)
def test_invalid_client_configuration_is_sanitized(model, base_url):
    settings = configured_settings()
    settings.nvidia_model = model
    settings.nvidia_base_url = base_url
    with pytest.raises(nvidia.AssistantError) as error:
        nvidia.answer("Explain this return", nvidia.AssistantContext(("No record selected.",)), settings=settings)
    assert error.value.code == "ai_unavailable"
    assert not base_url.strip() or base_url.strip() not in error.value.message
    assert not model.strip() or model.strip() not in error.value.message


def test_successful_chat_uses_configured_model_and_bounded_openai_parameters():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return completion_response("The backend says this return case is awaiting pickup.")

    client = mocked_openai(handler)
    try:
        result = nvidia.answer(
            "What is the next permitted step?",
            nvidia.AssistantContext(("Case case-test is pickup_scheduled.",), case_id="case-test"),
            settings=configured_settings(),
            client=client,
        )
    finally:
        client.close()

    assert result["answer"] == "The backend says this return case is awaiting pickup."
    assert result["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert result["data_source"] == "simulated"
    assert captured["path"] == "/v1/chat/completions"
    assert captured["authorization"] == "Bearer mock-key"
    assert captured["body"]["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert captured["body"]["temperature"] == 1.0
    assert captured["body"]["top_p"] == 0.95
    assert captured["body"]["max_tokens"] == nvidia.MAX_OUTPUT_TOKENS
    assert captured["body"]["chat_template_kwargs"]["enable_thinking"] is False


def test_model_whitespace_is_normalized_before_request():
    settings = configured_settings()
    settings.nvidia_model = "  nvidia/nemotron-3.5-lightning-30b-a3b  "
    captured = {}

    def handler(request):
        captured["model"] = json.loads(request.content)["model"]
        return completion_response("Model selection is normalized.")

    client = mocked_openai(handler)
    try:
        result = nvidia.answer("Explain this case", nvidia.AssistantContext(("Demo fact",)), settings=settings, client=client)
    finally:
        client.close()

    assert captured["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert result["model"] == captured["model"]


@pytest.mark.parametrize(
    ("status", "expected_code", "expected_status"),
    [
        (401, "ai_authentication_failed", 502),
        (403, "ai_access_denied", 502),
        (429, "ai_rate_limited", 503),
        (503, "ai_provider_error", 502),
    ],
)
def test_provider_http_failures_are_sanitized(status, expected_code, expected_status):
    def handler(_request):
        return httpx.Response(status, json={"error": {"message": "provider detail must not escape"}})

    client = mocked_openai(handler)
    try:
        with pytest.raises(nvidia.AssistantError) as error:
            nvidia.answer("Summarize this case", nvidia.AssistantContext(("Case is simulated.",)), settings=configured_settings(), client=client)
    finally:
        client.close()

    assert error.value.code == expected_code
    assert error.value.status_code == expected_status
    assert "provider detail" not in error.value.message
    assert "mock-key" not in error.value.message


def test_rate_limit_includes_only_sanitized_numeric_retry_after():
    def handler(_request):
        return httpx.Response(
            429,
            headers={"Retry-After": "17", "X-Provider-Private": "do-not-return"},
            json={"error": {"message": "private provider message"}},
        )

    client = mocked_openai(handler)
    try:
        with pytest.raises(nvidia.AssistantError) as error:
            nvidia.answer("Explain the event", nvidia.AssistantContext(("Demo fact",)), settings=configured_settings(), client=client)
    finally:
        client.close()

    assert error.value.code == "ai_rate_limited"
    assert "17 seconds" in error.value.message
    assert "private" not in error.value.message


def test_rate_limit_http_date_retry_after_is_summarized_safely():
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    client = mocked_openai(lambda _request: httpx.Response(429, headers={"Retry-After": format_datetime(retry_at)}, json={"error": {"message": "private"}}))
    try:
        with pytest.raises(nvidia.AssistantError) as error:
            nvidia.answer("Explain the event", nvidia.AssistantContext(("Demo fact",)), settings=configured_settings(), client=client)
    finally:
        client.close()
    assert error.value.code == "ai_rate_limited"
    assert "seconds" in error.value.message
    assert "private" not in error.value.message


@pytest.mark.parametrize("retry_after", ["not-a-date", "0", "86401", "999999"])
def test_invalid_or_over_bound_retry_after_uses_generic_rate_limit_message(retry_after):
    client = mocked_openai(lambda _request: httpx.Response(429, headers={"Retry-After": retry_after}, json={"error": {"message": "private provider message"}}))
    try:
        with pytest.raises(nvidia.AssistantError) as error:
            nvidia.answer("Explain the event", nvidia.AssistantContext(("Demo fact",)), settings=configured_settings(), client=client)
    finally:
        client.close()
    assert error.value.code == "ai_rate_limited"
    assert error.value.message == "NVIDIA inference is rate limited. Please try again later."
    assert "private" not in error.value.message


def test_unexpected_provider_exception_is_sanitized():
    class UnexpectedClient:
        class Chat:
            class Completions:
                @staticmethod
                def create(**_kwargs):
                    raise RuntimeError("unexpected exception containing fake-key")

            completions = Completions()

        chat = Chat()

    with pytest.raises(nvidia.AssistantError) as error:
        nvidia.answer(
            "Explain the event",
            nvidia.AssistantContext(("Demo fact",)),
            settings=configured_settings(),
            client=UnexpectedClient(),
        )

    assert error.value.code == "ai_internal_error"
    assert error.value.status_code == 502
    assert "fake-key" not in error.value.message


def test_timeout_and_connection_outage_are_controlled():
    def timeout(_request):
        raise httpx.ReadTimeout("sensitive transport details")

    timeout_client = mocked_openai(timeout)
    try:
        with pytest.raises(nvidia.AssistantError) as timeout_error:
            nvidia.answer("Explain the event", nvidia.AssistantContext(("A simulated event was recorded.",)), settings=configured_settings(), client=timeout_client)
    finally:
        timeout_client.close()
    assert timeout_error.value.code == "ai_timeout"
    assert timeout_error.value.status_code == 504
    assert "sensitive" not in timeout_error.value.message

    def outage(_request):
        raise httpx.ConnectError("private connection detail")

    outage_client = mocked_openai(outage)
    try:
        with pytest.raises(nvidia.AssistantError) as outage_error:
            nvidia.answer("Explain the event", nvidia.AssistantContext(("A simulated event was recorded.",)), settings=configured_settings(), client=outage_client)
    finally:
        outage_client.close()
    assert outage_error.value.code == "ai_unavailable"
    assert outage_error.value.status_code == 502
    assert "private connection" not in outage_error.value.message


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_model_response_is_not_replaced_with_fabricated_answer(text):
    client = mocked_openai(lambda _request: completion_response(text))
    try:
        with pytest.raises(nvidia.AssistantError) as error:
            nvidia.answer("What happened?", nvidia.AssistantContext(("Pickup is scheduled.",)), settings=configured_settings(), client=client)
    finally:
        client.close()
    assert error.value.code == "ai_invalid_response"
    assert error.value.status_code == 502


def test_missing_choices_are_treated_as_an_invalid_response():
    client = mocked_openai(lambda _request: httpx.Response(200, json={"choices": []}))
    try:
        with pytest.raises(nvidia.AssistantError) as error:
            nvidia.answer("What happened?", nvidia.AssistantContext(("A simulated event was recorded.",)), settings=configured_settings(), client=client)
    finally:
        client.close()
    assert error.value.code == "ai_invalid_response"


def test_invalid_json_provider_response_is_sanitized():
    client = mocked_openai(lambda _request: httpx.Response(200, text="{not valid json: provider details"))
    try:
        with pytest.raises(nvidia.AssistantError) as error:
            nvidia.answer("What happened?", nvidia.AssistantContext(("A simulated event was recorded.",)), settings=configured_settings(), client=client)
    finally:
        client.close()
    assert error.value.status_code == 502
    assert error.value.code == "ai_invalid_response"
    assert "provider details" not in error.value.message


def test_oversized_model_response_is_rejected():
    client = mocked_openai(lambda _request: completion_response("x" * (nvidia.MAX_RESPONSE_CHARS + 1)))
    try:
        with pytest.raises(nvidia.AssistantError) as error:
            nvidia.answer("What happened?", nvidia.AssistantContext(("A simulated event was recorded.",)), settings=configured_settings(), client=client)
    finally:
        client.close()
    assert error.value.code == "ai_invalid_response"
    assert error.value.status_code == 502


def test_order_context_is_retrieved_from_backend_and_contains_policy_result(api_client):
    context = nvidia.build_context(order_id="demo-order-004")

    assert context.order_id == "demo-order-004"
    assert context.eligibility is False
    assert any("Clearance headphones" in fact for fact in context.facts)
    assert any("final sale" in fact for fact in context.facts)
    assert any("not eligible" in fact for fact in context.facts)


def test_case_context_contains_recorded_status_without_customer_availability(api_client):
    context = nvidia.build_context(case_id="case-demo-001")

    assert context.case_id == "case-demo-001"
    assert context.order_id == "demo-order-001"
    assert any("pickup_scheduled" in fact for fact in context.facts)
    assert not any("availability" in fact.lower() for fact in context.facts)


@pytest.mark.parametrize(
    ("order_id", "model_text", "expected_fragment"),
    [
        ("demo-order-004", "This item is eligible for a return.", "not eligible"),
        ("demo-order-002", "Your refund has been credited to your bank.", "bank credit is not verified"),
    ],
)
def test_model_cannot_override_policy_or_claim_bank_credit(api_client, order_id, model_text, expected_fragment):
    context = nvidia.build_context(order_id=order_id)
    client = mocked_openai(lambda _request: completion_response(model_text))
    try:
        result = nvidia.answer("Please summarize this order.", context, settings=configured_settings(), client=client)
    finally:
        client.close()

    assert expected_fragment in result["answer"].lower()
    assert model_text not in result["answer"]


def test_model_cannot_claim_unresolved_case_is_resolved(api_client):
    context = nvidia.build_context(case_id="case-demo-001")
    assert context.resolved is False
    client = mocked_openai(lambda _request: completion_response("This return case is resolved."))
    try:
        result = nvidia.answer("Is this return case done?", context, settings=configured_settings(), client=client)
    finally:
        client.close()
    assert "cannot advance or resolve" in result["answer"].lower()


def test_chat_validation_and_unknown_record_errors(api_client, monkeypatch):
    oversized = api_client.post("/api/ai/chat", json={"message": "x" * 2001})
    blank = api_client.post("/api/ai/chat", json={"message": "   "})
    both_contexts = api_client.post("/api/ai/chat", json={"message": "help", "case_id": "case-demo-001", "order_id": "demo-order-001"})
    client_facts = api_client.post("/api/ai/chat", json={"message": "help", "facts": ["this item is eligible"]})
    unknown_case = api_client.post("/api/ai/chat", json={"message": "help", "case_id": "missing-case"})

    assert oversized.status_code == 422
    assert blank.status_code == 422
    assert both_contexts.status_code == 422
    assert client_facts.status_code == 422
    assert unknown_case.status_code == 404


def test_chat_route_returns_model_answer_and_backend_facts(api_client, monkeypatch):
    provider = mocked_openai(lambda _request: completion_response("The backend marks this item not eligible because it is final sale."))
    monkeypatch.setattr(nvidia, "_client", lambda _settings: provider)
    response = api_client.post(
        "/api/ai/chat",
        json={"message": "Why can't I return this?", "order_id": "demo-order-004"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("The backend marks")
    assert body["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert body["data_source"] == "simulated"
    assert any("final sale" in fact for fact in body["facts"])


def test_chat_route_reports_unconfigured_provider_without_secret(api_client, monkeypatch):
    monkeypatch.setattr(nvidia, "get_settings", lambda: Settings(_env_file=None))
    response = api_client.post("/api/ai/chat", json={"message": "Explain the demo policy."})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ai_unavailable"
    assert "NVIDIA_API_KEY" not in response.text


def test_chat_route_sanitizes_provider_error_body(api_client, monkeypatch):
    provider = mocked_openai(
        lambda _request: httpx.Response(
            503,
            json={"error": {"message": "private provider body fake-key"}},
        )
    )
    monkeypatch.setattr(nvidia, "_client", lambda _settings: provider)
    response = api_client.post("/api/ai/chat", json={"message": "Explain the demo policy."})

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ai_provider_error"
    assert "private provider body" not in response.text
    assert "fake-key" not in response.text


def test_assistant_is_disabled_outside_demo_environment(api_client, monkeypatch):
    monkeypatch.setattr(main.settings, "app_env", "production")
    response = api_client.post("/api/ai/chat", json={"message": "Explain the return policy."})
    assert response.status_code == 403
    monkeypatch.setattr(main.settings, "app_env", "development")


def test_health_never_exposes_nvidia_credential(api_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "nvidia_api_key", SecretStr("health-test-secret"))
    response = api_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["nvidia"]["configured"] is True
    assert "health-test-secret" not in response.text
    assert "NVIDIA_API_KEY" not in response.text