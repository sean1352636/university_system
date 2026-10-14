"""REST API for Nursery Occupancy Report.

Read-only aggregate occupancy reporting: per-room occupancy, the count of
unplaced children, and an overall summary.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

occupancy_report_bp = Blueprint(
    "nsy_occupancy_report", __name__, url_prefix="/api/occupancy-report")


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


@occupancy_report_bp.route("", methods=["GET"])
@occupancy_report_bp.route("/", methods=["GET"])
@_token_required
def list_rooms_route():
    from education_system.systems.nursery.domain.operations.reporting.occupancy_report import (
        occupancy_report as data,
    )
    rows = data.list_room_occupancy()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@occupancy_report_bp.route("/unplaced", methods=["GET"])
@_token_required
def unplaced_route():
    from education_system.systems.nursery.domain.operations.reporting.occupancy_report import (
        occupancy_report as data,
    )
    return jsonify({"unplaced_children": data.unplaced_children()})


@occupancy_report_bp.route("/summary", methods=["GET"])
@_token_required
def summary_route():
    from education_system.systems.nursery.domain.operations.reporting.occupancy_report import (
        occupancy_report as data,
    )
    return jsonify(_dump(data.summary()))
