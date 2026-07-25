"""REST API for Nursery EYFS Compliance.

Read-only HTTP access to the computed EYFS statutory-framework compliance
checklist (checks, per-section summary, overall score, section ordering).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

eyfs_compliance_bp = Blueprint("nsy_eyfs_compliance", __name__, url_prefix="/api/eyfs-compliance")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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


@eyfs_compliance_bp.route("", methods=["GET"])
@eyfs_compliance_bp.route("/", methods=["GET"])
@_token_required
def list_checks():
    """Full EYFS compliance checklist, optionally filtered by ?section / ?status."""
    from education_system.systems.nursery.domain.governance.compliance.eyfs_compliance import (
        eyfs_compliance as data,
    )

    rows = data.compliance()

    section = request.args.get("section")
    status = request.args.get("status")
    if section:
        rows = [c for c in rows if c.section == section]
    if status:
        rows = [c for c in rows if c.status == status]

    return jsonify({"items": _dump(rows), "count": len(rows)})


@eyfs_compliance_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    """Per-section counts of ok / warning / fail / info."""
    from education_system.systems.nursery.domain.governance.compliance.eyfs_compliance import (
        eyfs_compliance as data,
    )

    return jsonify(data.section_summary())


@eyfs_compliance_bp.route("/score", methods=["GET"])
@_token_required
def score():
    """Overall compliance score across all checks."""
    from education_system.systems.nursery.domain.governance.compliance.eyfs_compliance import (
        eyfs_compliance as data,
    )

    return jsonify(data.score())


@eyfs_compliance_bp.route("/sections", methods=["GET"])
@_token_required
def sections():
    """Section labels in their canonical order."""
    from education_system.systems.nursery.domain.governance.compliance.eyfs_compliance import (
        eyfs_compliance as data,
    )

    rows = data.sections_in_order()
    return jsonify({"items": rows, "count": len(rows)})
