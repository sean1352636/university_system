"""REST API for Secondary School reports."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

reports_bp = Blueprint("sec_reports", __name__, url_prefix="/api/reports")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SCHOOL_API_TOKEN")
            got = request.headers.get("X-School-Token")
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


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── data_export: presets (full CRUD) + jobs (read) + overview ──────

@reports_bp.route("/export/presets", methods=["GET"])
@_token_required
def list_export_presets():
    from education_system.secondarysch_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    rows = data.list_presets()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@reports_bp.route("/export/presets/<key>", methods=["GET"])
@_token_required
def get_export_preset(key):
    from education_system.secondarysch_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    # Numeric path segments are treated as preset ids.
    key_or_id: str | int = int(key) if key.isdigit() else key
    p = data.get_preset(key_or_id)
    if p is None:
        return jsonify({"error": "Preset not found"}), 404
    return jsonify(_dump(p))


@reports_bp.route("/export/presets", methods=["POST"])
@_token_required
def create_export_preset():
    from education_system.secondarysch_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    try:
        p = data.create_preset(_body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(p)), 201


@reports_bp.route("/export/presets/<int:preset_id>", methods=["PUT"])
@_token_required
def update_export_preset(preset_id: int):
    from education_system.secondarysch_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    if data.get_preset(preset_id) is None:
        return jsonify({"error": "Preset not found"}), 404
    try:
        p = data.update_preset(preset_id, _body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(p))


@reports_bp.route("/export/presets/<int:preset_id>", methods=["DELETE"])
@_token_required
def delete_export_preset(preset_id: int):
    from education_system.secondarysch_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    if not data.delete_preset(preset_id):
        return jsonify({"error": "Preset not found or not deletable"}), 404
    return jsonify({"deleted": preset_id})


@reports_bp.route("/export/jobs", methods=["GET"])
@_token_required
def list_export_jobs():
    from education_system.secondarysch_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    preset_key = request.args.get("preset_key") or None
    status = request.args.get("status") or None
    try:
        rows = data.list_jobs(preset_key=preset_key, status=status)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@reports_bp.route("/export/jobs/<int:job_id>", methods=["GET"])
@_token_required
def get_export_job(job_id: int):
    from education_system.secondarysch_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    j = data.get_job(job_id)
    if j is None:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(_dump(j))


@reports_bp.route("/export/overview", methods=["GET"])
@_token_required
def export_overview():
    from education_system.secondarysch_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    return jsonify(_dump(data.overview()))


# ── kpi_dashboard: read-only aggregate snapshot ────────────────────

@reports_bp.route("/kpi/snapshot", methods=["GET"])
@_token_required
def kpi_snapshot():
    from education_system.secondarysch_system.modules.domain.reports.kpi_dashboard import (
        kpi_dashboard as data,
    )
    try:
        window_days = int(request.args.get("window_days", data.DEFAULT_WINDOW_DAYS))
        threshold_pct = float(request.args.get("threshold_pct", data.DEFAULT_THRESHOLD))
    except (TypeError, ValueError):
        return jsonify({"error": "window_days and threshold_pct must be numeric"}), 400
    snap = data.snapshot(window_days=window_days, threshold_pct=threshold_pct)
    return jsonify(_dump(snap))
