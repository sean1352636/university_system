"""REST API for Primary KPI Dashboard."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

kpi_dashboard_bp = Blueprint("pri_kpi_dashboard", __name__, url_prefix="/api/kpi-dashboard")


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


def _int_arg(name, default):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _float_arg(name, default):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


# This module is a read-only headline-metric dashboard. It exposes no schema
# and no CRUD; the only public entrypoint is `snapshot()`, which returns a
# `Snapshot` dataclass containing a list of `Tile` dataclasses. Hence GET only.


@kpi_dashboard_bp.route("", methods=["GET"])
@kpi_dashboard_bp.route("/", methods=["GET"])
@_token_required
def get_snapshot():
    from education_system.systems.primary.domain.operations.reporting.kpi_dashboard import (
        kpi_dashboard as data,
    )

    window_days = _int_arg("window_days", data.DEFAULT_WINDOW_DAYS)
    threshold_pct = _float_arg("threshold_pct", data.DEFAULT_THRESHOLD)
    snap = data.snapshot(window_days=window_days, threshold_pct=threshold_pct)
    return jsonify(_dump(snap))


@kpi_dashboard_bp.route("/tiles", methods=["GET"])
@_token_required
def list_tiles():
    from education_system.systems.primary.domain.operations.reporting.kpi_dashboard import (
        kpi_dashboard as data,
    )

    window_days = _int_arg("window_days", data.DEFAULT_WINDOW_DAYS)
    threshold_pct = _float_arg("threshold_pct", data.DEFAULT_THRESHOLD)
    snap = data.snapshot(window_days=window_days, threshold_pct=threshold_pct)
    rows = snap.tiles
    return jsonify({"items": _dump(rows), "count": len(rows)})
