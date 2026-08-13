from urllib.parse import parse_qs, urlparse

from core.security.artifact_tokens import verify_token
from core.task_storage import StorageService


def test_download_url_contains_valid_signed_token(monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_SIGNING_SECRET", "x" * 40)
    from core.config import get_settings

    get_settings.cache_clear()
    artifact_id = "a" * 32
    url = StorageService.create_download_url(artifact_id, expires_s=60)
    token = parse_qs(urlparse(url).query)["token"][0]

    payload = verify_token(token, allowed_purposes={"download"})
    assert payload is not None
    assert payload["artifact_id"] == artifact_id
    assert payload["purpose"] == "download"
    get_settings.cache_clear()
