"""Email API routes."""

from flask import Blueprint, jsonify

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.modules.domain.communication.email.services.email_service import EmailService

emails_bp = Blueprint("emails", __name__, url_prefix="/api/emails")

_db_path = None


def init_emails_routes(db_path=None):
    global _db_path
    _db_path = db_path


@emails_bp.route("", methods=["GET"])
@token_required
def list_emails():
    svc = EmailService(_db_path)
    items = svc.list_emails()
    return jsonify({"data": items})


@emails_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def send_email():
    data = get_json_body()
    require_fields(data, "recipient", "subject", "body")
    svc = EmailService(_db_path)
    result = svc.send_email(**data)
    return jsonify({"message": "Email sent.", "data": result}), 201
