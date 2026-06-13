"""REST API for Nursery Ofsted Readiness.

Read-only inspection-readiness report: exposes the computed EYFS welfare
checklist, the roll-up readiness score and a CSV export trigger.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

ofsted_bp = Blueprint("nsy_ofsted", __name__, url_prefix="/api/ofsted")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("NURSERY_API_TOKEN")
            got = request.headers.get("X-Nursery-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe data."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


@ofsted_bp.route("", methods=["GET"])
@ofsted_bp.route("/", methods=["GET"])
@_token_required
def list_checks():
    """Return the full Ofsted readiness checklist."""
    from education_system.nursery_system.modules.domain.ofsted import ofsted as data

    rows = data.readiness()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@ofsted_bp.route("/score", methods=["GET"])
@_token_required
def get_score():
    """Return the rolled-up readiness grade/score."""
    from education_system.nursery_system.modules.domain.ofsted import ofsted as data

    return jsonify(data.score())


@ofsted_bp.route("/export", methods=["POST"])
@_token_required
def export_csv():
    """Write the readiness checklist to CSV and return path + row count."""
    from education_system.nursery_system.modules.domain.ofsted import ofsted as data

    payload = request.get_json(silent=True) or {}
    path = payload.get("path")
    try:
        result = data.export_csv(path)
    except OSError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
