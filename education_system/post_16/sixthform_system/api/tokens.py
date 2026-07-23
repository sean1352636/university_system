"""Minimal signed-token helper for the Sixth Form REST API.

Avoids a hard dependency on a JWT library: tokens are
``base64(payload).hmac_sha256`` strings signed with a server secret.
The payload carries the parent account id and an expiry timestamp. This
is enough for a read-only parent portal session; swap in the shared
JWT auth if/when the portal needs to federate with staff auth.

The secret comes from ``EDU_SIXTHFORM_API_SECRET``. If unset, a random
per-process secret is generated — fine for dev (tokens simply don't
survive a restart), but production should set a stable secret.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60 * 60 * 8  # 8 hours

_SECRET = os.environ.get("EDU_SIXTHFORM_API_SECRET") or secrets.token_hex(32)
if "EDU_SIXTHFORM_API_SECRET" not in os.environ:
    logger.warning("EDU_SIXTHFORM_API_SECRET not set — using an ephemeral secret; "
                   "tokens will not survive a restart.")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(payload_b64: str) -> str:
    sig = hmac.new(_SECRET.encode(), payload_b64.encode(), hashlib.sha256).digest()
    return _b64e(sig)


def issue(account_id: int, *, ttl: int = DEFAULT_TTL_SECONDS,
          now: float | None = None) -> str:
    now = now if now is not None else time.time()
    payload = {"sub": account_id, "exp": int(now + ttl)}
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify(token: str, *, now: float | None = None) -> int | None:
    """Return the account id if the token is valid and unexpired, else None."""
    now = now if now is not None else time.time()
    try:
        payload_b64, sig = token.split(".", 1)
    except (ValueError, AttributeError):
        return None
    if not hmac.compare_digest(sig, _sign(payload_b64)):
        return None
    try:
        payload = json.loads(_b64d(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < now:
        return None
    sub = payload.get("sub")
    return int(sub) if isinstance(sub, int) else None
