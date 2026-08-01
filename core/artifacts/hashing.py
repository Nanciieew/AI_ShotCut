"""Artifact hashing utilities.

Centralizes the hashing logic used for cache keys, artifact integrity,
and input fingerprinting per the architecture spec §17.
"""

import hashlib
from pathlib import Path


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """SHA-256 hex digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cache_key(
    *,
    input_sha256: str,
    model_name: str,
    model_version: str,
    parameters: dict,
    schema_version: str,
    code_revision: str | None = None,
) -> str:
    """Build a deterministic cache key for artifact reuse.

    Per §17 of the architecture spec:
      cache_key = input_sha256 + model_name + model_version
                  + parameters + schema_version + code_revision

    Returns a hex digest of the combined inputs.
    """
    from json import dumps

    payload = "|".join(
        [
            input_sha256,
            model_name,
            model_version,
            dumps(parameters, sort_keys=True),
            schema_version,
            code_revision or "",
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()
