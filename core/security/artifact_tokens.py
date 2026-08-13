"""HMAC-signed artifact tokens for download and provider URLs.

Token format: artifact_id|expires_at|purpose|project_id|signature_fullSHA256

- Full SHA-256 HMAC (not truncated)
- hmac.compare_digest() prevents timing attacks
- allowed_purposes: "download" or "provider"
- expires_at: absolute UNIX timestamp, max 1 hour for provider
"""

import hashlib
import hmac
import re
import time

_MAX_PROVIDER_TTL = 3600

_ARTIFACT_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def _get_secret() -> bytes:
    """Read signing secret from Settings on each call — never cache at import."""
    try:
        from core.config import get_settings

        s = get_settings().artifact_signing_secret
        if s and s != "change-me-in-production" and len(s) >= 32:
            return s.encode("utf-8")
    except Exception:
        pass
    raise RuntimeError("ARTIFACT_SIGNING_SECRET must be configured with at least 32 characters")


def _hmac_full(payload: str) -> str:
    return hmac.new(_get_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_token(artifact_id: str, expires_at: int, purpose: str, project_id: str = "") -> str:
    """Create a signed token with full SHA-256 HMAC."""
    payload = f"{artifact_id}|{expires_at}|{purpose}|{project_id}"
    sig = _hmac_full(payload)
    return f"{payload}|{sig}"


def verify_token(token: str, allowed_purposes: set[str]) -> dict | None:
    """Verify a signed token.

    allowed_purposes: e.g. {"download"} or {"provider"} or {"download","provider"}
    Returns dict(artifact_id, expires_at, purpose, project_id) or None.
    """
    parts = token.rsplit("|", 1)
    if len(parts) != 2:
        return None
    payload, sig = parts
    if not hmac.compare_digest(_hmac_full(payload), sig):
        return None
    fields = payload.split("|")
    if len(fields) < 4:
        return None
    artifact_id, expires_str, purpose, project_id, *_ = fields

    # Validate artifact_id format
    if not _ARTIFACT_ID_RE.match(artifact_id):
        return None

    try:
        expires_at = int(expires_str)
    except ValueError:
        return None

    if purpose not in allowed_purposes:
        return None
    if expires_at < int(time.time()):
        return None

    # Provider: require non-empty project_id, enforce max TTL
    if purpose == "provider":
        if not project_id or not _ARTIFACT_ID_RE.match(project_id):
            return None
        if expires_at - int(time.time()) > _MAX_PROVIDER_TTL:
            return None

    return {
        "artifact_id": artifact_id,
        "expires_at": expires_at,
        "purpose": purpose,
        "project_id": project_id,
    }
