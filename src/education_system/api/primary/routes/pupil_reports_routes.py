"""REST API for Primary Pupil Reports."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

pupil_reports_bp = Blueprint(
    "pri_pupil_reports", __name__, url_prefix="/api/pupil-reports"
)


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("PRIMARY_API_TOKEN")
            got = request.headers.get("X-Primary-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _dump_pair(pair):
    """Serialize a (Report, Pupil|None) tuple from list_reports."""
    report, pupil = pair
    return {"report": _dump(report), "pupil": _dump(pupil)}


@pupil_reports_bp.route("", methods=["GET"])
@pupil_reports_bp.route("/", methods=["GET"])
@_token_required
def list_reports():
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    args = request.args
    try:
        rows = data.list_reports(
            academic_year=args.get("academic_year"),
            term=args.get("term"),
            status=args.get("status"),
            pupil_id=args.get("pupil_id"),
            year_group=args.get("year_group"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [_dump_pair(p) for p in rows]
    return jsonify({"items": items, "count": len(items)})


@pupil_reports_bp.route("/<int:report_id>", methods=["GET"])
@_token_required
def get_report(report_id: int):
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    rec = data.get(report_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@pupil_reports_bp.route("", methods=["POST"])
@pupil_reports_bp.route("/", methods=["POST"])
@_token_required
def create_report():
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@pupil_reports_bp.route("/<int:report_id>", methods=["PUT"])
@_token_required
def update_report(report_id: int):
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    if data.get(report_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(report_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@pupil_reports_bp.route("/<int:report_id>", methods=["DELETE"])
@_token_required
def delete_report(report_id: int):
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    if not data.delete(report_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "report_id": report_id})


@pupil_reports_bp.route("/<int:report_id>/publish", methods=["POST"])
@_token_required
def publish_report(report_id: int):
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    if data.get(report_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.publish(report_id, published_on=payload.get("published_on"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@pupil_reports_bp.route("/<int:report_id>/revert", methods=["POST"])
@_token_required
def revert_report(report_id: int):
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    if data.get(report_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.revert_to_draft(report_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@pupil_reports_bp.route("/pupil/<pupil_id>", methods=["GET"])
@_token_required
def list_for_pupil(pupil_id: str):
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    try:
        rows = data.list_for_pupil(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pupil_reports_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    args = request.args
    try:
        result = data.summary(
            academic_year=args.get("academic_year"),
            term=args.get("term"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@pupil_reports_bp.route("/years", methods=["GET"])
@_token_required
def known_years():
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    rows = data.known_years()
    return jsonify({"items": rows, "count": len(rows)})
