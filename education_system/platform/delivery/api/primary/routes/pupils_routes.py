"""REST API for Primary Pupils."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

pupils_bp = Blueprint("pri_pupils", __name__, url_prefix="/api/pupils")


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
    from education_system.systems.primary.domain.learners.pupils import pupils as data
    return data


@pupils_bp.route("", methods=["GET"])
@pupils_bp.route("/", methods=["GET"])
@_token_required
def list_pupils():
    data = _data()
    rows = data.list_pupils()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pupils_bp.route("/search", methods=["GET"])
@_token_required
def search_pupils():
    data = _data()
    query = request.args.get("q", "")
    rows = data.search_pupils(query)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pupils_bp.route("/<pupil_id>", methods=["GET"])
@_token_required
def get_pupil(pupil_id):
    data = _data()
    pupil = data.get_pupil(pupil_id)
    if pupil is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(pupil))


@pupils_bp.route("", methods=["POST"])
@pupils_bp.route("/", methods=["POST"])
@_token_required
def create_pupil():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        pupil = data.create_pupil(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(pupil)), 201


@pupils_bp.route("/<pupil_id>", methods=["PUT"])
@_token_required
def update_pupil(pupil_id):
    data = _data()
    if data.get_pupil(pupil_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        pupil = data.update_pupil(pupil_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(pupil))


@pupils_bp.route("/<pupil_id>", methods=["DELETE"])
@_token_required
def delete_pupil(pupil_id):
    data = _data()
    if not data.delete_pupil(pupil_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": pupil_id})
