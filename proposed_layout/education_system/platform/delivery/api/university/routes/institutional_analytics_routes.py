"""Institutional analytics routes: computed cross-module aggregate metrics.

Read-only endpoints backed by
``InstitutionalAnalyticsService`` (enrolment, retention, module
performance, course capacity, finance, demographics). These surface
institution-wide figures — including finance and whole-cohort data — so
they are restricted to non-student roles.
"""
from __future__ import annotations

import functools
import logging

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.systems.university.domain.operations.reporting.institutional_analytics.services.institutional_analytics_service import (  # noqa: E501
    InstitutionalAnalyticsError,
    InstitutionalAnalyticsService,
)

logger = logging.getLogger(__name__)

institutional_analytics_bp = Blueprint(
    "institutional_analytics", __name__, url_prefix="/api/analytics"
)

_service = InstitutionalAnalyticsService()


def staff_only(fn):
    """Deny the ``student`` role. Must be used after ``@token_required``."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        role = (g.get("current_user", {}) or {}).get("role", "student")
        if role == "student":
            return jsonify({"error": "Staff access required", "status": 403}), 403
        return fn(*args, **kwargs)

    return wrapper


def _handle(section_fn, **kwargs):
    """Run a service call and wrap the result / error in a JSON response."""
    try:
        return jsonify({"data": section_fn(**kwargs)})
    except InstitutionalAnalyticsError as exc:
        # Source data unavailable (e.g. table absent) — 404 is the closest fit.
        return jsonify({"error": str(exc), "status": 404}), 404
    except Exception:  # pragma: no cover - defensive
        logger.exception("institutional analytics endpoint failed")
        return jsonify({"error": "internal analytics error", "status": 500}), 500


@institutional_analytics_bp.route("/overview", methods=["GET"])
@token_required
@staff_only
def overview():
    # institutional_overview never raises — it reports failures under "errors".
    return jsonify({"data": _service.institutional_overview()})


@institutional_analytics_bp.route("/enrollment", methods=["GET"])
@token_required
@staff_only
def enrollment():
    return _handle(_service.enrollment_summary)


@institutional_analytics_bp.route("/retention", methods=["GET"])
@token_required
@staff_only
def retention():
    return _handle(_service.retention_metrics)


@institutional_analytics_bp.route("/modules", methods=["GET"])
@token_required
@staff_only
def modules():
    limit = request.args.get("limit", type=int)
    return _handle(_service.module_performance, limit=limit)


@institutional_analytics_bp.route("/capacity", methods=["GET"])
@token_required
@staff_only
def capacity():
    return _handle(_service.course_capacity)


@institutional_analytics_bp.route("/finance", methods=["GET"])
@token_required
@staff_only
def finance():
    return _handle(_service.financial_summary)


@institutional_analytics_bp.route("/demographics", methods=["GET"])
@token_required
@staff_only
def demographics():
    return _handle(_service.demographics)
