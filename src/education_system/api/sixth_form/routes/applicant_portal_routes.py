"""Applicant self-service portal API for the Sixth Form.

Mounted at ``/api/v1/sixthform/applicant-portal``. Like the public
application form it needs no staff token: an applicant signs in with
their reference (or applicant id), date of birth and a one-time code
e-mailed to them (see ``domain/admissions/applicant_portal.py``), and
then sends the session token as ``Authorization: Bearer <token>``.

Routes (JSON in and out unless noted):

* ``POST   /code``           ``{identifier, dob}`` → 202, always the same
  reply whether or not the details matched;
* ``POST   /session``        ``{identifier, dob, code}`` → ``{token}``;
* ``DELETE /session``        sign out;
* ``GET    /status``         the applicant's view of their application;
* ``POST   /offer/accept``   accept the offer;
* ``POST   /offer/decline``  ``{reason}`` (one of ``decline_reasons``);
* ``POST   /documents``      multipart: ``file`` + ``doc_type``;
* ``PUT    /contact``        ``{email?, phone?, address?}``.

Errors carry a short message for the applicant only — never a stack,
an applicant id or anything internal. Every response is ``no-store``.
The client address for rate limiting follows the same trusted-proxy rule
as the application form (``applications_routes.client_ip``).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque

from flask import Blueprint, jsonify, request

from education_system.api.sixth_form.routes.applications_routes import (
    client_ip,
)

logger = logging.getLogger(__name__)

applicant_portal_bp = Blueprint(
    "sf_applicant_portal", __name__, url_prefix="/api/applicant-portal")

MAX_JSON_BYTES: int = 4 * 1024
#: Multipart overhead allowed on top of the domain's file size limit.
UPLOAD_OVERHEAD_BYTES: int = 64 * 1024
#: In-process burst limit on sign-in calls per client address (the
#: persisted failure limit lives in the domain module).
SIGNIN_BURST_MAX: int = 10
SIGNIN_BURST_WINDOW_SECONDS: int = 600

_hits: dict[str, deque[float]] = {}
_lock = threading.Lock()

_CODE_SENT = ("If those details match an application, we have e-mailed a "
              "one-time code to the address on it. It expires in "
              "{minutes} minutes.")


def _portal():
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_portal,
    )
    return applicant_portal


def _allow(ip: str) -> bool:
    now = time.monotonic()
    with _lock:
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] > SIGNIN_BURST_WINDOW_SECONDS:
            q.popleft()
        if len(q) >= SIGNIN_BURST_MAX:
            return False
        q.append(now)
        if len(_hits) > 10_000:
            for key in [k for k, v in _hits.items() if not v]:
                _hits.pop(key, None)
        return True


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def _json_body() -> dict | None:
    if request.content_length is not None and \
            request.content_length > MAX_JSON_BYTES:
        return None
    raw = request.get_data(cache=False)
    if len(raw) > MAX_JSON_BYTES:
        return None
    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _token() -> str:
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header.startswith("Bearer ") else ""


def _run(fn, *, ok_status: int = 200):
    portal = _portal()
    try:
        result = fn(portal)
    except portal.RateLimited as e:
        return _error(str(e), 429)
    except portal.AuthFailed as e:
        return _error(str(e), 401)
    except portal.PortalError as e:
        return _error(str(e), 400)
    except Exception:
        logger.exception("Applicant portal request failed")
        return _error("Something went wrong — please try again later.", 500)
    if result is None:
        return "", 204
    return jsonify(result), ok_status


@applicant_portal_bp.after_request
def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


@applicant_portal_bp.route("/code", methods=["POST"])
def request_code():
    ip = client_ip()
    if not _allow(ip):
        return _error("Too many attempts — please try again later.", 429)
    body = _json_body()
    if body is None:
        return _error("Send your reference and date of birth as JSON.", 400)
    identifier, dob = body.get("identifier"), body.get("dob")
    if not isinstance(identifier, str) or not isinstance(dob, str):
        return _error("Send your reference and date of birth.", 400)

    def go(portal):
        portal.request_code(identifier, dob, client_ip=ip)
        return {"message": _CODE_SENT.format(
            minutes=portal.CODE_VALID_MINUTES)}
    return _run(go, ok_status=202)


@applicant_portal_bp.route("/session", methods=["POST"])
def sign_in():
    ip = client_ip()
    if not _allow(ip):
        return _error("Too many attempts — please try again later.", 429)
    body = _json_body()
    if body is None:
        return _error("Send your reference, date of birth and code as JSON.",
                      400)
    identifier, dob, code = (body.get("identifier"), body.get("dob"),
                             body.get("code"))
    if not all(isinstance(v, str) for v in (identifier, dob, code)):
        return _error("Send your reference, date of birth and code.", 400)

    def go(portal):
        token = portal.verify_code(identifier, dob, code, client_ip=ip)
        return {"token": token,
                "idle_timeout_minutes": portal.SESSION_IDLE_MINUTES}
    return _run(go)


@applicant_portal_bp.route("/session", methods=["DELETE"])
def sign_out():
    token = _token()
    return _run(lambda portal: portal.sign_out(token))


@applicant_portal_bp.route("/status", methods=["GET"])
def status():
    token = _token()
    return _run(lambda portal: portal.status_view(token))


@applicant_portal_bp.route("/offer/accept", methods=["POST"])
def accept_offer():
    token = _token()
    return _run(lambda portal: portal.accept_offer(token))


@applicant_portal_bp.route("/offer/decline", methods=["POST"])
def decline_offer():
    token = _token()
    body = _json_body()
    reason = body.get("reason") if body else None
    if not isinstance(reason, str):
        return _error("Please choose a reason.", 400)
    return _run(lambda portal: portal.decline_offer(token, reason))


@applicant_portal_bp.route("/documents", methods=["POST"])
def upload_document():
    token = _token()
    portal = _portal()
    limit = portal.MAX_UPLOAD_BYTES + UPLOAD_OVERHEAD_BYTES
    if request.content_length is None or request.content_length > limit:
        return _error("The file is missing or too large.", 413)
    upload = request.files.get("file")
    if upload is None:
        return _error("Attach the file as 'file'.", 400)
    content = upload.stream.read(portal.MAX_UPLOAD_BYTES + 1)
    doc_type = request.form.get("doc_type") or "Other"
    filename = upload.filename or "document"
    return _run(lambda p: p.upload_document(token, filename, content,
                                            doc_type=doc_type),
                ok_status=201)


@applicant_portal_bp.route("/contact", methods=["PUT", "PATCH"])
def update_contact():
    token = _token()
    body = _json_body()
    if body is None:
        return _error("Send the details to change as JSON.", 400)
    unknown = set(body) - {"email", "phone", "address"}
    if unknown:
        return _error("Only email, phone and address can be changed here.",
                      400)
    if any(v is not None and not isinstance(v, str) for v in body.values()):
        return _error("Details must be text.", 400)
    return _run(lambda portal: portal.update_contact(
        token, email=body.get("email"), phone=body.get("phone"),
        address=body.get("address")))
