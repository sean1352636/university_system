"""REST API for Primary Mobile Dashboard."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

mobile_dashboard_bp = Blueprint("pri_mobile_dashboard", __name__, url_prefix="/api/mobile-dashboard")


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


@mobile_dashboard_bp.route("", methods=["GET"])
@mobile_dashboard_bp.route("/", methods=["GET"])
@_token_required
def get_dashboard():
    from education_system.systems.primary.domain.operations.reporting.mobile_dashboard import (
        mobile_dashboard as data,
    )

    dashboard = data.build_dashboard()
    return jsonify(_dump(dashboard))
