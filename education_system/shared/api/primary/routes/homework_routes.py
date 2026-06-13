"""REST API for Primary Homework."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

homework_bp = Blueprint("pri_homework", __name__, url_prefix="/api/homework")


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
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    return obj


def _data():
    from education_system.primarysch_system.modules.domain.homework import (
        homework as data,
    )
    return data


# ── Assignments ───────────────────────────────────────────────────

@homework_bp.route("", methods=["GET"])
@homework_bp.route("/", methods=["GET"])
@_token_required
def list_assignments():
    data = _data()
    args = request.args
    sid = args.get("subject_id")
    try:
        rows = data.list_assignments(
            year_group=args.get("year_group"),
            subject_id=int(sid) if sid not in (None, "") else None,
            status=args.get("status"),
            teacher=args.get("teacher"),
            due_from=args.get("due_from"),
            due_to=args.get("due_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "subject_id must be a number"}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@homework_bp.route("/summary", methods=["GET"])
@_token_required
def assignment_status_counts():
    data = _data()
    return jsonify(data.assignment_status_counts())


@homework_bp.route("/<int:assignment_id>", methods=["GET"])
@_token_required
def get_assignment(assignment_id: int):
    data = _data()
    rec = data.get_assignment(assignment_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@homework_bp.route("", methods=["POST"])
@homework_bp.route("/", methods=["POST"])
@_token_required
def create_assignment():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_assignment(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@homework_bp.route("/<int:assignment_id>", methods=["PUT"])
@_token_required
def update_assignment(assignment_id: int):
    data = _data()
    if data.get_assignment(assignment_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_assignment(assignment_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@homework_bp.route("/<int:assignment_id>", methods=["DELETE"])
@_token_required
def delete_assignment(assignment_id: int):
    data = _data()
    if not data.delete_assignment(assignment_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Submissions (nested under an assignment) ──────────────────────

@homework_bp.route("/<int:assignment_id>/submissions", methods=["GET"])
@_token_required
def list_submissions(assignment_id: int):
    data = _data()
    if data.get_assignment(assignment_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_submissions(assignment_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@homework_bp.route("/<int:assignment_id>/submissions", methods=["POST"])
@_token_required
def upsert_submission(assignment_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.upsert_submission(assignment_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@homework_bp.route("/<int:assignment_id>/submissions/seed", methods=["POST"])
@_token_required
def seed_submissions(assignment_id: int):
    data = _data()
    try:
        added = data.seed_submissions(assignment_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"added": added}), 201


@homework_bp.route("/<int:assignment_id>/summary", methods=["GET"])
@_token_required
def submission_summary(assignment_id: int):
    data = _data()
    try:
        result = data.submission_summary(assignment_id)
    except data.ValidationError:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(result))


@homework_bp.route("/submissions/<int:submission_id>", methods=["GET"])
@_token_required
def get_submission(submission_id: int):
    data = _data()
    rec = data.get_submission(submission_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@homework_bp.route("/submissions/<int:submission_id>", methods=["DELETE"])
@_token_required
def delete_submission(submission_id: int):
    data = _data()
    if not data.delete_submission(submission_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


@homework_bp.route("/pupils/<pupil_id>/submissions", methods=["GET"])
@_token_required
def list_for_pupil(pupil_id: str):
    data = _data()
    try:
        rows = data.list_for_pupil(pupil_id, status=request.args.get("status"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})
