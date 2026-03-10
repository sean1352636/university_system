"""Library API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.modules.domain.pupil_life.library.services.library_service import LibraryService

library_bp = Blueprint("library", __name__, url_prefix="/api/library")

_db_path = None


def init_library_routes(db_path=None):
    global _db_path
    _db_path = db_path


@library_bp.route("/books", methods=["GET"])
@token_required
def list_books():
    svc = LibraryService(_db_path)
    items = svc.list_books()
    return jsonify({"data": items})


@library_bp.route("/books", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def add_book():
    data = get_json_body()
    require_fields(data, "title", "author")
    svc = LibraryService(_db_path)
    result = svc.add_book(**data)
    return jsonify({"message": "Book added.", "data": result}), 201


@library_bp.route("/loans", methods=["GET"])
@token_required
def list_loans():
    svc = LibraryService(_db_path)
    items = svc.list_loans()
    return jsonify({"data": items})


@library_bp.route("/loans", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_loan():
    data = get_json_body()
    require_fields(data, "book_id", "pupil_id")
    svc = LibraryService(_db_path)
    result = svc.create_loan(**data)
    return jsonify({"message": "Loan created.", "data": result}), 201
