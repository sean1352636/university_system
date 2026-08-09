"""REST API for Primary Trips & Payments."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

trips_bp = Blueprint("pri_trips", __name__, url_prefix="/api/trips")


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


# ── Trips ──────────────────────────────────────────────────────────

@trips_bp.route("", methods=["GET"])
@trips_bp.route("/", methods=["GET"])
@_token_required
def list_trips_view():
    from education_system.systems.primary.domain.finance.trips import trips as data
    try:
        rows = data.list_trips(
            year_group=request.args.get("year_group"),
            status=request.args.get("status"),
            open_only=request.args.get("open_only", "").lower()
            in ("1", "true", "yes"),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@trips_bp.route("/summary", methods=["GET"])
@_token_required
def summary_view():
    from education_system.systems.primary.domain.finance.trips import trips as data
    return jsonify(_dump(data.summary()))


@trips_bp.route("/<int:trip_id>", methods=["GET"])
@_token_required
def get_trip_view(trip_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    obj = data.get_trip(trip_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@trips_bp.route("/<int:trip_id>/view", methods=["GET"])
@_token_required
def view_trip_view(trip_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    obj = data.view_trip(trip_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@trips_bp.route("", methods=["POST"])
@trips_bp.route("/", methods=["POST"])
@_token_required
def create_trip_view():
    from education_system.systems.primary.domain.finance.trips import trips as data
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_trip(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj)), 201


@trips_bp.route("/<int:trip_id>", methods=["PUT"])
@_token_required
def update_trip_view(trip_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    if data.get_trip(trip_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_trip(trip_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj))


@trips_bp.route("/<int:trip_id>", methods=["DELETE"])
@_token_required
def delete_trip_view(trip_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    if not data.delete_trip(trip_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Bookings ───────────────────────────────────────────────────────

@trips_bp.route("/bookings", methods=["GET"])
@_token_required
def list_bookings_view():
    from education_system.systems.primary.domain.finance.trips import trips as data
    trip_id = request.args.get("trip_id", type=int)
    try:
        rows = data.list_bookings(
            trip_id=trip_id,
            student_id=request.args.get("student_id"),
            status=request.args.get("status"),
            active_only=request.args.get("active_only", "").lower()
            in ("1", "true", "yes"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@trips_bp.route("/bookings/<int:booking_id>", methods=["GET"])
@_token_required
def get_booking_view(booking_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    obj = data.get_booking(booking_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@trips_bp.route("/bookings/<int:booking_id>/view", methods=["GET"])
@_token_required
def view_booking_view(booking_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    obj = data.view_booking(booking_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@trips_bp.route("/<int:trip_id>/bookings", methods=["POST"])
@_token_required
def create_booking_view(trip_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_booking(trip_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj)), 201


@trips_bp.route("/bookings/<int:booking_id>", methods=["PUT"])
@_token_required
def update_booking_view(booking_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    if data.get_booking(booking_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_booking(booking_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj))


@trips_bp.route("/bookings/<int:booking_id>", methods=["DELETE"])
@_token_required
def delete_booking_view(booking_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    if not data.delete_booking(booking_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Payments ───────────────────────────────────────────────────────

@trips_bp.route("/payments", methods=["GET"])
@_token_required
def list_payments_view():
    from education_system.systems.primary.domain.finance.trips import trips as data
    try:
        rows = data.list_payments(
            booking_id=request.args.get("booking_id", type=int),
            trip_id=request.args.get("trip_id", type=int),
            student_id=request.args.get("student_id"),
            method=request.args.get("method"),
            status=request.args.get("status"),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@trips_bp.route("/payments/<int:payment_id>", methods=["GET"])
@_token_required
def get_payment_view(payment_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    obj = data.get_payment(payment_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@trips_bp.route("/bookings/<int:booking_id>/payments", methods=["POST"])
@_token_required
def add_payment_view(booking_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.add_payment(booking_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj)), 201


@trips_bp.route("/payments/<int:payment_id>", methods=["PUT"])
@_token_required
def update_payment_view(payment_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    if data.get_payment(payment_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_payment(payment_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj))


@trips_bp.route("/payments/<int:payment_id>", methods=["DELETE"])
@_token_required
def delete_payment_view(payment_id: int):
    from education_system.systems.primary.domain.finance.trips import trips as data
    if not data.delete_payment(payment_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})
