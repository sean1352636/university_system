"""Web portal routes: serves the single-page application UI."""

from __future__ import annotations

import os

from flask import Blueprint, make_response, send_from_directory

from education_system.platform.delivery.api.security_headers import document_csp
from education_system.platform.delivery.api.static_files import send_static_asset

web_bp = Blueprint("web", __name__)

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
_STUDENT_PAGES = {
    "timetable": "timetable.html",
    "submissions": "submissions.html",
    "fees": "fees.html",
    "support": "support.html",
    "graduation": "graduation.html",
}
_OPERATIONS_PAGES = {
    "cases": "operations-cases.html",
    "identity": "operations-identity.html",
    "connectors": "operations-connectors.html",
    "timetabling": "operations-timetabling.html",
    "pgr": "operations-pgr.html",
    "programmes": "operations-programmes.html",
}


def _send_index():
    """Read and return the index.html with appropriate headers."""
    response = make_response(send_from_directory(_STATIC_DIR, "index.html"))
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    # Override CSP so the portal page can load its own static JS/CSS.
    response._custom_csp = True
    # The portal shell is deliberately embeddable within its own origin, so it
    # relaxes frame-ancestors to 'self' — but only that. The old policy omitted
    # frame-ancestors, base-uri and form-action entirely, which left the page
    # frameable by any origin and open to a <base> or form-action hijack.
    response.headers["Content-Security-Policy"] = document_csp(frame_ancestors="'self'")
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


@web_bp.route("/portal")
@web_bp.route("/portal/")
def portal():
    """Serve the web portal single-page application."""
    return _send_index()


@web_bp.route("/portal/journey")
@web_bp.route("/portal/journey/")
def applicant_journey():
    """Serve the accessible applicant-to-enrolment journey."""
    response = make_response(send_from_directory(_STATIC_DIR, "journey.html"))
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response._custom_csp = True
    response.headers["Content-Security-Policy"] = document_csp()
    return response


@web_bp.route("/portal/student/<page>")
@web_bp.route("/portal/student/<page>/")
def student_page(page):
    """Serve one of the task-focused student portal pages."""
    filename = _STUDENT_PAGES.get(page)
    if filename is None:
        return {"error": "Page not found"}, 404
    response = make_response(send_from_directory(_STATIC_DIR, filename))
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response._custom_csp = True
    response.headers["Content-Security-Policy"] = document_csp()
    return response


@web_bp.route("/portal/operations")
@web_bp.route("/portal/operations/")
def operations_hub():
    return _send_operations_page("operations.html")


@web_bp.route("/portal/operations/<page>")
@web_bp.route("/portal/operations/<page>/")
def operations_page(page):
    filename = _OPERATIONS_PAGES.get(page)
    if filename is None:
        return {"error": "Page not found"}, 404
    return _send_operations_page(filename)


@web_bp.route("/portal/operations/assets/<path:filename>")
def operations_asset(filename):
    """Serve the allow-listed operations CSS and JavaScript."""
    allowed = {
        "css/journey.css": os.path.join(_STATIC_DIR, "css"),
        "js/student_pages.js": os.path.join(_STATIC_DIR, "js"),
        "js/institutional_pages.js": os.path.join(_STATIC_DIR, "js"),
    }
    directory = allowed.get(filename)
    if directory is None:
        return {"error": "Asset not found"}, 404
    return send_static_asset(directory, os.path.basename(filename))


def _send_operations_page(filename: str):
    response = make_response(send_from_directory(_STATIC_DIR, filename))
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response._custom_csp = True
    response.headers["Content-Security-Policy"] = document_csp()
    return response
