"""Public online application endpoint for the Sixth Form.

``POST /api/v1/sixthform/applications`` is the one sixth-form route that
needs no token: prospective students apply from the college website.
It is deliberately narrow:

* POST only, JSON only, body capped at :data:`MAX_BODY_BYTES`;
* strict field whitelist and validation (``online_application.clean``);
* a per-IP rate limit here (burst, in-process) on top of the persisted
  daily limit in the domain module;
* the response carries nothing but a reference number — no applicant
  id, no duplicate hints, no echo of the submitted data;
* the applicant lands as "Online - unverified" for staff to check in the
  admissions window before it joins the pipeline;
* a hidden honeypot field (``website``) is accepted and silently
  dropped by the domain (``online_application.HONEYPOT_FIELD``).

Client address for rate limiting (:func:`client_ip`): the socket address,
unless that address is a proxy listed in ``SIXTHFORM_TRUSTED_PROXIES``
(comma-separated IPs or CIDR ranges, e.g. ``127.0.0.1,10.0.0.0/8``). Only
then is ``X-Forwarded-For`` read, taking the right-most hop that is not
itself a trusted proxy — the left-most entries are whatever the client
chose to send. With the variable unset, ``X-Forwarded-For`` is ignored.

It is not wrapped in ``_token_required`` / the access gate on purpose.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import threading
import time
from collections import deque

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

applications_bp = Blueprint(
    "sf_applications", __name__, url_prefix="/api/applications")

#: Largest accepted request body (the personal statement is the bulk).
MAX_BODY_BYTES: int = 16 * 1024
#: Burst limit per client address: at most BURST_MAX posts per window.
BURST_MAX: int = 3
BURST_WINDOW_SECONDS: int = 600

_hits: dict[str, deque[float]] = {}
_lock = threading.Lock()


TRUSTED_PROXIES_ENV: str = "SIXTHFORM_TRUSTED_PROXIES"
_proxy_cache: tuple[str, tuple] = ("", ())


def _trusted_networks() -> tuple:
    global _proxy_cache
    raw = os.environ.get(TRUSTED_PROXIES_ENV, "").strip()
    if raw != _proxy_cache[0]:
        nets = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                nets.append(ipaddress.ip_network(part, strict=False))
            except ValueError:
                logger.warning("%s: ignoring %r (not an IP or CIDR range)",
                               TRUSTED_PROXIES_ENV, part)
        _proxy_cache = (raw, tuple(nets))
    return _proxy_cache[1]


def _in_networks(addr: str, nets: tuple) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in n for n in nets)


def client_ip() -> str:
    """The address to rate-limit on (see the module docstring)."""
    remote = request.remote_addr or "-"
    nets = _trusted_networks()
    if not nets or not _in_networks(remote, nets):
        # X-Forwarded-For is client-controlled; trusting it from anyone
        # but our own proxy would let a client reset its own limit.
        return remote
    hops = [h.strip() for h in
            request.headers.get("X-Forwarded-For", "").split(",") if h.strip()]
    for hop in reversed(hops):
        if _in_networks(hop, nets):
            continue
        try:
            return str(ipaddress.ip_address(hop))
        except ValueError:
            return remote
    return remote



def _allow(ip: str) -> bool:
    now = time.monotonic()
    with _lock:
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] > BURST_WINDOW_SECONDS:
            q.popleft()
        if len(q) >= BURST_MAX:
            return False
        q.append(now)
        # Keep the table from growing without bound.
        if len(_hits) > 10_000:
            for key in [k for k, v in _hits.items() if not v]:
                _hits.pop(key, None)
        return True


@applications_bp.route("", methods=["POST"], strict_slashes=False)
def submit_application():
    if request.content_length is None or request.content_length > MAX_BODY_BYTES:
        return jsonify({"error": "Request body missing or too large"}), 413
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415
    ip = client_ip()
    if not _allow(ip):
        return jsonify({"error": "Too many applications — please try "
                                 "again later"}), 429
    raw = request.get_data(cache=False)
    if len(raw) > MAX_BODY_BYTES:
        return jsonify({"error": "Request body too large"}), 413
    try:
        import json
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return jsonify({"error": "Body is not valid JSON"}), 400

    from education_system.systems.sixth_form.domain.admissions import (
        online_application,
    )
    try:
        ref = online_application.submit(body, client_ip=ip)
    except online_application.RateLimited:
        return jsonify({"error": "Too many applications — please try "
                                 "again later"}), 429
    except online_application.ValidationError as e:
        # Messages name fields and rules only; nothing from the database.
        return jsonify({"error": "Invalid application",
                        "details": str(e)}), 400
    except Exception:
        logger.exception("Online application failed")
        return jsonify({"error": "Application could not be saved"}), 500
    return jsonify({"reference": ref}), 201
