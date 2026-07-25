"""REST API for Primary Document Hub."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

document_hub_bp = Blueprint("pri_document_hub", __name__, url_prefix="/api/document-hub")


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
    from education_system.systems.primary.domain.operations.document_hub import (
        document_hub as data,
    )
    return data


# ── List / Get ────────────────────────────────────────────

@document_hub_bp.route("", methods=["GET"])
@document_hub_bp.route("/", methods=["GET"])
@_token_required
def list_documents():
    data = _data()
    args = request.args
    rows = data.list_documents(
        category=args.get("category"),
        audience=args.get("audience"),
        access_level=args.get("access_level"),
        status=args.get("status"),
        current_only=args.get("current_only", "").lower() in ("1", "true", "yes"),
        overdue_review_only=args.get("overdue_review_only", "").lower()
        in ("1", "true", "yes"),
        title_like=args.get("title_like"),
        keyword_like=args.get("keyword_like"),
        author_like=args.get("author_like"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@document_hub_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@document_hub_bp.route("/<int:document_id>", methods=["GET"])
@_token_required
def get_document(document_id: int):
    data = _data()
    doc = data.get_document(document_id)
    if doc is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(doc))


# ── Create / Update / Delete ──────────────────────────────

@document_hub_bp.route("", methods=["POST"])
@document_hub_bp.route("/", methods=["POST"])
@_token_required
def create_document():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        doc = data.create_document(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(doc)), 201


@document_hub_bp.route("/<int:document_id>", methods=["PUT"])
@_token_required
def update_document(document_id: int):
    data = _data()
    if data.get_document(document_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        doc = data.update_document(document_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(doc))


@document_hub_bp.route("/<int:document_id>", methods=["DELETE"])
@_token_required
def delete_document(document_id: int):
    data = _data()
    if not data.delete_document(document_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "document_id": document_id})


# ── Workflow ──────────────────────────────────────────────

@document_hub_bp.route("/<int:document_id>/submit-for-review", methods=["POST"])
@_token_required
def submit_for_review(document_id: int):
    data = _data()
    try:
        doc = data.submit_for_review(document_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(doc))


@document_hub_bp.route("/<int:document_id>/approve", methods=["POST"])
@_token_required
def approve(document_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        doc = data.approve(document_id, approved_by=payload.get("approved_by"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(doc))


@document_hub_bp.route("/<int:document_id>/publish", methods=["POST"])
@_token_required
def publish(document_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        doc = data.publish(document_id, issued_on=payload.get("issued_on"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(doc))


@document_hub_bp.route("/<int:document_id>/withdraw", methods=["POST"])
@_token_required
def withdraw(document_id: int):
    data = _data()
    try:
        doc = data.withdraw(document_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(doc))


@document_hub_bp.route("/<int:document_id>/archive", methods=["POST"])
@_token_required
def archive(document_id: int):
    data = _data()
    try:
        doc = data.archive(document_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(doc))


@document_hub_bp.route("/<int:document_id>/supersede", methods=["POST"])
@_token_required
def supersede(document_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        doc = data.supersede(
            document_id,
            new_version=(payload.get("new_version") or ""),
            carry_over=bool(payload.get("carry_over", True)),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(doc)), 201


@document_hub_bp.route("/<int:document_id>/status", methods=["PUT"])
@_token_required
def set_status(document_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        doc = data.set_status(document_id, payload.get("status") or "")
    except data.ValidationError as exc:
        status_code = 404 if "No document" in str(exc) else 400
        return jsonify({"error": str(exc)}), status_code
    return jsonify(_dump(doc))


@document_hub_bp.route("/<int:document_id>/downloads", methods=["POST"])
@_token_required
def increment_downloads(document_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        by = int(payload.get("by", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "'by' must be an integer"}), 400
    try:
        doc = data.increment_downloads(document_id, by=by)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(doc))


@document_hub_bp.route("/auto-archive-expired", methods=["POST"])
@_token_required
def auto_archive_expired():
    data = _data()
    count = data.auto_archive_expired()
    return jsonify({"archived": count})
