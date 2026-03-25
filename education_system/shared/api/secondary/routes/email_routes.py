"""Email API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.communication.email.services.email_service import EmailService

email_bp = Blueprint("email", __name__, url_prefix="/api/email")

_db_path = None


def init_email_routes(db_path=None):
    global _db_path
    _db_path = db_path


@email_bp.route("", methods=["POST"])
@token_required
def send_email():
    data = get_json_body()
    require_fields(data, "sender_id", "recipient_id", "subject", "body")
    svc = EmailService(_db_path)
    result = svc.send(sender_id=data["sender_id"], recipient_id=data["recipient_id"], subject=data["subject"], body=data["body"])
    return jsonify({"message": "Created.", "data": result}), 201


@email_bp.route("/inbox/<int:user_id>", methods=["GET"])
@token_required
def get_inbox(user_id):
    svc = EmailService(_db_path)
    result = svc.get_inbox(user_id)
    return jsonify({"data": result})


@email_bp.route("/sent/<int:user_id>", methods=["GET"])
@token_required
def get_sent(user_id):
    svc = EmailService(_db_path)
    result = svc.get_sent(user_id)
    return jsonify({"data": result})


@email_bp.route("/<int:email_id>", methods=["GET"])
@token_required
def get_email(email_id):
    svc = EmailService(_db_path)
    result = svc.get_email(email_id)
    return jsonify({"data": result})


@email_bp.route("/<int:email_id>/read", methods=["PUT"])
@token_required
def mark_read(email_id):
    svc = EmailService(_db_path)
    result = svc.mark_read(email_id)
    return jsonify({"message": "Updated.", "data": result})


@email_bp.route("/<int:email_id>", methods=["DELETE"])
@token_required
def delete_email(email_id):
    svc = EmailService(_db_path)
    result = svc.delete_email(email_id)
    return jsonify({"message": "Deleted.", "data": result})


@email_bp.route("/unread/<int:user_id>", methods=["GET"])
@token_required
def unread_count(user_id):
    svc = EmailService(_db_path)
    result = svc.get_unread_count(user_id)
    return jsonify({"data": result})

