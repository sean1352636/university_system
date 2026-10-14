"""Local administrative control of the running server.

Currently one route: an orderly shutdown, so the desktop-style portal can
offer a "Shut down" button instead of leaving the user to find the
terminal they launched it from.

An endpoint that stops the server is a denial-of-service primitive, so it
is deliberately hard to reach. Four conditions must all hold:

1. the request arrives from the loopback interface;
2. the caller presents a valid access token;
3. the caller's role is an administrative one;
4. ``ALLOW_REMOTE_SHUTDOWN`` is not required — see below.

Condition 1 is the important one. A deployment behind a reverse proxy
sees every request as coming from the proxy, which would make loopback
checks meaningless — so the proxy case is refused outright unless the
operator sets ``ALLOW_REMOTE_SHUTDOWN=true``, which they should only do
for a single-user local install.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import signal
import threading

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.auth import token_required

logger = logging.getLogger(__name__)

admin_control_bp = Blueprint("admin_control", __name__)

#: Roles permitted to stop the server.
_SHUTDOWN_ROLES = {"admin", "superadmin"}


def _is_loopback(addr: str | None) -> bool:
    if not addr:
        return False
    try:
        return ipaddress.ip_address(addr.strip()).is_loopback
    except ValueError:
        return False


def _behind_proxy() -> bool:
    """Whether this request was forwarded, making remote_addr untrustworthy."""
    return any(request.headers.get(h) for h in
               ("X-Forwarded-For", "X-Real-IP", "Forwarded"))


def _caller_role() -> str:
    user = g.get("current_user") or {}
    role = user.get("role")
    if role:
        return str(role).lower()
    # Shared-login tokens carry access per system rather than a flat role.
    for entry in user.get("systems") or ():
        if isinstance(entry, dict) and entry.get("role"):
            if str(entry["role"]).lower() in _SHUTDOWN_ROLES:
                return str(entry["role"]).lower()
    return ""


@admin_control_bp.route("/admin/shutdown", methods=["POST"])
@token_required
def shutdown():
    """Stop the server after returning a response."""
    allow_remote = os.getenv("ALLOW_REMOTE_SHUTDOWN", "").lower() in ("1", "true", "yes")

    if _behind_proxy() and not allow_remote:
        logger.warning("Shutdown refused: forwarded request from %s",
                       request.remote_addr)
        return jsonify({
            "error": "Shutdown is only available to a locally running server.",
        }), 403

    if not allow_remote and not _is_loopback(request.remote_addr):
        logger.warning("Shutdown refused: non-loopback caller %s",
                       request.remote_addr)
        return jsonify({
            "error": "Shutdown may only be requested from this machine.",
        }), 403

    role = _caller_role()
    if role not in _SHUTDOWN_ROLES:
        logger.warning("Shutdown refused for role %r (user %s)",
                       role, (g.get("current_user") or {}).get("username"))
        return jsonify({"error": "Administrator access required."}), 403

    username = (g.get("current_user") or {}).get("username", "unknown")
    logger.info("Shutdown requested by %s from %s", username, request.remote_addr)

    def _stop() -> None:
        # Give the response time to reach the browser before the process
        # goes away, otherwise the click looks like a network failure.
        import time
        time.sleep(0.5)
        # SIGTERM rather than os._exit: the dev server, gunicorn and a
        # container supervisor all handle it, and shutdown hooks still run.
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({"message": "Shutting down."})
