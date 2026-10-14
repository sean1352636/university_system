"""REST API for Primary Recruitment (vacancies & applicants)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

recruitment_bp = Blueprint("pri_recruitment", __name__, url_prefix="/api/recruitment")


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
    from education_system.systems.primary.domain.staff.recruitment import (
        recruitment as data,
    )
    return data


# ── Vacancies ────────────────────────────────────────────

@recruitment_bp.route("", methods=["GET"])
@recruitment_bp.route("/", methods=["GET"])
@_token_required
def list_vacancies():
    data = _data()
    rows = data.list_vacancies()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@recruitment_bp.route("/<int:vacancy_id>", methods=["GET"])
@_token_required
def get_vacancy(vacancy_id):
    data = _data()
    obj = data.get_vacancy(vacancy_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@recruitment_bp.route("", methods=["POST"])
@recruitment_bp.route("/", methods=["POST"])
@_token_required
def create_vacancy():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_vacancy(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@recruitment_bp.route("/<int:vacancy_id>", methods=["PUT"])
@_token_required
def update_vacancy(vacancy_id):
    data = _data()
    if data.get_vacancy(vacancy_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_vacancy(vacancy_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@recruitment_bp.route("/<int:vacancy_id>", methods=["DELETE"])
@_token_required
def delete_vacancy(vacancy_id):
    data = _data()
    if not data.delete_vacancy(vacancy_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Applicants ───────────────────────────────────────────

@recruitment_bp.route("/applicants", methods=["GET"])
@_token_required
def list_applicants():
    data = _data()
    vacancy_id = request.args.get("vacancy_id", type=int)
    rows = data.list_applicants(vacancy_id=vacancy_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@recruitment_bp.route("/applicants/<int:applicant_id>", methods=["GET"])
@_token_required
def get_applicant(applicant_id):
    data = _data()
    obj = data.get_applicant(applicant_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@recruitment_bp.route("/<int:vacancy_id>/applicants", methods=["POST"])
@_token_required
def add_applicant(vacancy_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.add_applicant(vacancy_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@recruitment_bp.route("/applicants/<int:applicant_id>", methods=["PUT"])
@_token_required
def update_applicant(applicant_id):
    data = _data()
    if data.get_applicant(applicant_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_applicant(applicant_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@recruitment_bp.route("/applicants/<int:applicant_id>", methods=["DELETE"])
@_token_required
def delete_applicant(applicant_id):
    data = _data()
    if not data.delete_applicant(applicant_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Summary ──────────────────────────────────────────────

@recruitment_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))
