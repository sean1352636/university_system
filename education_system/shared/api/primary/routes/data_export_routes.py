"""REST API for Primary Data Export."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

data_export_bp = Blueprint("pri_data_export", __name__, url_prefix="/api/data-export")


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
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


# ── Datasets registry ─────────────────────────────────────────────

@data_export_bp.route("/datasets", methods=["GET"])
@_token_required
def list_datasets():
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    rows = [{"key": k, "label": label} for k, label in data.available_datasets()]
    return jsonify({"items": rows, "count": len(rows)})


# ── Summary ───────────────────────────────────────────────────────

@data_export_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    return jsonify(_dump(data.overview()))


# ── Presets (full CRUD) ───────────────────────────────────────────

@data_export_bp.route("/presets", methods=["GET"])
@data_export_bp.route("/presets/", methods=["GET"])
@_token_required
def list_presets():
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    rows = data.list_presets()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@data_export_bp.route("/presets/<key_or_id>", methods=["GET"])
@_token_required
def get_preset(key_or_id):
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    lookup: str | int = int(key_or_id) if key_or_id.isdigit() else key_or_id
    obj = data.get_preset(lookup)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@data_export_bp.route("/presets", methods=["POST"])
@data_export_bp.route("/presets/", methods=["POST"])
@_token_required
def create_preset():
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_preset(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj)), 201


@data_export_bp.route("/presets/<int:preset_id>", methods=["PUT"])
@_token_required
def update_preset(preset_id):
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    if data.get_preset(preset_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_preset(preset_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj))


@data_export_bp.route("/presets/<int:preset_id>", methods=["DELETE"])
@_token_required
def delete_preset(preset_id):
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    if not data.delete_preset(preset_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "preset_id": preset_id})


# ── Jobs (read + delete) ──────────────────────────────────────────

@data_export_bp.route("/jobs", methods=["GET"])
@data_export_bp.route("/jobs/", methods=["GET"])
@_token_required
def list_jobs():
    from education_system.primarysch_system.modules.domain.data_export import (
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
    return jsonify({"items": _dump(rows), "count": len(rows)})


@data_export_bp.route("/jobs/<int:job_id>", methods=["GET"])
@_token_required
def get_job(job_id):
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    obj = data.get_job(job_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@data_export_bp.route("/jobs/<int:job_id>", methods=["DELETE"])
@_token_required
def delete_job(job_id):
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    remove_files = str(request.args.get("remove_files", "")).lower() in (
        "1", "true", "yes",
    )
    if not data.delete_job(job_id, remove_files=remove_files):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "job_id": job_id})


# ── Run an export (action) ────────────────────────────────────────

@data_export_bp.route("/run", methods=["POST"])
@_token_required
def run_export():
    from education_system.primarysch_system.modules.domain.data_export import (
        data_export as data,
    )
    payload = request.get_json(silent=True) or {}
    preset = payload.get("preset_key_or_id")
    if isinstance(preset, str) and preset.isdigit():
        preset = int(preset)
    output_dir = payload.get("output_dir")
    if preset is None or not output_dir:
        return jsonify(
            {"error": "preset_key_or_id and output_dir are required"}
        ), 400
    try:
        job = data.run_export(
            preset,
            output_dir,
            fmt=payload.get("fmt", data.DEFAULT_FORMAT),
            zip_output=bool(payload.get("zip_output", False)),
            run_by=payload.get("run_by"),
            notes=payload.get("notes"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(job)), 201
