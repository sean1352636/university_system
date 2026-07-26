"""Read-only cross-system "single student view" API.

Exposes one learner's entire history across all five systems, keyed on the
canonical ``journey_id`` (or resolved from any system's local student id).
The aggregation lives in
:mod:`education_system.platform.cross_system.student_view`; this module is a
thin Flask surface over it.

Routes (registered under ``/api/v1/journey``):

* ``GET /<journey_id>/overview``
* ``GET /by-student/<system>/<student_id>/overview``

The payload is cross-system PII, so the endpoints are read-only and gated to
staff-level roles: a user who is ``admin``, ``staff`` or ``teacher`` in *any*
system may view a journey (these routes are unscoped, so ``role_required``
checks the role across all of the user's systems). ``parent`` and ``student``
roles are refused.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from education_system.platform.delivery.api.auth import role_required
from education_system.platform.cross_system import student_view

logger = logging.getLogger(__name__)

journey_bp = Blueprint("journey", __name__, url_prefix="/api/journey")

# Staff-level roles permitted to view the cross-system single student view.
_STAFF_ROLES = ("admin", "staff", "teacher")


def init_journey_routes() -> None:
    """Hook for app startup symmetry with the other route modules."""
    logger.info("Journey (single student view) routes initialised.")


@journey_bp.route("/<journey_id>/overview", methods=["GET"])
@role_required(*_STAFF_ROLES)
def journey_overview(journey_id: str):
    """Aggregated cross-system view for one canonical journey."""
    try:
        overview = student_view.build_overview(journey_id)
    except Exception:
        logger.exception("Journey overview failed for %s", journey_id)
        return jsonify({"error": "Failed to build journey overview"}), 500
    if not overview.get("found"):
        return jsonify({"error": "Journey not found",
                        "journey_id": journey_id}), 404
    return jsonify(overview), 200


@journey_bp.route("/by-student/<system>/<student_id>/overview",
                  methods=["GET"])
@role_required(*_STAFF_ROLES)
def journey_overview_by_student(system: str, student_id: str):
    """Resolve a journey from a local student id, then aggregate."""
    try:
        overview = student_view.build_overview_for_student(system, student_id)
    except Exception:
        logger.exception("Journey overview failed for %s/%s",
                         system, student_id)
        return jsonify({"error": "Failed to build journey overview"}), 500
    if not overview.get("found"):
        return jsonify({"error": "No journey for that student",
                        "system": system, "student_id": student_id}), 404
    return jsonify(overview), 200
