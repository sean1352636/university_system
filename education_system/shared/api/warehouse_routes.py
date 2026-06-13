"""Read-only cross-system reporting warehouse API.

Surfaces :class:`education_system.shared.analytics.warehouse.Warehouse` over
HTTP — org-wide questions no single system can answer (headcounts across
all phases, the nursery→university retention funnel, phase-to-phase
progression rates).

Routes (registered under ``/api/v1/warehouse``), all staff-gated and
read-only:

* ``GET /summary``      — everything in one call
* ``GET /headcount``    — live local headcount per system
* ``GET /retention``    — how many journeys reached each phase
* ``GET /progression``  — phase-to-phase conversion rates
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from education_system.shared.api.auth import role_required

logger = logging.getLogger(__name__)

warehouse_bp = Blueprint("warehouse", __name__, url_prefix="/api/warehouse")

# Org-wide stats are staff-level; parents/students are refused.
_STAFF_ROLES = ("admin", "staff", "teacher")


def init_warehouse_routes() -> None:
    """Hook for app-startup symmetry with the other route modules."""
    logger.info("Warehouse (cross-system reporting) routes initialised.")


def _warehouse():
    from education_system.shared.analytics.warehouse import Warehouse
    return Warehouse()


def _safe(fn, label):
    try:
        return jsonify(fn()), 200
    except Exception:
        logger.exception("Warehouse %s failed", label)
        return jsonify({"error": f"Failed to build {label}"}), 500


@warehouse_bp.route("/summary", methods=["GET"])
@role_required(*_STAFF_ROLES)
def summary():
    return _safe(lambda: _warehouse().summary(), "summary")


@warehouse_bp.route("/headcount", methods=["GET"])
@role_required(*_STAFF_ROLES)
def headcount():
    return _safe(lambda: {"headcount": _warehouse().headcount_by_system()},
                 "headcount")


@warehouse_bp.route("/retention", methods=["GET"])
@role_required(*_STAFF_ROLES)
def retention():
    return _safe(lambda: {"retention_funnel": _warehouse().retention_funnel()},
                 "retention funnel")


@warehouse_bp.route("/progression", methods=["GET"])
@role_required(*_STAFF_ROLES)
def progression():
    return _safe(lambda: {"progression_rates": _warehouse().progression_rates()},
                 "progression rates")
