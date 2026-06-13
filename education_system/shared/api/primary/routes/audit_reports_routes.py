"""REST API for Primary Audit Reports."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

audit_reports_bp = Blueprint("pri_audit_reports", __name__, url_prefix="/api/audit-reports")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
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
    if isinstance(obj, tuple):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return {k: _dump(v) for k, v in dataclasses.asdict(obj).items()}
    return obj


# ── Report-type catalogue (read-only metadata) ─────────────────────

@audit_reports_bp.route("/types", methods=["GET"])
@_token_required
def list_types():
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    rows = [
        {
            "report_type": rt,
            "label": data.REPORT_LABELS.get(rt, rt),
            "description": data.REPORT_DESCRIPTIONS.get(rt, ""),
        }
        for rt in data.REPORT_TYPES
    ]
    return jsonify({"items": rows, "count": len(rows)}), 200


# ── Saved report definitions (CRUD) ────────────────────────────────

@audit_reports_bp.route("", methods=["GET"])
@audit_reports_bp.route("/", methods=["GET"])
@_token_required
def list_defs():
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    report_type = request.args.get("report_type") or None
    rows = data.list_defs(report_type=report_type)
    return jsonify({"items": _dump(rows), "count": len(rows)}), 200


@audit_reports_bp.route("/<int:def_id>", methods=["GET"])
@_token_required
def get_def(def_id: int):
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    obj = data.get_def(def_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj)), 200


@audit_reports_bp.route("", methods=["POST"])
@audit_reports_bp.route("/", methods=["POST"])
@_token_required
def create_def():
    from education_system.primarysch_system.modules.domain.audit_reports import (
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
def update_def(def_id: int):
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    if data.get_def(def_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_def(def_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 200


@audit_reports_bp.route("/<int:def_id>", methods=["DELETE"])
@_token_required
def delete_def(def_id: int):
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    if not data.delete_def(def_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "def_id": def_id}), 200


# ── Run a report (on-the-fly) ──────────────────────────────────────

@audit_reports_bp.route("/run", methods=["POST"])
@_token_required
def run_report():
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    payload = request.get_json(silent=True) or {}
    report_type = payload.get("report_type")
    if not report_type:
        return jsonify({"error": "report_type is required"}), 400
    try:
        result = data.run_report(
            report_type,
            filters=payload.get("filters"),
            name=payload.get("name"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(result)), 200


@audit_reports_bp.route("/<int:def_id>/run", methods=["POST"])
@_token_required
def run_def(def_id: int):
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    try:
        result = data.run_def(def_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(result)), 200


# ── Saved run snapshots ────────────────────────────────────────────

@audit_reports_bp.route("/runs", methods=["GET"])
@_token_required
def list_runs():
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    report_type = request.args.get("report_type") or None
    def_id_raw = request.args.get("def_id")
    def_id = None
    if def_id_raw not in (None, ""):
        try:
            def_id = int(def_id_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "def_id must be an integer"}), 400
    limit_raw = request.args.get("limit")
    kwargs = {"report_type": report_type, "def_id": def_id}
    if limit_raw not in (None, ""):
        try:
            kwargs["limit"] = int(limit_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "limit must be an integer"}), 400
    rows = data.list_runs(**kwargs)
    return jsonify({"items": _dump(rows), "count": len(rows)}), 200


@audit_reports_bp.route("/runs/<int:run_id>", methods=["GET"])
@_token_required
def get_run(run_id: int):
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    obj = data.get_run(run_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj)), 200


@audit_reports_bp.route("/runs/<int:run_id>", methods=["DELETE"])
@_token_required
def delete_run(run_id: int):
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    if not data.delete_run(run_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "run_id": run_id}), 200


# ── Overview / summary ─────────────────────────────────────────────

@audit_reports_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.audit_reports import (
        audit_reports as data,
    )
    return jsonify(_dump(data.overview())), 200
