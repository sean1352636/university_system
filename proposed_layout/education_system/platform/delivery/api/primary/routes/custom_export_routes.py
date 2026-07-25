"""REST API for Primary Custom Export (read-only export engine)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

custom_export_bp = Blueprint("pri_custom_export", __name__, url_prefix="/api/custom-export")


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


def _data():
    from education_system.systems.primary.domain.operations.reporting.custom_export import (
        custom_export as data,
    )
    return data


def _csv_list(value):
    if value is None:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or None


def _collect_filters(data, spec):
    """Pull recognised filter keys for ``spec`` out of the query string."""
    filters = {}
    for key in getattr(spec, "filter_keys", []) or []:
        val = request.args.get(key)
        if val not in (None, ""):
            filters[key] = val
    return filters


# ── List all datasets ─────────────────────────────────────────────


@custom_export_bp.route("", methods=["GET"])
@custom_export_bp.route("/", methods=["GET"])
@_token_required
def list_datasets():
    data = _data()
    rows = data.list_datasets()
    items = [
        {
            "key": d.key,
            "label": d.label,
            "description": d.description,
            "columns": [{"key": k, "header": h} for k, h in d.columns],
            "filter_keys": list(d.filter_keys),
        }
        for d in rows
    ]
    return jsonify({"items": items, "count": len(items)})


# ── Supported formats ─────────────────────────────────────────────


@custom_export_bp.route("/formats", methods=["GET"])
@_token_required
def list_formats():
    data = _data()
    fmts = list(data.FORMATS)
    return jsonify({"items": fmts, "count": len(fmts), "default": data.DEFAULT_FORMAT})


# ── Get a single dataset spec ─────────────────────────────────────


@custom_export_bp.route("/<key>", methods=["GET"])
@_token_required
def get_dataset(key):
    data = _data()
    try:
        spec = data.get_dataset(key)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(
        {
            "key": spec.key,
            "label": spec.label,
            "description": spec.description,
            "columns": [{"key": k, "header": h} for k, h in spec.columns],
            "filter_keys": list(spec.filter_keys),
        }
    )


# ── Preview rows for a dataset ────────────────────────────────────


@custom_export_bp.route("/<key>/preview", methods=["GET"])
@_token_required
def preview_dataset(key):
    data = _data()
    try:
        spec = data.get_dataset(key)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    columns = _csv_list(request.args.get("columns"))
    filters = _collect_filters(data, spec)
    try:
        limit = int(request.args.get("limit", 10))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400
    try:
        headers, rows = data.preview(
            spec, columns=columns, filters=filters, limit=limit
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "dataset": spec.key,
            "headers": headers,
            "items": rows,
            "count": len(rows),
        }
    )


# ── Render a dataset to an export string ──────────────────────────


@custom_export_bp.route("/<key>/render", methods=["GET"])
@_token_required
def render_dataset(key):
    data = _data()
    try:
        spec = data.get_dataset(key)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    fmt = request.args.get("fmt", data.DEFAULT_FORMAT)
    columns = _csv_list(request.args.get("columns"))
    filters = _collect_filters(data, spec)
    limit_raw = request.args.get("limit")
    try:
        limit = int(limit_raw) if limit_raw not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400
    try:
        body = data.render(
            spec, fmt=fmt, columns=columns, filters=filters, limit=limit
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"dataset": spec.key, "fmt": fmt.lower().strip(), "body": body})
