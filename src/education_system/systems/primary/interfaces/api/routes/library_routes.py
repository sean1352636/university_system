"""REST API for Primary Library."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

library_bp = Blueprint("pri_library", __name__, url_prefix="/api/library")


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


# ── Books ────────────────────────────────────────────────────────

@library_bp.route("", methods=["GET"])
@library_bp.route("/", methods=["GET"])
@_token_required
def list_books_view():
    from education_system.systems.primary.domain.academics.library import library as data
    args = request.args
    rows = data.list_books(
        active_only=args.get("active_only", "").lower() in ("1", "true", "yes"),
        available_only=args.get("available_only", "").lower() in ("1", "true", "yes"),
        category=args.get("category") or None,
        query=args.get("query") or None,
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@library_bp.route("/books", methods=["GET"])
@_token_required
def list_books_alias():
    return list_books_view()


@library_bp.route("/<int:book_id>", methods=["GET"])
@library_bp.route("/books/<int:book_id>", methods=["GET"])
@_token_required
def get_book_view(book_id: int):
    from education_system.systems.primary.domain.academics.library import library as data
    rec = data.get_book(book_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@library_bp.route("", methods=["POST"])
@library_bp.route("/", methods=["POST"])
@library_bp.route("/books", methods=["POST"])
@_token_required
def create_book_view():
    from education_system.systems.primary.domain.academics.library import library as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_book(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@library_bp.route("/<int:book_id>", methods=["PUT"])
@library_bp.route("/books/<int:book_id>", methods=["PUT"])
@_token_required
def update_book_view(book_id: int):
    from education_system.systems.primary.domain.academics.library import library as data
    if data.get_book(book_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_book(book_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@library_bp.route("/<int:book_id>", methods=["DELETE"])
@library_bp.route("/books/<int:book_id>", methods=["DELETE"])
@_token_required
def delete_book_view(book_id: int):
    from education_system.systems.primary.domain.academics.library import library as data
    try:
        ok = data.delete_book(book_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    if not ok:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "book_id": book_id})


@library_bp.route("/<int:book_id>/toggle-active", methods=["POST"])
@_token_required
def toggle_active_view(book_id: int):
    from education_system.systems.primary.domain.academics.library import library as data
    try:
        rec = data.toggle_active(book_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


# ── Loans ────────────────────────────────────────────────────────

@library_bp.route("/loans", methods=["GET"])
@_token_required
def list_loans_view():
    from education_system.systems.primary.domain.academics.library import library as data
    args = request.args
    book_id = args.get("book_id")
    try:
        rows = data.list_loans(
            status=args.get("status") or None,
            pupil_id=args.get("pupil_id") or None,
            book_id=int(book_id) if book_id else None,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@library_bp.route("/loans/<int:loan_id>", methods=["GET"])
@_token_required
def get_loan_view(loan_id: int):
    from education_system.systems.primary.domain.academics.library import library as data
    rec = data.get_loan(loan_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@library_bp.route("/loans", methods=["POST"])
@_token_required
def lend_view():
    from education_system.systems.primary.domain.academics.library import library as data
    payload = request.get_json(silent=True) or {}
    book_id = payload.get("book_id")
    if book_id is None:
        return jsonify({"error": "book_id is required"}), 400
    try:
        rec = data.lend(
            int(book_id),
            payload.get("pupil_id") or "",
            loan_date=payload.get("loan_date"),
            due_date=payload.get("due_date"),
            notes=payload.get("notes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "book_id must be an integer"}), 400
    return jsonify(_dump(rec)), 201


@library_bp.route("/loans/<int:loan_id>/return", methods=["POST"])
@_token_required
def return_loan_view(loan_id: int):
    from education_system.systems.primary.domain.academics.library import library as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.return_loan(
            loan_id,
            returned_date=payload.get("returned_date"),
            notes=payload.get("notes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@library_bp.route("/loans/<int:loan_id>/lost", methods=["POST"])
@_token_required
def mark_lost_view(loan_id: int):
    from education_system.systems.primary.domain.academics.library import library as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.mark_lost(loan_id, notes=payload.get("notes"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


# ── Summary ──────────────────────────────────────────────────────

@library_bp.route("/summary", methods=["GET"])
@_token_required
def summary_view():
    from education_system.systems.primary.domain.academics.library import library as data
    return jsonify(_dump(data.overview()))
