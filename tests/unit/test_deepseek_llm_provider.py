import requests

from models.vlm_boundary.providers.deepseek_llm import DeepSeekLLMProvider


class _Response:
    status_code = 200
    text = ""

    @staticmethod
    def json():
        return {"choices": [{"message": {"content": '{"ok": true}'}}]}


def test_deepseek_retries_timeout_then_returns_parsed_json(monkeypatch) -> None:
    calls = 0

    def post(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
        nonlocal calls
        calls += 1
        if calls == 1:
            raise requests.Timeout("temporary")
        return _Response()

    provider = DeepSeekLLMProvider(
        api_key="test",
        max_attempts=2,
        retry_delay_s=0,
    )
    monkeypatch.setattr(provider.session, "post", post)

    result = provider.send([{"role": "user", "content": "test"}])

    assert calls == 2
    assert result["data"] == {"ok": True}
    assert result["telemetry"]["attempts"] == 2
    assert result["telemetry"]["retry_count"] == 1
