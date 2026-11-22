"""The public page behind a postgraduate reference request.

``GET  /admissions-references/<token>`` shows the referee a short form;
``POST /admissions-references/<token>`` records the reference (text and/or
an attached letter). Unauthenticated by design - the referee follows a
link in an e-mail - so the token is the credential: random, stored only as
a hash, single use and time-limited (``admissions_postgraduate``). Rate
limited per IP.

Mounted under ``/api/v1/university``, which is where
``admissions_postgraduate.reference_url`` points.
"""

from __future__ import annotations

import html
import logging

from flask import Blueprint, Response, request

from education_system.platform.delivery.api.rate_limiter import rate_limiter
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_postgraduate as postgraduate,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)

logger = logging.getLogger(__name__)

admission_reference_bp = Blueprint(
    "admission_references", __name__, url_prefix="/api/admissions-references")

_INVALID = "This link is not valid, has expired or has already been used."


def _page(title: str, body_html: str, status: int = 200) -> Response:
    page = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title></head><body "
            f"style='font-family:sans-serif;max-width:720px;margin:2em auto;padding:0 16px'>"
            f"<h1>{html.escape(title)}</h1>{body_html}</body></html>")
    response = Response(page, status=status, mimetype="text/html")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@admission_reference_bp.route("/<token>", methods=["GET"])
@rate_limiter.limit("30/minute")
def reference_form(token: str):
    info = postgraduate.referee_for_token(token[:200])
    if info is None:
        return _page("Link not recognised", f"<p>{html.escape(_INVALID)}</p>", 404)
    intro = (f"<p>Dear {html.escape(info['referee_name'])}, thank you for supporting "
             f"<strong>{html.escape(info['applicant'] or 'the applicant')}</strong>'s "
             f"application for {html.escape(info['programme'] or 'postgraduate study')}.</p>"
             "<p>Write your reference below and/or attach a signed letter "
             "(PDF, Word or image, up to 20 MB). This link can be used once.</p>")
    form = ("<form method='post' enctype='multipart/form-data'>"
            "<p><textarea name='reference' rows='14' style='width:100%'></textarea></p>"
            "<p><input type='file' name='letter'></p>"
            "<p><button type='submit'>Submit reference</button></p></form>")
    return _page("Postgraduate reference", intro + form)


@admission_reference_bp.route("/<token>", methods=["POST"])
@rate_limiter.limit("10/minute")
def submit_reference(token: str):
    upload = request.files.get("letter")
    data = upload.read() if upload and upload.filename else None
    try:
        result = postgraduate.submit_reference_by_token(
            token[:200], request.form.get("reference", "")[:20000],
            file_bytes=data, filename=upload.filename if data else "")
    except AdmissionsBoundaryError as exc:
        return _page("Reference not received", f"<p>{html.escape(str(exc))}</p>", 400)
    except Exception:
        logger.exception("Reference submission failed")
        return _page("Something went wrong", "<p>Please try again later.</p>", 500)
    if not result.get("ok"):
        return _page("Reference not received", f"<p>{html.escape(result['message'])}</p>", 400)
    return _page("Reference received", f"<p>{html.escape(result['message'])}</p>")
