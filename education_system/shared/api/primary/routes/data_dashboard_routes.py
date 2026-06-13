"""REST API for Primary Data Dashboard."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

data_dashboard_bp = Blueprint("pri_data_dashboard", __name__, url_prefix="/api/data-dashboard")


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


def _window_days():
    raw = request.args.get("window_days")
    if raw is None:
        from education_system.primarysch_system.modules.domain.data_dashboard import (
            data_dashboard as data,
        )
        return data.DEFAULT_WINDOW_DAYS
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


# ── Read-only dashboard module: build_panels(*, window_days) -> DataSnapshot ──


@data_dashboard_bp.route("", methods=["GET"])
@data_dashboard_bp.route("/", methods=["GET"])
@_token_required
def get_dashboard():
    from education_system.primarysch_system.modules.domain.data_dashboard import (
        data_dashboard as data,
    )
    days = _window_days()
    if days is None:
        return jsonify({"error": "window_days must be an integer"}), 400
    snapshot = data.build_panels(window_days=days)
    return jsonify(_dump(snapshot))


@data_dashboard_bp.route("/panels", methods=["GET"])
@_token_required
def list_panels():
    from education_system.primarysch_system.modules.domain.data_dashboard import (
        data_dashboard as data,
    )
    days = _window_days()
    if days is None:
        return jsonify({"error": "window_days must be an integer"}), 400
    snapshot = data.build_panels(window_days=days)
    rows = snapshot.panels
    return jsonify({"items": _dump(rows), "count": len(rows)})
