"""REST API for Primary Parents' Evenings."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

parents_evenings_bp = Blueprint(
    "pri_parents_evenings", __name__, url_prefix="/api/parents-evenings"
)


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
    from education_system.systems.primary.domain.operations.communications.parents_evenings import (
        parents_evenings as data,
    )
    return data


# ── Events ────────────────────────────────────────────────────────

@parents_evenings_bp.route("", methods=["GET"])
@parents_evenings_bp.route("/", methods=["GET"])
@_token_required
def list_events():
    data = _data()
    args = request.args
    try:
        rows = data.list_events(
            year_group=args.get("year_group"),
            status=args.get("status"),
            open_only=args.get("open_only", "").lower() in ("1", "true", "yes"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@parents_evenings_bp.route("/summary", methods=["GET"])
@_token_required
def overall_summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@parents_evenings_bp.route("/<int:event_id>", methods=["GET"])
@_token_required
def get_event(event_id: int):
    data = _data()
    row = data.get_event(event_id)
    if row is None:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(_dump(row))


@parents_evenings_bp.route("/<int:event_id>/summary", methods=["GET"])
@_token_required
def event_summary(event_id: int):
    data = _data()
    try:
        return jsonify(_dump(data.summarize_event(event_id)))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404


@parents_evenings_bp.route("", methods=["POST"])
@parents_evenings_bp.route("/", methods=["POST"])
@_token_required
def create_event():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_event(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@parents_evenings_bp.route("/<int:event_id>", methods=["PUT"])
@_token_required
def update_event(event_id: int):
    data = _data()
    if data.get_event(event_id) is None:
        return jsonify({"error": "Event not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_event(event_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@parents_evenings_bp.route("/<int:event_id>", methods=["DELETE"])
@_token_required
def delete_event(event_id: int):
    data = _data()
    if not data.delete_event(event_id):
        return jsonify({"error": "Event not found"}), 404
    return jsonify({"deleted": True, "event_id": event_id})


# ── Bookings ──────────────────────────────────────────────────────

@parents_evenings_bp.route("/bookings", methods=["GET"])
@_token_required
def list_bookings():
    data = _data()
    args = request.args
    event_id = args.get("event_id", type=int)
    try:
        rows = data.list_bookings(
            event_id=event_id,
            student_id=args.get("student_id"),
            staff_id=args.get("staff_id"),
            status=args.get("status"),
            slot_time=args.get("slot_time"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@parents_evenings_bp.route("/bookings/<int:booking_id>", methods=["GET"])
@_token_required
def get_booking(booking_id: int):
    data = _data()
    row = data.get_booking(booking_id)
    if row is None:
        return jsonify({"error": "Booking not found"}), 404
    return jsonify(_dump(row))


@parents_evenings_bp.route("/<int:event_id>/bookings", methods=["POST"])
@_token_required
def create_booking(event_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_booking(event_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@parents_evenings_bp.route("/bookings/<int:booking_id>", methods=["PUT"])
@_token_required
def update_booking(booking_id: int):
    data = _data()
    if data.get_booking(booking_id) is None:
        return jsonify({"error": "Booking not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_booking(booking_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@parents_evenings_bp.route("/bookings/<int:booking_id>", methods=["DELETE"])
@_token_required
def delete_booking(booking_id: int):
    data = _data()
    if not data.delete_booking(booking_id):
        return jsonify({"error": "Booking not found"}), 404
    return jsonify({"deleted": True, "booking_id": booking_id})
