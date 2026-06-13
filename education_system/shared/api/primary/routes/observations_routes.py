"""REST API for Primary Lesson Observations."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

observations_bp = Blueprint("pri_observations", __name__, url_prefix="/api/observations")


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


def _data():
    from education_system.primarysch_system.modules.domain.observations import (
        observations as data,
    )
    return data


_FILTERS = (
    "teacher", "observer", "observation_type", "judgement",
    "status", "year_group", "date_from", "date_to",
)


@observations_bp.route("", methods=["GET"])
@observations_bp.route("/", methods=["GET"])
@_token_required
def list_observations():
    data = _data()
    kwargs = {k: request.args.get(k) for k in _FILTERS if request.args.get(k)}
    try:
        rows = data.list_observations(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@observations_bp.route("/<int:observation_id>", methods=["GET"])
@_token_required
def get_observation(observation_id: int):
    rec = _data().get(observation_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@observations_bp.route("", methods=["POST"])
@observations_bp.route("/", methods=["POST"])
@_token_required
def create_observation():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@observations_bp.route("/<int:observation_id>", methods=["PUT"])
@_token_required
def update_observation(observation_id: int):
    data = _data()
    if data.get(observation_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(observation_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@observations_bp.route("/<int:observation_id>", methods=["DELETE"])
@_token_required
def delete_observation(observation_id: int):
    if not _data().delete(observation_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


@observations_bp.route("/summary", methods=["GET"])
@_token_required
def observations_summary():
    data = _data()
    teacher = request.args.get("teacher")
    try:
        if teacher:
            result = data.teacher_summary(teacher)
        else:
            result = data.cohort_summary()
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    if "observations" in result:
        result["observations"] = _dump(result["observations"])
    return jsonify(result)
