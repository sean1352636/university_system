"""REST API for Sixth Form Reports.

Exposes two reports submodules:
* ``data_export`` — CRUD over user-defined export presets, plus read-only
  access to export jobs, the export overview and the dataset registry.
* ``kpi_dashboard`` — read-only headline-metric snapshot.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

reports_bp = Blueprint("sf_reports", __name__, url_prefix="/api/sixthform/reports")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SIXTHFORM_API_TOKEN")
            got = request.headers.get("X-Sixthform-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe dicts."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


# ── data_export: presets (CRUD) ───────────────────────────────────

@reports_bp.route("/export/presets", methods=["GET"])
@_token_required
def list_export_presets():
    from education_system.sixthform_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    rows = data.list_presets()
    return jsonify({"presets": _dump(rows), "count": len(rows)})


@reports_bp.route("/export/presets/<key_or_id>", methods=["GET"])
@_token_required
def get_export_preset(key_or_id):
    from education_system.sixthform_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    lookup: str | int = int(key_or_id) if key_or_id.isdigit() else key_or_id
    preset = data.get_preset(lookup)
    if preset is None:
        return jsonify({"error": "Preset not found"}), 404
    return jsonify(_dump(preset))


@reports_bp.route("/export/presets", methods=["POST"])
@_token_required
def create_export_preset():
    from education_system.sixthform_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        preset = data.create_preset(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(preset)), 201


@reports_bp.route("/export/presets/<int:preset_id>", methods=["PUT"])
@_token_required
def update_export_preset(preset_id: int):
    from education_system.sixthform_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        preset = data.update_preset(preset_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(preset))


@reports_bp.route("/export/presets/<int:preset_id>", methods=["DELETE"])
@_token_required
def delete_export_preset(preset_id: int):
    from education_system.sixthform_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    if not data.delete_preset(preset_id):
        return jsonify({"error": "Preset not found or not deletable"}), 404
    return jsonify({"deleted": preset_id})


# ── data_export: jobs / overview / datasets (read-only) ───────────

@reports_bp.route("/export/jobs", methods=["GET"])
@_token_required
def list_export_jobs():
    from education_system.sixthform_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    preset_key = request.args.get("preset_key")
    status = request.args.get("status")
    try:
        limit = int(request.args.get("limit", 200))
    except (TypeError, ValueError):
        limit = 200
    try:
        rows = data.list_jobs(preset_key=preset_key, status=status, limit=limit)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"jobs": _dump(rows), "count": len(rows)})


@reports_bp.route("/export/jobs/<int:job_id>", methods=["GET"])
@_token_required
def get_export_job(job_id: int):
    from education_system.sixthform_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    job = data.get_job(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(_dump(job))


@reports_bp.route("/export/overview", methods=["GET"])
@_token_required
def export_overview():
    from education_system.sixthform_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    return jsonify(_dump(data.overview()))


@reports_bp.route("/export/datasets", methods=["GET"])
@_token_required
def export_datasets():
    from education_system.sixthform_system.modules.domain.reports.data_export import (
        data_export as data,
    )
    pairs = data.available_datasets()
    rows = [{"key": k, "label": label} for k, label in pairs]
    return jsonify({"datasets": rows, "count": len(rows)})


# ── kpi_dashboard (read-only) ─────────────────────────────────────

@reports_bp.route("/kpi/snapshot", methods=["GET"])
@_token_required
def kpi_snapshot():
    from education_system.sixthform_system.modules.domain.reports.kpi_dashboard import (
        kpi_dashboard as data,
    )
    kwargs = {}
    if request.args.get("window_days") is not None:
        try:
            kwargs["window_days"] = int(request.args["window_days"])
        except (TypeError, ValueError):
            return jsonify({"error": "window_days must be an integer"}), 400
    if request.args.get("threshold_pct") is not None:
        try:
            kwargs["threshold_pct"] = float(request.args["threshold_pct"])
        except (TypeError, ValueError):
            return jsonify({"error": "threshold_pct must be a number"}), 400
    return jsonify(_dump(data.snapshot(**kwargs)))
