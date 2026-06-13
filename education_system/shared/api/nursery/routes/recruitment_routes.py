"""REST API for Nursery Recruitment.

Exposes CRUD over staff vacancies plus nested applicants and a summary.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

recruitment_bp = Blueprint("nsy_recruitment", __name__, url_prefix="/api/recruitment")


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


def _truthy(value: str | None) -> bool:
    return str(value).lower() in ("1", "true", "yes", "on") if value is not None else False


# ── Vacancies ─────────────────────────────────────────────

@recruitment_bp.route("", methods=["GET"])
@recruitment_bp.route("/", methods=["GET"])
@_token_required
def list_vacancies():
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    q = request.args
    rows = data.list_vacancies(
        role_type=q.get("role_type"),
        contract_type=q.get("contract_type"),
        status=q.get("status"),
        department_like=q.get("department_like"),
        title_like=q.get("title_like"),
        open_only=_truthy(q.get("open_only")),
        closing_passed=_truthy(q.get("closing_passed")),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@recruitment_bp.route("/<int:vacancy_id>", methods=["GET"])
@_token_required
def get_vacancy(vacancy_id: int):
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    row = data.get_vacancy(vacancy_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@recruitment_bp.route("", methods=["POST"])
@recruitment_bp.route("/", methods=["POST"])
@_token_required
def create_vacancy():
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    try:
        row = data.create_vacancy(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@recruitment_bp.route("/<int:vacancy_id>", methods=["PUT"])
@_token_required
def update_vacancy(vacancy_id: int):
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    if data.get_vacancy(vacancy_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_vacancy(vacancy_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@recruitment_bp.route("/<int:vacancy_id>", methods=["DELETE"])
@_token_required
def delete_vacancy(vacancy_id: int):
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    if not data.delete_vacancy(vacancy_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": vacancy_id})


# ── Applicants (nested under a vacancy / flat collection) ──

@recruitment_bp.route("/applicants", methods=["GET"])
@_token_required
def list_applicants():
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    q = request.args
    vid = q.get("vacancy_id")
    rows = data.list_applicants(
        vacancy_id=int(vid) if vid not in (None, "") else None,
        status=q.get("status"),
        shortlisted_only=_truthy(q.get("shortlisted_only")),
        interview_scheduled=_truthy(q.get("interview_scheduled")),
        offer_made=_truthy(q.get("offer_made")),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@recruitment_bp.route("/applicants/<int:applicant_id>", methods=["GET"])
@_token_required
def get_applicant(applicant_id: int):
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    row = data.get_applicant(applicant_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@recruitment_bp.route("/<int:vacancy_id>/applicants", methods=["POST"])
@_token_required
def add_applicant(vacancy_id: int):
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    try:
        row = data.add_applicant(vacancy_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@recruitment_bp.route("/applicants/<int:applicant_id>", methods=["PUT"])
@_token_required
def update_applicant(applicant_id: int):
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    if data.get_applicant(applicant_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_applicant(applicant_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@recruitment_bp.route("/applicants/<int:applicant_id>", methods=["DELETE"])
@_token_required
def delete_applicant(applicant_id: int):
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    if not data.delete_applicant(applicant_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": applicant_id})


# ── Summary ────────────────────────────────────────────────

@recruitment_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.nursery_system.modules.domain.recruitment import recruitment as data
    return jsonify(_dump(data.summary()))
