"""Replay-safe writes, keyed by an ``Idempotency-Key`` header.

A client that times out on a POST cannot tell whether the write happened.
Retrying is the only sensible thing to do, and without a key that retry
creates a second student, a second payment, a second course. With one, the
server recognises the repeat and replays the original response instead of
acting twice.

Two layers exist, deliberately:

* ``StudentLifecycleService`` and friends take an ``idempotency_key`` and
  de-duplicate against the transactional outbox. That is the strong
  guarantee — atomic with the write itself.
* This decorator is the transport-level cache in front of it, so a repeat
  gets the *same response body*, including for routes whose service layer
  has no outbox. It is not a substitute for the former where both apply.

Scope: unsafe methods only, and only when the client supplies a key. No key
means no promise, which keeps every existing client working unchanged.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Callable

from flask import Response, jsonify, request

logger = logging.getLogger(__name__)

HEADER = "Idempotency-Key"

#: How long a key is honoured. Long enough to cover a retry storm or a client
#: restart, short enough that the table stays small.
TTL = timedelta(hours=24)

#: Keys are client-supplied; cap the length so the store cannot be flooded.
MAX_KEY_LENGTH = 255

_LOCK = threading.Lock()
_MEMORY: dict[str, tuple[datetime, int, Any]] = {}


def _fingerprint() -> str:
    """Identify the request a key was first used for.

    Reusing one key for a *different* request is a client bug; replaying the
    first response would hide it. Comparing a fingerprint surfaces it as a
    409 instead.
    """
    body = request.get_data(cache=True) or b""
    material = b"|".join([
        request.method.encode(), request.path.encode(),
        hashlib.sha256(body).digest(),
    ])
    return hashlib.sha256(material).hexdigest()


def _prune(now: datetime) -> None:
    stale = [k for k, (seen, _, _) in _MEMORY.items() if now - seen > TTL]
    for key in stale:
        _MEMORY.pop(key, None)


def idempotent(view: Callable) -> Callable:
    """Replay the first response for a repeated ``Idempotency-Key``."""

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        key = (request.headers.get(HEADER) or "").strip()
        if request.method in ("GET", "HEAD", "OPTIONS") or not key:
            return view(*args, **kwargs)
        if len(key) > MAX_KEY_LENGTH:
            return jsonify({
                "error": "Idempotency-Key too long",
                "detail": f"Maximum {MAX_KEY_LENGTH} characters.",
                "status": 400,
            }), 400

        now = datetime.now()
        print_key = f"{request.method}:{request.path}:{key}"
        with _LOCK:
            _prune(now)
            record = _MEMORY.get(print_key)

        if record is not None:
            seen, status, payload = record
            stored_fp, body = payload
            if stored_fp != _fingerprint():
                # Same key, different request: a client bug worth surfacing.
                return jsonify({
                    "error": "Idempotency-Key reused for a different request",
                    "detail": "This key was already used with a different "
                              "method, path or body.",
                    "status": 409,
                }), 409
            logger.info("Replaying idempotent response for %s", print_key)
            response = Response(body, status=status,
                                mimetype="application/json")
            response.headers["Idempotent-Replay"] = "true"
            return response

        result = view(*args, **kwargs)

        # Only successful writes are worth replaying: a failure should be
        # retryable, and caching a 500 would make a transient fault sticky.
        body, status = _split(result)
        if body is not None and 200 <= status < 300:
            with _LOCK:
                _MEMORY[print_key] = (now, status, (_fingerprint(), body))
        return result

    return wrapper


def _split(result) -> tuple[bytes | None, int]:
    """Normalise a Flask view return into (body bytes, status)."""
    status = 200
    explicit_status = False
    payload = result
    if isinstance(result, tuple):
        payload = result[0]
        if len(result) > 1 and isinstance(result[1], int):
            status = result[1]
            explicit_status = True
    try:
        if isinstance(payload, Response):
            # A `(jsonify(...), 201)` tuple carries the real status alongside a
            # Response whose own status_code is still 200. Prefer the explicit
            # one, or a replayed 201 would come back as 200.
            return payload.get_data(), (status if explicit_status
                                        else payload.status_code)
        if isinstance(payload, (dict, list)):
            return json.dumps(payload).encode(), status
    except Exception:
        logger.debug("idempotency: response not cacheable", exc_info=True)
    return None, status


def clear() -> None:
    """Drop every stored key. For tests."""
    with _LOCK:
        _MEMORY.clear()


__all__ = ["HEADER", "MAX_KEY_LENGTH", "TTL", "clear", "idempotent"]
