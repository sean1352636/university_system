"""REST API for Nursery Daily Register.

Exposes the per-date "who's in today" register: list active children for a date,
day summary, mark one child, and bulk mark-all-present.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

daily_register_bp = Blueprint("nsy_daily_register", __name__, url_prefix="/api/daily-register")


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


@daily_register_bp.route("", methods=["GET"])
@daily_register_bp.route("/", methods=["GET"])
@_token_required
def list_register():
    """List every active child for a date (defaults to today)."""
    from education_system.nursery_system.modules.domain.daily_register import (
        daily_register as data,
    )

    attend_date = request.args.get("date") or data.today()
    try:
        rows = data.register_for_date(attend_date)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows), "date": attend_date})


@daily_register_bp.route("/today", methods=["GET"])
@_token_required
def get_today():
    """Return today's ISO date string."""
    from education_system.nursery_system.modules.domain.daily_register import (
        daily_register as data,
    )

    return jsonify({"date": data.today()})


@daily_register_bp.route("/<attend_date>", methods=["GET"])
@_token_required
def get_register_for_date(attend_date):
    """List active children for a specific date."""
    from education_system.nursery_system.modules.domain.daily_register import (
        daily_register as data,
    )

    try:
        rows = data.register_for_date(attend_date)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows), "date": attend_date})


@daily_register_bp.route("/<attend_date>/summary", methods=["GET"])
@_token_required
def get_summary(attend_date):
    """Counts per status for a date, plus not_marked and total."""
    from education_system.nursery_system.modules.domain.daily_register import (
        daily_register as data,
    )

    try:
        summary = data.day_summary(attend_date)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"date": attend_date, "summary": summary})


@daily_register_bp.route("/mark", methods=["POST"])
@_token_required
def mark_child():
    """Mark one child's all-day register row for a date.

    Body: {"pupil_id", "date", "status", optional: arrival_time, departure_time,
    absence_reason, notes, room}.
    """
    from education_system.nursery_system.modules.domain.daily_register import (
        daily_register as data,
    )

    payload = request.get_json(silent=True) or {}
    pupil_id = payload.get("pupil_id")
    attend_date = payload.get("date") or payload.get("attend_date")
    status = payload.get("status")
    if not pupil_id or not attend_date or not status:
        return jsonify({"error": "pupil_id, date and status are required"}), 400
    extra = {
        k: payload[k]
        for k in ("arrival_time", "departure_time", "absence_reason", "notes", "room")
        if k in payload
    }
    try:
        data.mark(pupil_id, attend_date, status, **extra)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"marked": True, "pupil_id": pupil_id, "date": attend_date, "status": status})


@daily_register_bp.route("/<attend_date>/mark-all-present", methods=["POST"])
@_token_required
def mark_all_present(attend_date):
    """Mark every active child not yet marked that date as present."""
    from education_system.nursery_system.modules.domain.daily_register import (
        daily_register as data,
    )

    try:
        count = data.mark_all_present(attend_date)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"date": attend_date, "marked": count})
