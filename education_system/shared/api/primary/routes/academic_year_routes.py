"""REST API for Primary Academic Year."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

academic_year_bp = Blueprint("pri_academic_year", __name__, url_prefix="/api/academic-year")


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
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _dump(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    return obj


def _data():
    from education_system.primarysch_system.modules.domain.academic_year import (
        academic_year as data,
    )
    return data


# ── Years ──────────────────────────────────────────────────────────

@academic_year_bp.route("", methods=["GET"])
@academic_year_bp.route("/", methods=["GET"])
@_token_required
def list_years():
    data = _data()
    status = request.args.get("status")
    try:
        rows = data.list_years(status=status)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@academic_year_bp.route("/current", methods=["GET"])
@_token_required
def current_year():
    data = _data()
    row = data.current_year()
    if row is None:
        return jsonify({"error": "No current academic year"}), 404
    return jsonify(_dump(row))


@academic_year_bp.route("/<int:year_id>", methods=["GET"])
@_token_required
def get_year(year_id: int):
    data = _data()
    row = data.get_year(year_id)
    if row is None:
        return jsonify({"error": "Academic year not found"}), 404
    return jsonify(_dump(row))


@academic_year_bp.route("/<int:year_id>/summary", methods=["GET"])
@_token_required
def year_summary(year_id: int):
    data = _data()
    try:
        row = data.year_summary(year_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(row))


@academic_year_bp.route("", methods=["POST"])
@academic_year_bp.route("/", methods=["POST"])
@_token_required
def create_year():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_year(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@academic_year_bp.route("/<int:year_id>", methods=["PUT"])
@_token_required
def update_year(year_id: int):
    data = _data()
    if data.get_year(year_id) is None:
        return jsonify({"error": "Academic year not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_year(year_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@academic_year_bp.route("/<int:year_id>/set-current", methods=["POST"])
@_token_required
def set_current(year_id: int):
    data = _data()
    try:
        row = data.set_current(year_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(row))


@academic_year_bp.route("/<int:year_id>", methods=["DELETE"])
@_token_required
def delete_year(year_id: int):
    data = _data()
    if not data.delete_year(year_id):
        return jsonify({"error": "Academic year not found"}), 404
    return jsonify({"deleted": True, "year_id": year_id})


# ── Terms ──────────────────────────────────────────────────────────

@academic_year_bp.route("/terms", methods=["GET"])
@_token_required
def list_terms():
    data = _data()
    year_id = request.args.get("year_id", type=int)
    rows = data.list_terms(year_id=year_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@academic_year_bp.route("/terms/<int:term_id>", methods=["GET"])
@_token_required
def get_term(term_id: int):
    data = _data()
    row = data.get_term(term_id)
    if row is None:
        return jsonify({"error": "Term not found"}), 404
    return jsonify(_dump(row))


@academic_year_bp.route("/terms", methods=["POST"])
@_token_required
def create_term():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_term(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@academic_year_bp.route("/terms/<int:term_id>", methods=["PUT"])
@_token_required
def update_term(term_id: int):
    data = _data()
    if data.get_term(term_id) is None:
        return jsonify({"error": "Term not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_term(term_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@academic_year_bp.route("/terms/<int:term_id>", methods=["DELETE"])
@_token_required
def delete_term(term_id: int):
    data = _data()
    if not data.delete_term(term_id):
        return jsonify({"error": "Term not found"}), 404
    return jsonify({"deleted": True, "term_id": term_id})


# ── Breaks ─────────────────────────────────────────────────────────

@academic_year_bp.route("/breaks", methods=["GET"])
@_token_required
def list_breaks():
    data = _data()
    year_id = request.args.get("year_id", type=int)
    btype = request.args.get("type")
    try:
        rows = data.list_breaks(year_id=year_id, type=btype)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@academic_year_bp.route("/breaks/<int:break_id>", methods=["GET"])
@_token_required
def get_break(break_id: int):
    data = _data()
    row = data.get_break(break_id)
    if row is None:
        return jsonify({"error": "Break not found"}), 404
    return jsonify(_dump(row))


@academic_year_bp.route("/breaks", methods=["POST"])
@_token_required
def create_break():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_break(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@academic_year_bp.route("/breaks/<int:break_id>", methods=["PUT"])
@_token_required
def update_break(break_id: int):
    data = _data()
    if data.get_break(break_id) is None:
        return jsonify({"error": "Break not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_break(break_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@academic_year_bp.route("/breaks/<int:break_id>", methods=["DELETE"])
@_token_required
def delete_break(break_id: int):
    data = _data()
    if not data.delete_break(break_id):
        return jsonify({"error": "Break not found"}), 404
    return jsonify({"deleted": True, "break_id": break_id})
