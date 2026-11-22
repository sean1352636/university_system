"""University e-mail: the public unsubscribe link and the outbox API.

Public (no sign-in; the reader is following a link in an e-mail):

* ``GET  /email/unsubscribe/<token>`` – a confirmation page with a button.
  It changes nothing, so link scanners and mail previewers cannot
  unsubscribe people by fetching the link.
* ``POST /email/unsubscribe/<token>`` – unsubscribes (``everything=1`` stops
  all bulk and marketing mail, otherwise just that list).

Signed in:

* ``GET  /email/status`` and ``GET /email/outbox`` (``status``, ``q``,
  ``bulk_id``, ``limit``), ``GET /email/outbox/<id>``,
  ``POST /email/outbox/<id>/retry`` and ``/cancel`` – e-mail
  administrators only (``email_outbox.holds(..., 'email_admin')``).
* ``GET``/``PUT /email/preferences`` – the caller's own preferences only,
  keyed by username.

Mounted under ``/api/v1/university``, which is where
``email_outbox.UNSUBSCRIBE_PATH`` points.
"""

from __future__ import annotations

import html
import logging

from flask import Blueprint, Response, g, jsonify, request

from education_system.platform.delivery.api.rate_limiter import rate_limiter
from education_system.platform.delivery.api.university.auth import token_required
from education_system.systems.university.application.mail import (
    admin as email_admin,
    outbox as email_outbox,
)
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

email_bp = Blueprint("university_email", __name__, url_prefix="/api/email")


def _page(title: str, message: str, status: int, form: str = "") -> Response:
    body = ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{html.escape(title)}</title></head><body style='font-family:sans-serif;"
            "max-width:36em;margin:2em auto;padding:0 1em'>"
            f"<h1>{html.escape(title)}</h1><p>{html.escape(message)}</p>{form}</body></html>")
    response = Response(body, status=status, mimetype="text/html")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _token_row(conn, token: str):
    email_outbox.ensure(conn)
    return conn.execute("SELECT address, category FROM email_unsubscribe_tokens "
                        "WHERE token = ?", (token,)).fetchone()


@email_bp.route("/unsubscribe/<token>", methods=["GET"])
@rate_limiter.limit("30/minute")
def unsubscribe_page(token: str):
    """Ask before unsubscribing; nothing changes on GET."""
    token = token[:200]
    conn = get_connection(row_factory=False)
    try:
        row = _token_row(conn, token)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("unsubscribe page failed")
        return _page("Something went wrong", "Please try again later.", 500)
    finally:
        conn.close()
    if not row:
        return _page("Link not recognised", "This unsubscribe link is not valid.", 404)
    action = html.escape(f"{email_outbox.UNSUBSCRIBE_PATH}{token}", quote=True)
    category = html.escape(row[1])
    form = (f"<form method='post' action='{action}'>"
            f"<p><button type='submit' name='everything' value='0'>Stop '{category}' e-mails"
            "</button></p><p><button type='submit' name='everything' value='1'>Stop all "
            "bulk and marketing e-mail from the university</button></p></form>"
            "<p>You will still receive e-mail you need, such as account, results and "
            "payment messages.</p>")
    return _page("Unsubscribe", f"Unsubscribe {row[0]} from university e-mail?", 200, form)


@email_bp.route("/unsubscribe/<token>", methods=["POST"])
@rate_limiter.limit("20/minute")
def unsubscribe(token: str):
    everything = str(request.form.get("everything") or request.args.get("everything") or
                     "0") == "1"
    conn = get_connection(row_factory=False)
    try:
        result = email_outbox.unsubscribe(conn, token[:200], everything=everything)
        conn.commit()
    except ValueError as exc:
        conn.rollback()
        return _page("Link not recognised", str(exc), 404)
    except Exception:
        conn.rollback()
        logger.exception("unsubscribe failed")
        return _page("Something went wrong", "Please try again later.", 500)
    finally:
        conn.close()
    what = ("all bulk and marketing e-mail" if result["category"] == "*"
            else f"'{result['category']}' e-mails")
    return _page("Unsubscribed", f"{result['address']} will no longer receive {what}.", 200)


# ── signed-in routes ────────────────────────────────────────────────────


def _caller() -> tuple[str | None, str]:
    user = g.get("current_user") or {}
    return (user.get("username") or user.get("sub") or None), str(user.get("role") or "")


def _with_conn(fn):
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _admin_only(fn):
    """Run ``fn(conn, username, role)`` for an e-mail administrator."""
    username, role = _caller()
    if not username:
        return jsonify({"error": "Not signed in"}), 401

    def body(conn):
        if not email_outbox.holds(conn, username, "email_admin", role):
            raise PermissionError("E-mail administrators only")
        return fn(conn, username, role)
    try:
        return jsonify(_with_conn(body))
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@email_bp.route("/status", methods=["GET"])
@token_required
def status():
    from education_system.systems.university.infrastructure.email import outbox_delivery

    def body(conn, _username, _role):
        delivery = outbox_delivery.status()
        delivery.pop("sandbox_dir", None)
        return {"delivery": delivery, "outbox": email_admin.summary(conn)}
    return _admin_only(body)


@email_bp.route("/outbox", methods=["GET"])
@token_required
def outbox():
    args = request.args
    limit = min(max(args.get("limit", 100, type=int) or 100, 1), 500)
    return _admin_only(lambda conn, _u, _r: {"messages": email_outbox.messages(
        conn, status=args.get("status") or None, search=args.get("q") or None,
        bulk_id=args.get("bulk_id", type=int), limit=limit)})


@email_bp.route("/outbox/<int:message_id>", methods=["GET"])
@token_required
def message(message_id: int):
    def body(conn, _u, _r):
        found = email_outbox.message(conn, message_id)
        if not found:
            raise ValueError(f"No message {message_id}")
        return found
    return _admin_only(body)


@email_bp.route("/outbox/<int:message_id>/retry", methods=["POST"])
@token_required
def retry(message_id: int):
    def body(conn, username, role):
        email_outbox.retry(conn, username, role, message_id)
        return {"ok": True}
    result = _admin_only(body)
    _kick()
    return result


@email_bp.route("/outbox/<int:message_id>/cancel", methods=["POST"])
@token_required
def cancel(message_id: int):
    def body(conn, username, role):
        email_outbox.cancel(conn, username, role, message_id)
        return {"ok": True}
    return _admin_only(body)


def _kick():
    try:
        from education_system.systems.university.infrastructure.email import outbox_delivery
        outbox_delivery.kick()
    except Exception:
        logger.debug("delivery pass not started", exc_info=True)


@email_bp.route("/preferences", methods=["GET"])
@token_required
def my_preferences():
    username, _role = _caller()
    if not username:
        return jsonify({"error": "Not signed in"}), 401
    return jsonify({"username": username,
                    "preferences": _with_conn(lambda c: email_outbox.preferences(c, username))})


@email_bp.route("/preferences", methods=["PUT"])
@token_required
def set_my_preferences():
    """Body: ``{"category": bool, ...}``. Only the caller's own rows."""
    username, _role = _caller()
    if not username:
        return jsonify({"error": "Not signed in"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "Send a JSON object of category: true/false"}), 400
    if any(not isinstance(v, bool) or not str(k).strip() or len(str(k)) > 64
           for k, v in data.items()):
        return jsonify({"error": "Each value must be true or false"}), 400

    def body(conn):
        for category, enabled in data.items():
            email_outbox.set_preference(conn, username, str(category).strip(), enabled)
        return email_outbox.preferences(conn, username)
    return jsonify({"username": username, "preferences": _with_conn(body)})
