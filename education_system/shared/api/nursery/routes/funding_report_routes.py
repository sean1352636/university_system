"""REST API for Nursery Funding Report.

Read-only HTTP access to the computed funding report: entitlement breakdown,
claims detail list and roll-up summaries over the nursery funding tables.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

funding_report_bp = Blueprint("nsy_funding_report", __name__, url_prefix="/api/funding-report")


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


@funding_report_bp.route("", methods=["GET"])
@funding_report_bp.route("/", methods=["GET"])
@_token_required
def list_claims_endpoint():
    """List all funding claims (the report's detail rows)."""
    from education_system.nursery_system.modules.domain.funding_report import (
        funding_report as data,
    )
    rows = data.list_claims()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@funding_report_bp.route("/claims", methods=["GET"])
@_token_required
def claims_endpoint():
    """Claims detail list (alias of the root listing)."""
    from education_system.nursery_system.modules.domain.funding_report import (
        funding_report as data,
    )
    rows = data.list_claims()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@funding_report_bp.route("/entitlements", methods=["GET"])
@_token_required
def entitlements_endpoint():
    """Per-entitlement roll-up over active funded-hours records."""
    from education_system.nursery_system.modules.domain.funding_report import (
        funding_report as data,
    )
    rows = data.entitlement_breakdown()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@funding_report_bp.route("/summary", methods=["GET"])
@_token_required
def summary_endpoint():
    """Headline roll-up across funded hours records and claims."""
    from education_system.nursery_system.modules.domain.funding_report import (
        funding_report as data,
    )
    return jsonify(_dump(data.summary()))


@funding_report_bp.route("/claims-summary", methods=["GET"])
@_token_required
def claims_summary_endpoint():
    """Claims totals by status and by funding period."""
    from education_system.nursery_system.modules.domain.funding_report import (
        funding_report as data,
    )
    return jsonify(_dump(data.claims_summary()))
