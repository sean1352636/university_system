"""Library API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.student_life.library.services.library_service import LibraryService

library_bp = Blueprint("library", __name__, url_prefix="/api/library")

_db_path = None


def init_library_routes(db_path=None):
    global _db_path
    _db_path = db_path


@library_bp.route("/books", methods=["POST"])
@token_required
@role_required("admin")
def add_book():
    data = get_json_body()
    require_fields(data, "title", "author")
    svc = LibraryService(_db_path)
    result = svc.add_book(title=data["title"], author=data["author"], isbn=data.get("isbn", ""), category=data.get("category", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@library_bp.route("/books", methods=["GET"])
@token_required
def list_books():
    svc = LibraryService(_db_path)
    result = svc.list_books()
    return jsonify({"data": result})


@library_bp.route("/books/<int:book_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_book(book_id):
    svc = LibraryService(_db_path)
    result = svc.delete_book(book_id)
    return jsonify({"message": "Deleted.", "data": result})


@library_bp.route("/loans", methods=["POST"])
@token_required
def issue_loan():
    data = get_json_body()
    require_fields(data, "book_id", "student_id")
    svc = LibraryService(_db_path)
    result = svc.issue_loan(data["book_id"], data["student_id"])
    return jsonify({"message": "Created.", "data": result}), 201


@library_bp.route("/loans/<int:loan_id>/return", methods=["PUT"])
@token_required
def return_book(loan_id):
    svc = LibraryService(_db_path)
    result = svc.return_book(loan_id)
    return jsonify({"message": "Updated.", "data": result})


@library_bp.route("/loans", methods=["GET"])
@token_required
def list_loans():
    svc = LibraryService(_db_path)
    result = svc.list_loans()
    return jsonify({"data": result})


@library_bp.route("/loans/overdue", methods=["GET"])
@token_required
def overdue_loans():
    svc = LibraryService(_db_path)
    result = svc.overdue_loans()
    return jsonify({"data": result})

