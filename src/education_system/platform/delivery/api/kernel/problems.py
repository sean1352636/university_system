"""RFC 7807 ``application/problem+json`` payloads.

One shape for every error the API returns, so a client can handle
failures without special-casing each endpoint. Today the same condition
is reported three different ways depending on which layer caught it::

    {"error": "Invalid credentials"}                        shared auth
    {"error": "Forbidden", "status": 403}                   university
    {"error": "Internal server error", "correlation_id": …} the handler

RFC 7807 gives them one envelope::

    {
      "type":     "https://.../problems/forbidden",
      "title":    "Forbidden",
      "status":   403,
      "detail":   "You do not have access to this student record.",
      "instance": "/api/v1/university/students/42",
      "trace_id": "36739411e33e4f25"
    }

``type`` is a stable identifier a client can branch on; ``title`` is the
same for every instance of that type; ``detail`` is specific to this
occurrence and is the only field that should ever quote request data.

Keep ``detail`` free of anything the caller is not already entitled to
see. "No student with id 42" tells an unauthorised caller that record 42
exists — prefer the same wording for missing and forbidden where the
distinction itself is sensitive.
"""

from __future__ import annotations

from typing import Any

from flask import jsonify, request

#: Base for ``type`` URIs. Not required to resolve, but it must be stable —
#: clients match on it.
PROBLEM_BASE = "https://education-system.invalid/problems"

CONTENT_TYPE = "application/problem+json"

#: Canonical titles. A status without an entry falls back to "Error".
TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    413: "Payload Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


def problem_dict(status: int, detail: str | None = None, *,
                 title: str | None = None,
                 type_slug: str | None = None,
                 instance: str | None = None,
                 trace_id: str | None = None,
                 **extra: Any) -> dict:
    """Build a problem payload as a plain dict."""
    resolved_title = title or TITLES.get(status, "Error")
    slug = type_slug or resolved_title.lower().replace(" ", "-")
    body: dict[str, Any] = {
        "type": f"{PROBLEM_BASE}/{slug}",
        "title": resolved_title,
        "status": int(status),
    }
    if detail:
        body["detail"] = detail
    # Default the instance to the current path when there is a request in
    # flight; a problem raised outside one simply omits it.
    if instance is None:
        try:
            instance = request.path
        except RuntimeError:
            instance = None
    if instance:
        body["instance"] = instance
    if trace_id is None:
        try:
            from flask import g
            trace_id = getattr(g, "request_id", None)
        except RuntimeError:
            trace_id = None
    if trace_id:
        body["trace_id"] = trace_id
    body.update({k: v for k, v in extra.items() if v is not None})
    # Compatibility shim. Existing clients — including the portal's
    # EduPortal.apiFetch, which does `data.error || "HTTP " + status` — read a
    # top-level "error" string. Emitting the problem envelope without it would
    # turn every readable message into "HTTP 400". Remove once no client reads
    # it; the canonical fields are title/detail.
    body.setdefault("error", detail or resolved_title)
    return body


def problem(status: int, detail: str | None = None, **kwargs):
    """Build a Flask ``(response, status)`` pair carrying a problem body."""
    response = jsonify(problem_dict(status, detail, **kwargs))
    response.status_code = int(status)
    response.mimetype = CONTENT_TYPE
    return response, int(status)


def validation_problem(errors: dict[str, str], detail: str | None = None):
    """422 with a per-field breakdown under ``errors``."""
    return problem(
        422,
        detail or "One or more fields are invalid.",
        type_slug="validation-failed",
        errors=errors,
    )


__all__ = ["PROBLEM_BASE", "CONTENT_TYPE", "TITLES",
           "problem", "problem_dict", "validation_problem"]
