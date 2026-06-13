"""REST API for Sixth Form Student Services.

Exposes HTTP CRUD over the sixth-form students domain submodules:
admissions (applicants), enrolments, and alumni. The students core
submodule is intentionally not re-exposed (see students_routes.py).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

student_services_bp = Blueprint(
    "sf_student_services", __name__,
    url_prefix="/api/sixthform/student-services")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SIXTHFORM_API_TOKEN")
            got = request.headers.get("X-Sixthform-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe dicts."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


# ── Admissions (applicants) ─────────────────────────────────────────

def _admissions():
    from education_system.sixthform_system.modules.domain.students.admissions import (  # noqa: E501
        admissions as data,
    )
    return data


@student_services_bp.route("/admissions", methods=["GET"])
@_token_required
def list_applicants():
    data = _admissions()
    args = request.args
    try:
        rows = data.list_applicants(
            status=args.get("status"),
            source=args.get("source"),
            open_only=args.get("open_only", "").lower() in ("1", "true", "yes"),
            has_offer=args.get("has_offer", "").lower() in ("1", "true", "yes"),
            enrolled_only=args.get("enrolled_only", "").lower()
            in ("1", "true", "yes"),
            search=args.get("search"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"applicants": _dump(rows), "count": len(rows)})


@student_services_bp.route("/admissions/<applicant_id>", methods=["GET"])
@_token_required
def get_applicant(applicant_id):
    data = _admissions()
    obj = data.get_applicant(applicant_id)
    if obj is None:
        return jsonify({"error": "Applicant not found"}), 404
    return jsonify(_dump(obj))


@student_services_bp.route("/admissions", methods=["POST"])
@_token_required
def create_applicant():
    data = _admissions()
    try:
        obj = data.create_applicant(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj)), 201


@student_services_bp.route("/admissions/<applicant_id>", methods=["PUT"])
@_token_required
def update_applicant(applicant_id):
    data = _admissions()
    if data.get_applicant(applicant_id) is None:
        return jsonify({"error": "Applicant not found"}), 404
    try:
        obj = data.update_applicant(
            applicant_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj))


@student_services_bp.route("/admissions/<applicant_id>", methods=["DELETE"])
@_token_required
def delete_applicant(applicant_id):
    data = _admissions()
    if not data.delete_applicant(applicant_id):
        return jsonify({"error": "Applicant not found"}), 404
    return jsonify({"deleted": applicant_id})


@student_services_bp.route("/admissions/summary", methods=["GET"])
@_token_required
def admissions_summary():
    data = _admissions()
    window = request.args.get("upcoming_window_days", type=int)
    obj = (data.summary(upcoming_window_days=window)
           if window is not None else data.summary())
    return jsonify(_dump(obj))


# ── Enrolments ──────────────────────────────────────────────────────

def _enrolments():
    from education_system.sixthform_system.modules.domain.students.enrolments import (  # noqa: E501
        enrolments as data,
    )
    return data


@student_services_bp.route("/enrolments", methods=["GET"])
@_token_required
def list_enrolments():
    data = _enrolments()
    args = request.args
    try:
        rows = data.list_enrolments(
            student_id=args.get("student_id"),
            academic_year=args.get("academic_year"),
            year_group=args.get("year_group", type=int),
            status=args.get("status"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"enrolments": _dump(rows), "count": len(rows)})


@student_services_bp.route("/enrolments/<int:enrolment_id>", methods=["GET"])
@_token_required
def get_enrolment(enrolment_id):
    data = _enrolments()
    obj = data.get_enrolment(enrolment_id)
    if obj is None:
        return jsonify({"error": "Enrolment not found"}), 404
    return jsonify(_dump(obj))


@student_services_bp.route("/enrolments", methods=["POST"])
@_token_required
def create_enrolment():
    data = _enrolments()
    try:
        obj = data.create_enrolment(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj)), 201


@student_services_bp.route("/enrolments/<int:enrolment_id>", methods=["PUT"])
@_token_required
def update_enrolment(enrolment_id):
    data = _enrolments()
    if data.get_enrolment(enrolment_id) is None:
        return jsonify({"error": "Enrolment not found"}), 404
    try:
        obj = data.update_enrolment(
            enrolment_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj))


@student_services_bp.route("/enrolments/<int:enrolment_id>", methods=["DELETE"])
@_token_required
def delete_enrolment(enrolment_id):
    data = _enrolments()
    if not data.delete_enrolment(enrolment_id):
        return jsonify({"error": "Enrolment not found"}), 404
    return jsonify({"deleted": enrolment_id})


# ── Alumni ──────────────────────────────────────────────────────────

def _alumni():
    from education_system.sixthform_system.modules.domain.students.alumni import (  # noqa: E501
        alumni as data,
    )
    return data


@student_services_bp.route("/alumni", methods=["GET"])
@_token_required
def list_alumni():
    data = _alumni()
    args = request.args
    try:
        rows = data.list_alumni(
            leaving_year=args.get("leaving_year"),
            destination_type=args.get("destination_type"),
            status=args.get("status"),
            contactable_only=args.get("contactable_only", "").lower()
            in ("1", "true", "yes"),
            search=args.get("search"),
            employer=args.get("employer"),
            university=args.get("university"),
            sector=args.get("sector"),
            country=args.get("country"),
            tag=args.get("tag"),
            include_deleted=args.get("include_deleted", "").lower()
            in ("1", "true", "yes"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"alumni": _dump(rows), "count": len(rows)})


@student_services_bp.route("/alumni/<int:alumni_id>", methods=["GET"])
@_token_required
def get_alumnus(alumni_id):
    data = _alumni()
    obj = data.get_alumnus(alumni_id)
    if obj is None:
        return jsonify({"error": "Alumnus not found"}), 404
    return jsonify(_dump(obj))


@student_services_bp.route("/alumni", methods=["POST"])
@_token_required
def create_alumnus():
    data = _alumni()
    try:
        obj = data.create_alumnus(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj)), 201


@student_services_bp.route("/alumni/<int:alumni_id>", methods=["PUT"])
@_token_required
def update_alumnus(alumni_id):
    data = _alumni()
    if data.get_alumnus(alumni_id) is None:
        return jsonify({"error": "Alumnus not found"}), 404
    try:
        obj = data.update_alumnus(
            alumni_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(obj))


@student_services_bp.route("/alumni/<int:alumni_id>", methods=["DELETE"])
@_token_required
def delete_alumnus(alumni_id):
    data = _alumni()
    if not data.delete_alumnus(alumni_id):
        return jsonify({"error": "Alumnus not found"}), 404
    return jsonify({"deleted": alumni_id})
