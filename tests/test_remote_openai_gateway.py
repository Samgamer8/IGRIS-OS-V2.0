import os
from unittest.mock import Mock, patch

from igris_os.ai.frontier_gateway import FrontierGateway, REMOTE_OPENAI_PREFIX


def test_remote_endpoint_requires_opt_in_https_v1_and_token():
    values = {
        "IGRIS_ALLOW_REMOTE_MODELS": "1",
        "IGRIS_REMOTE_OPENAI_ENDPOINT": "https://worker.example/v1",
        "IGRIS_REMOTE_OPENAI_API_KEY": "test-token",
    }
    with patch.dict(os.environ, values, clear=True):
        assert FrontierGateway._remote_openai_config() == (
            "https://worker.example/v1", "test-token",
        )
    with patch.dict(os.environ, {**values, "IGRIS_ALLOW_REMOTE_MODELS": "0"}, clear=True):
        assert FrontierGateway._remote_openai_config() == ("", "")
    with patch.dict(os.environ, {
        **values, "IGRIS_REMOTE_OPENAI_ENDPOINT": "http://worker.example/v1",
    }, clear=True):
        assert FrontierGateway._remote_openai_config() == ("", "")
    with patch.dict(os.environ, {
        **values, "IGRIS_REMOTE_OPENAI_API_KEY": "",
    }, clear=True):
        assert FrontierGateway._remote_openai_config() == ("", "")


def test_remote_models_are_namespaced_and_authorized_without_exposing_token():
    local = Mock()
    local.models.return_value = ()
    local.backends.return_value = ()
    gateway = FrontierGateway(local=local)
    request = Mock(return_value={"data": [{"id": "qwen-coder-large"}]})
    gateway._request_json = request
    with patch.dict(os.environ, {
        "IGRIS_ALLOW_REMOTE_MODELS": "1",
        "IGRIS_REMOTE_OPENAI_ENDPOINT": "https://worker.example/v1",
        "IGRIS_REMOTE_OPENAI_API_KEY": "test-token",
        "IGRIS_ALLOW_CLOUD_MODELS": "0",
    }, clear=True):
        models = gateway.models()
        target = gateway._remote_target(REMOTE_OPENAI_PREFIX + "qwen-coder-large")

    assert models == (REMOTE_OPENAI_PREFIX + "qwen-coder-large",)
    assert target == (
        "remote-openai", "https://worker.example/v1", "qwen-coder-large", "test-token",
    )
    kwargs = request.call_args.kwargs
    assert kwargs["headers"] == {"Authorization": "Bearer test-token"}


def test_remote_model_generation_fails_closed_without_config():
    local = Mock()
    gateway = FrontierGateway(local=local)
    with patch.dict(os.environ, {"IGRIS_ALLOW_REMOTE_MODELS": "0"}, clear=True):
        reply = gateway.generate("prompt", REMOTE_OPENAI_PREFIX + "model")
    assert not reply.ok
    assert "no configurado" in reply.error
    local.generate.assert_not_called()


def test_remote_model_generation_uses_authenticated_https_endpoint():
    local = Mock()
    gateway = FrontierGateway(local=local)
    request = Mock(return_value={"choices": [{"message": {"content": "respuesta"}}]})
    gateway._request_json = request
    with patch.dict(os.environ, {
        "IGRIS_ALLOW_REMOTE_MODELS": "1",
        "IGRIS_REMOTE_OPENAI_ENDPOINT": "https://worker.example/v1",
        "IGRIS_REMOTE_OPENAI_API_KEY": "test-token",
    }, clear=True):
        reply = gateway.generate("prompt", REMOTE_OPENAI_PREFIX + "model")
    assert reply.ok
    assert reply.text == "respuesta"
    assert reply.backend == "remote-openai"
    assert request.call_args.args[:2] == (
        "POST", "https://worker.example/v1/chat/completions",
    )
    headers = request.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["Content-Type"] == "application/json"
