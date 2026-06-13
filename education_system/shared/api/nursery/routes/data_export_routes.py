"""REST API for Nursery Data Export.

Exposes the whitelisted-table listing and CSV export operations (read-only over
the data; export writes CSV files to a server-side directory).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

data_export_bp = Blueprint("nsy_data_export", __name__, url_prefix="/api/data-export")


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


@data_export_bp.route("", methods=["GET"])
@data_export_bp.route("/", methods=["GET"])
@_token_required
def list_exportable_tables():
    """List whitelisted tables that exist, with their live row counts."""
    from education_system.nursery_system.modules.domain.data_export import data_export as data
    rows = data.list_tables()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@data_export_bp.route("/default-dir", methods=["GET"])
@_token_required
def get_default_dir():
    """Return the dated default export destination directory."""
    from education_system.nursery_system.modules.domain.data_export import data_export as data
    return jsonify({"dir": str(data.default_export_dir())})


@data_export_bp.route("/<table>", methods=["POST"])
@_token_required
def export_one_table(table):
    """Export a single whitelisted table to a CSV file.

    Body (JSON, optional): {"dir": "<destination directory>"}. Defaults to the
    dated default export directory.
    """
    from education_system.nursery_system.modules.domain.data_export import data_export as data
    payload = request.get_json(silent=True) or {}
    dir_path = payload.get("dir") or str(data.default_export_dir())
    try:
        result = data.export_table(table, dir_path)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except OSError as exc:
        logger.exception("export_table failed")
        return jsonify({"error": str(exc)}), 500
    return jsonify(_dump(result)), 201


@data_export_bp.route("/export-all", methods=["POST"])
@_token_required
def export_all_tables():
    """Export all (or a given list of) whitelisted tables to CSV files.

    Body (JSON, optional): {"dir": "<dir>", "tables": ["pupils", ...]}.
    """
    from education_system.nursery_system.modules.domain.data_export import data_export as data
    payload = request.get_json(silent=True) or {}
    dir_path = payload.get("dir") or str(data.default_export_dir())
    tables = payload.get("tables")
    try:
        result = data.export_all(dir_path, tables=tables)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except OSError as exc:
        logger.exception("export_all failed")
        return jsonify({"error": str(exc)}), 500
    return jsonify(_dump(result)), 201
