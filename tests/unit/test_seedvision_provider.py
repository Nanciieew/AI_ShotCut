import requests

from models.doubao_vision.providers.seedvision import SeedVisionProvider


class _Response:
    status_code = 200
    headers = {}

    def json(self):
        return {"choices": [{"message": {"content": '{"ok": true}'}}]}


class _FlakySession:
    def __init__(self):
        self.calls = 0

    def mount(self, *_args):
        pass

    def post(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            raise requests.ReadTimeout("slow response")
        return _Response()

    def close(self):
        pass


def test_provider_retries_read_timeout() -> None:
    session = _FlakySession()
    provider = SeedVisionProvider(
        api_key="test",
        session=session,
        max_attempts=2,
        retry_backoff_seconds=0,
    )
    result = provider.send([])
    assert result["data"] == {"ok": True}
    assert session.calls == 2
