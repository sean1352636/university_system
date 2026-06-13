"""REST API for Nursery Audit Reports.

Exposes saved report-definition CRUD, report runs (snapshots), on-demand
report execution, and an audit overview built on the activity feed.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

audit_reports_bp = Blueprint("nsy_audit_reports", __name__, url_prefix="/api/audit-reports")


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


# ── Saved report definitions ──────────────────────────────────────

@audit_reports_bp.route("", methods=["GET"])
@_token_required
def list_definitions():
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    report_type = request.args.get("report_type") or None
    rows = data.list_defs(report_type=report_type)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@audit_reports_bp.route("/<int:def_id>", methods=["GET"])
@_token_required
def get_definition(def_id):
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    obj = data.get_def(def_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@audit_reports_bp.route("", methods=["POST"])
@_token_required
def create_definition():
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_def(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@audit_reports_bp.route("/<int:def_id>", methods=["PUT"])
@_token_required
def update_definition(def_id):
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    if data.get_def(def_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_def(def_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@audit_reports_bp.route("/<int:def_id>", methods=["DELETE"])
@_token_required
def delete_definition(def_id):
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    if not data.delete_def(def_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "def_id": def_id})


# ── On-demand report execution ────────────────────────────────────

@audit_reports_bp.route("/run", methods=["POST"])
@_token_required
def run_report():
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    payload = request.get_json(silent=True) or {}
    report_type = payload.get("report_type")
    try:
        result = data.run_report(
            report_type,
            filters=payload.get("filters"),
            name=payload.get("name"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(result))


@audit_reports_bp.route("/<int:def_id>/run", methods=["POST"])
@_token_required
def run_definition(def_id):
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    try:
        result = data.run_def(def_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(result))


# ── Run snapshots ─────────────────────────────────────────────────

@audit_reports_bp.route("/runs", methods=["GET"])
@_token_required
def list_run_snapshots():
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    report_type = request.args.get("report_type") or None
    def_id = request.args.get("def_id", type=int)
    rows = data.list_runs(report_type=report_type, def_id=def_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@audit_reports_bp.route("/runs/<int:run_id>", methods=["GET"])
@_token_required
def get_run_snapshot(run_id):
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    obj = data.get_run(run_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@audit_reports_bp.route("/runs/<int:run_id>", methods=["DELETE"])
@_token_required
def delete_run_snapshot(run_id):
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    if not data.delete_run(run_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "run_id": run_id})


# ── Summary ───────────────────────────────────────────────────────

@audit_reports_bp.route("/overview", methods=["GET"])
@_token_required
def get_overview():
    from education_system.nursery_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    return jsonify(_dump(data.overview()))
