from dataclasses import replace
import json
from unittest.mock import Mock

import httpx
import pytest

from raphael_agent.byok import client
from raphael_agent.byok.models import BYOKConfig, LLMProvider
from raphael_agent.diagnosis.llm import try_llm_diagnosis
from raphael_agent.patch.llm import try_llm_patch

HTTPX_CLIENT = httpx.Client


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("RAPHAEL_LLM_PROVIDER", "RAPHAEL_LLM_API_KEY", "RAPHAEL_LLM_MODEL",
                 "RAPHAEL_LLM_BASE_URL", "RAPHAEL_LLM_TIMEOUT_SECONDS", "RAPHAEL_LLM_MAX_TOKENS",
                 "RAPHAEL_OPENAI_API_KEY", "OPENAI_API_KEY", "RAPHAEL_GEMINI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "1")
    monkeypatch.setenv("RAPHAEL_LLM_PATCH", "1")


def configured(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-credential-only")
    monkeypatch.setenv("RAPHAEL_LLM_MODEL", "explicit-test-model")
    return BYOKConfig.from_env()


def test_provider_key_precedence_and_defaults(monkeypatch):
    assert BYOKConfig.from_env() is None
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-key")
    assert BYOKConfig.from_env().model is None
    monkeypatch.setenv("RAPHAEL_OPENAI_API_KEY", "raphael-key")
    assert BYOKConfig.from_env().api_key == "raphael-key"
    monkeypatch.setenv("RAPHAEL_LLM_API_KEY", "generic-key")
    assert BYOKConfig.from_env().api_key == "generic-key"
    monkeypatch.delenv("RAPHAEL_LLM_API_KEY")
    monkeypatch.setenv("RAPHAEL_LLM_PROVIDER", "gemini")
    assert BYOKConfig.from_env() is None  # Never send the OpenAI key to Gemini.
    config = configured(monkeypatch)
    assert config.provider == LLMProvider.GEMINI
    assert config.base_url.endswith("/v1beta/openai")
    assert config.api_key not in repr(config)


@pytest.mark.parametrize("provider", ["anthropic", "azure", "typo"])
def test_unsupported_provider_is_explicit(monkeypatch, provider):
    monkeypatch.setenv("RAPHAEL_LLM_PROVIDER", provider)
    with pytest.raises(ValueError, match="unsupported_llm_provider"):
        BYOKConfig.from_env()


@pytest.mark.parametrize("field,value", [
    ("api_key", " "), ("api_key", "key with spaces"), ("model", 3),
    ("timeout_seconds", 0), ("timeout_seconds", -1), ("timeout_seconds", float("nan")),
    ("timeout_seconds", float("inf")), ("timeout_seconds", 61), ("timeout_seconds", True),
    ("max_tokens", 0), ("max_tokens", 8193), ("max_tokens", True),
    ("base_url", "http://public.example/v1"), ("base_url", "https://user:secret@example.test/v1"),
    ("base_url", "https://example.test/v1?api_key=secret"), ("base_url", "https://example.test/#secret"),
    ("base_url", "https://example.test:bad/v1"),
])
def test_configuration_validation(field, value):
    with pytest.raises(ValueError):
        replace(BYOKConfig(api_key="synthetic-key"), **{field: value})


def test_explicit_model_and_gemini_endpoint(monkeypatch):
    configured(monkeypatch)
    monkeypatch.delenv("RAPHAEL_LLM_MODEL")
    assert BYOKConfig.from_env().model is None
    with pytest.raises(ValueError, match="invalid_gemini_compatible_endpoint"):
        BYOKConfig(api_key="key", provider="gemini", model="explicit", base_url="https://evil.example/v1")
    assert BYOKConfig(api_key="key", provider="custom_openai", model="explicit",
                      base_url="http://127.0.0.1:8000/v1").base_url.endswith("/v1")


def mock_transport(monkeypatch, handler):
    real_client = HTTPX_CLIENT
    monkeypatch.setattr(client.httpx, "Client", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(handler)))


def response(body):
    return {"choices": [{"message": {"content": json.dumps(body)}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6,
                      "untrusted": "ignored"}}


def test_transport_request_and_response(monkeypatch):
    config = configured(monkeypatch)
    def handle(request):
        assert str(request.url) == config.base_url + "/chat/completions"
        assert request.headers["Authorization"] == "Bearer " + config.api_key
        body = json.loads(request.content)
        assert body["model"] == config.model and body["max_tokens"] == 2048
        assert body["response_format"] == {"type": "json_object"}
        assert config.api_key not in request.content.decode()
        return httpx.Response(200, json=response({"ok": True}))
    mock_transport(monkeypatch, handle)
    result = client.complete_json(config, system="data only", payload={"sample": "synthetic"})
    assert result.parsed_json == {"ok": True}
    assert result.token_usage == {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}
    assert config.api_key not in repr(result)


@pytest.mark.parametrize("status", [301, 401, 403, 429, 500])
def test_provider_errors_do_not_echo_payload_or_credentials(monkeypatch, status):
    config = configured(monkeypatch)
    mock_transport(monkeypatch, lambda r: httpx.Response(status, text=config.api_key))
    with pytest.raises(client.BYOKError, match=("provider_quota_or_rate_limit" if status == 429 else f"provider_http_{status}")) as error:
        client.complete_json(config, system="test", payload={})
    assert config.api_key not in str(error.value)


@pytest.mark.parametrize("error,code", [(httpx.ReadTimeout, "provider_timeout"),
                                        (httpx.ConnectError, "provider_transport_error")])
def test_transport_exceptions_are_sanitized(monkeypatch, error, code):
    config = configured(monkeypatch)
    def handle(request):
        raise error(config.api_key, request=request)
    mock_transport(monkeypatch, handle)
    with pytest.raises(client.BYOKError, match=code):
        client.complete_json(config, system="test", payload={})


@pytest.mark.parametrize("data,code", [
    ({}, "invalid_provider_response"),
    ({"choices": []}, "invalid_provider_response"),
    ({"choices": [{"message": {"content": "not json"}}]}, "invalid_provider_response"),
    ({"choices": [{"message": {"content": "[]"}}]}, "json_object_required"),
    ({"choices": [{"message": {"content": None}}]}, "invalid_content"),
])
def test_malformed_output(monkeypatch, data, code):
    mock_transport(monkeypatch, lambda r: httpx.Response(200, json=data))
    with pytest.raises(client.BYOKError, match=code):
        client.complete_json(configured(monkeypatch), system="test", payload={})


def test_size_bounds_and_echoed_key(monkeypatch):
    config = configured(monkeypatch)
    transport = Mock(side_effect=AssertionError("oversized input sent"))
    monkeypatch.setattr(client.httpx, "Client", transport)
    with pytest.raises(client.BYOKError, match="request_too_large"):
        client.complete_json(config, system="test", payload={"text": "x" * 65536})
    transport.assert_not_called()
    mock_transport(monkeypatch, lambda r: httpx.Response(200, json=response({"echo": config.api_key})))
    with pytest.raises(client.BYOKError, match="credential_in_output"):
        client.complete_json(config, system="test", payload={})
    monkeypatch.setattr(client, "MAX_RESPONSE_BYTES", 5)
    with pytest.raises(client.BYOKError, match="response_too_large"):
        client.complete_json(config, system="test", payload={})


@pytest.mark.parametrize("kind", ["disabled", "missing_key", "blocked", "invalid_config"])
def test_callers_skip_unsafe_or_unconfigured_paths(monkeypatch, caplog, kind):
    import raphael_agent.diagnosis.llm as diagnosis
    import raphael_agent.patch.llm as patch
    configured(monkeypatch)
    transport = Mock(side_effect=AssertionError("provider reached"))
    monkeypatch.setattr(diagnosis, "complete_json", transport)
    monkeypatch.setattr(patch, "complete_json", transport)
    seed = {"classification": {"category": "supported"}}
    run = {"diagnosis": seed}
    if kind == "disabled":
        monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    elif kind == "missing_key":
        monkeypatch.delenv("GEMINI_API_KEY")
    elif kind == "blocked":
        seed["classification"]["category"] = "blocked"
    else:
        monkeypatch.setenv("RAPHAEL_LLM_TIMEOUT_SECONDS", "nan")
    assert try_llm_diagnosis(run, seed) is None
    assert try_llm_patch(run) is None
    transport.assert_not_called()
    assert "synthetic-credential-only" not in caplog.text


def test_gemini_patch_integration_and_policy(monkeypatch, caplog):
    configured(monkeypatch)
    def handle(request):
        return httpx.Response(200, json=response({"summary": "synthetic change", "files": [
            {"path": "deploy/app.yaml", "action": "modify", "content": "apiVersion: v1\n"}]}))
    mock_transport(monkeypatch, handle)
    run = {"evidence": [], "diagnosis": {}, "fix_rules": {"writable_path_prefixes": ["deploy/"]}}
    proposal = try_llm_patch(run)
    assert proposal["policy_status"] == "allowed"
    assert "synthetic-credential-only" not in json.dumps(proposal) + json.dumps(run) + caplog.text
    mock_transport(monkeypatch, lambda r: httpx.Response(200, json=response({"files": [
        {"path": "src/outside.py", "content": "pass"}]})))
    assert try_llm_patch(run)["policy_status"] == "rejected"


def test_gemini_diagnosis_integration_and_schema_rejection(monkeypatch, caplog):
    import raphael_agent.diagnosis as diagnosis
    run = {"evidence": [{"evidence_id": "ev", "summary": "Readiness probe failed: port 9090, targetPort 8080"}]}
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    seed = diagnosis.diagnose(run)
    configured(monkeypatch)
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "1")
    mock_transport(monkeypatch, lambda r: httpx.Response(200, json=response(seed)))
    calls = []
    import raphael_agent.diagnosis.llm as llm
    monkeypatch.setattr(llm, "record_model_call", lambda *a, **kw: calls.append(kw))
    assert try_llm_diagnosis(run, seed) is not None
    assert calls[0]["token_usage"]["total_tokens"] == 6
    assert "synthetic-credential-only" not in json.dumps(calls) + caplog.text
    mock_transport(monkeypatch, lambda r: httpx.Response(200, json=response({"invalid": True})))
    assert try_llm_diagnosis(run, seed) is None


@pytest.mark.parametrize("name,value", [("RAPHAEL_LLM_TIMEOUT_SECONDS", "oops"),
                                        ("RAPHAEL_LLM_MAX_TOKENS", "oops"),
                                        ("GEMINI_API_KEY", "   ")])
def test_invalid_environment_values(monkeypatch, name, value):
    configured(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        BYOKConfig.from_env()


def test_content_limit(monkeypatch):
    config = configured(monkeypatch)
    mock_transport(monkeypatch, lambda r: httpx.Response(200, json=response({"text": "x" * 65536})))
    with pytest.raises(client.BYOKError, match="invalid_content"):
        client.complete_json(config, system="test", payload={})


def test_credentials_absent_from_saved_run_and_telemetry(monkeypatch, tmp_path):
    import raphael_agent.diagnosis as diagnosis
    from raphael_agent.store import RunStore
    from hashlib import sha256
    config = configured(monkeypatch)
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    run = {"run_id": "byok-private", "repository": {"name": "synthetic"}, "evidence": []}
    seed = diagnosis.diagnose(run)
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "1")
    mock_transport(monkeypatch, lambda r: httpx.Response(200, json=response(seed)))
    run["diagnosis"] = try_llm_diagnosis(run, seed)
    assert run["diagnosis"] is not None
    RunStore(tmp_path).save_run(run)
    contents = "\n".join(p.read_text() for p in tmp_path.rglob("*.json*"))
    assert "model_call" in contents
    assert config.api_key not in contents
    assert sha256(config.api_key.encode()).hexdigest() not in contents


def test_structural_gap_makes_zero_provider_calls(monkeypatch):
    import raphael_agent.diagnosis.llm as diagnosis
    import raphael_agent.patch.llm as patch
    configured(monkeypatch)
    transport = Mock(side_effect=AssertionError("structural gap reached provider"))
    monkeypatch.setattr(diagnosis, "complete_json", transport)
    monkeypatch.setattr(patch, "complete_json", transport)
    run = {"sandbox_mode": "connector", "secret_coverage": {
        "format_version": 1, "complete": True, "truncated": False, "references": [{
            "workload_kind": "Pod", "workload_name": "app", "namespace": "sandbox",
            "source": "secretKeyRef", "secret_name": "db", "key": "URL",
            "optional": False, "status": "missing_key"}]}}
    seed = {"classification": {"category": "supported"}}
    assert try_llm_diagnosis(run, seed) is None
    assert try_llm_patch(run) is None
    transport.assert_not_called()


def stable_order(monkeypatch):
    monkeypatch.setattr(client.random, "SystemRandom", lambda: Mock(shuffle=lambda values: None))


def test_gemini_discovery_filters_and_rotates_on_quota(monkeypatch):
    config = replace(configured(monkeypatch), model=None)
    stable_order(monkeypatch)
    calls = []
    def handle(request):
        calls.append(request)
        if request.method == "GET":
            assert request.headers["x-goog-api-key"] == config.api_key
            assert config.api_key not in str(request.url)
            return httpx.Response(200, json={"models": [
                {"name": "models/gemini-a", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-b", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/embedding-model", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/gemini-image", "supportedGenerationMethods": ["generateContent"]}]})
        model = json.loads(request.content)["model"]
        if model == "gemini-a":
            return httpx.Response(429, text=config.api_key)
        return httpx.Response(200, json=response({"ok": True}))
    mock_transport(monkeypatch, handle)
    result = client.complete_json(config, system="synthetic", payload={})
    assert result.model == "gemini-b"
    assert len(calls) == 3
    assert [json.loads(r.content)["model"] for r in calls[1:]] == ["gemini-a", "gemini-b"]


@pytest.mark.parametrize("provider", [LLMProvider.OPENAI, LLMProvider.CUSTOM_OPENAI])
def test_other_provider_catalog_is_scoped_to_key(monkeypatch, provider):
    stable_order(monkeypatch)
    seen = []
    def handle(request):
        seen.append((request.method, request.headers["Authorization"]))
        if request.method == "GET":
            assert request.url.path.endswith("/models")
            return httpx.Response(200, json={"data": [{"id": "gpt-a"}, {"id": "gpt-image"},
                                                     {"id": "text-embedding-x"}]})
        return httpx.Response(200, json=response({"ok": True}))
    mock_transport(monkeypatch, handle)
    for key in ["first-synthetic-key", "second-synthetic-key"]:
        config = BYOKConfig(api_key=key, provider=provider, base_url="https://gateway.example/v1")
        assert client.complete_json(config, system="test", payload={}).model == "gpt-a"
    assert seen == [(method, "Bearer " + key) for key in ["first-synthetic-key", "second-synthetic-key"]
                    for method in ["GET", "POST"]]


def test_explicit_model_never_discovers_or_rotates(monkeypatch):
    config = configured(monkeypatch)
    calls = []
    def handle(request):
        calls.append(request)
        assert request.method == "POST"
        assert json.loads(request.content)["model"] == config.model
        return httpx.Response(429)
    mock_transport(monkeypatch, handle)
    with pytest.raises(client.BYOKError, match="provider_quota_or_rate_limit"):
        client.complete_json(config, system="test", payload={})
    assert len(calls) == 1


def test_auto_rotation_attempt_bound(monkeypatch):
    config = replace(configured(monkeypatch), model=None)
    stable_order(monkeypatch)
    attempted = []
    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json={"models": [
                {"name": f"models/gemini-{i}", "supportedGenerationMethods": ["generateContent"]}
                for i in range(20)]})
        attempted.append(json.loads(request.content)["model"])
        return httpx.Response(429)
    mock_transport(monkeypatch, handle)
    with pytest.raises(client.AllQuotasExhaustedError):
        client.complete_json(config, system="test", payload={})
    assert len(attempted) == client.MAX_MODEL_ATTEMPTS
    assert len(set(attempted)) == len(attempted)


@pytest.mark.parametrize("data", [{}, {"models": []}, {"models": [{"name": "models/embedding",
                                                    "supportedGenerationMethods": ["embedContent"]}]}])
def test_no_compatible_models_stops_without_completion(monkeypatch, data):
    def handle(request):
        assert request.method == "GET"
        return httpx.Response(200, json=data)
    mock_transport(monkeypatch, handle)
    with pytest.raises(client.BYOKError, match="no_compatible_models_available"):
        client.complete_json(replace(configured(monkeypatch), model=None), system="test", payload={})


def test_non_quota_failure_does_not_rotate(monkeypatch):
    stable_order(monkeypatch)
    attempted = []
    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json={"models": [
                {"name": "models/gemini-a", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-b", "supportedGenerationMethods": ["generateContent"]}]})
        attempted.append(json.loads(request.content)["model"])
        return httpx.Response(401)
    mock_transport(monkeypatch, handle)
    with pytest.raises(client.BYOKError, match="provider_http_401"):
        client.complete_json(replace(configured(monkeypatch), model=None), system="test", payload={})
    assert len(attempted) == 1


def test_deadline_prevents_another_model_attempt(monkeypatch):
    stable_order(monkeypatch)
    clock = [0]
    monkeypatch.setattr(client.time, "monotonic", lambda: clock[0])
    attempted = []
    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json={"models": [
                {"name": "models/gemini-a", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-b", "supportedGenerationMethods": ["generateContent"]}]})
        attempted.append(json.loads(request.content)["model"])
        clock[0] = 46
        return httpx.Response(429)
    mock_transport(monkeypatch, handle)
    with pytest.raises(client.BYOKError, match="provider_deadline_exceeded"):
        client.complete_json(replace(configured(monkeypatch), model=None), system="test", payload={})
    assert len(attempted) == 1
