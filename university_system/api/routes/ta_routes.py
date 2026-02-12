"""Teaching assistant routes: assignments, permissions, and workload."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import token_required
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

ta_bp = Blueprint("teaching_assistants", __name__, url_prefix="/api/teaching-assistants")

# Initialize the service at module level
from university_system.modules.domain.academics.services.ta_management.ta_service import (
    TAService,
)

_service = TAService()


# ---- TA Assignment CRUD ----


@ta_bp.route("", methods=["GET"])
@token_required
def list_tas():
    """List all TAs, optionally filtered by status or module_code."""
    status = request.args.get("status", "active")
    module_code = request.args.get("module_code")

    try:
        if module_code:
            items = _service.get_tas_for_module(module_code)
        else:
            items = _service.get_all_tas(status=status)

        log_activity("view", "teaching_assistants", user=g.current_user.get("sub"))
        return jsonify({"items": items, "total": len(items)})
    except Exception as e:
        logger.error(f"Error listing TAs: {e}")
        return jsonify({"error": "Failed to retrieve teaching assistants", "details": str(e)}), 500


@ta_bp.route("/<int:id>", methods=["GET"])
@token_required
def get_ta(id: int):
    """Get a specific TA assignment by ID."""
    try:
        item = _service.get_ta(id)
        if not item:
            return jsonify({"error": f"TA assignment {id} not found"}), 404

        log_activity("view", "teaching_assistant", user=g.current_user.get("sub"))
        return jsonify(item)
    except Exception as e:
        logger.error(f"Error retrieving TA {id}: {e}")
        return jsonify({"error": "Failed to retrieve TA assignment", "details": str(e)}), 500


@ta_bp.route("", methods=["POST"])
@token_required
def assign_ta():
    """Assign a student as a Teaching Assistant."""
    data = request.get_json(silent=True) or {}

    required_fields = ["student_id", "instructor_id", "module_code"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        ta_id = _service.assign_ta(
            student_id=data["student_id"],
            instructor_id=data["instructor_id"],
            module_code=data["module_code"],
            role_type=data.get("role_type", "ta"),
            hours_per_week=data.get("hours_per_week", 10),
        )

        item = _service.get_ta(ta_id)
        log_activity("create", "teaching_assistant", user=g.current_user.get("sub"))
        return jsonify(item), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error assigning TA: {e}")
        return jsonify({"error": "Failed to assign teaching assistant", "details": str(e)}), 500


@ta_bp.route("/<int:id>", methods=["PUT"])
@token_required
def update_ta(id: int):
    """Update an existing TA assignment."""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No fields provided for update"}), 400

    try:
        existing = _service.get_ta(id)
        if not existing:
            return jsonify({"error": f"TA assignment {id} not found"}), 404

        updated = _service.update_ta(id, **data)
        if not updated:
            return jsonify({"error": "No valid fields to update"}), 400

        item = _service.get_ta(id)
        log_activity("update", "teaching_assistant", user=g.current_user.get("sub"))
        return jsonify(item)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating TA {id}: {e}")
        return jsonify({"error": "Failed to update TA assignment", "details": str(e)}), 500


@ta_bp.route("/<int:id>", methods=["DELETE"])
@token_required
def remove_ta(id: int):
    """Remove (deactivate) a TA assignment."""
    try:
        removed = _service.remove_ta(id)
        if not removed:
            return jsonify({"error": f"TA assignment {id} not found or already inactive"}), 404

        log_activity("delete", "teaching_assistant", user=g.current_user.get("sub"))
        return jsonify({"message": f"TA assignment {id} removed successfully"})
    except Exception as e:
        logger.error(f"Error removing TA {id}: {e}")
        return jsonify({"error": "Failed to remove TA assignment", "details": str(e)}), 500


# ---- Module & Workload Queries ----


@ta_bp.route("/module/<module_code>", methods=["GET"])
@token_required
def get_tas_for_module(module_code: str):
    """Get all active TAs assigned to a specific module."""
    try:
        items = _service.get_tas_for_module(module_code)
        log_activity("view", "module_teaching_assistants", user=g.current_user.get("sub"))
        return jsonify({"items": items, "total": len(items), "module_code": module_code})
    except Exception as e:
        logger.error(f"Error retrieving TAs for module {module_code}: {e}")
        return jsonify({"error": "Failed to retrieve TAs for module", "details": str(e)}), 500


@ta_bp.route("/workload/<student_id>", methods=["GET"])
@token_required
def get_ta_workload(student_id: str):
    """Get TA workload summary for a specific student."""
    try:
        workload = _service.get_ta_workload(student_id)
        log_activity("view", "ta_workload", user=g.current_user.get("sub"))
        return jsonify({"student_id": student_id, **workload})
    except Exception as e:
        logger.error(f"Error retrieving TA workload for student {student_id}: {e}")
        return jsonify({"error": "Failed to retrieve TA workload", "details": str(e)}), 500


# ---- Permissions ----


@ta_bp.route("/<int:id>/permissions", methods=["POST"])
@token_required
def set_ta_permissions(id: int):
    """Set permissions for a TA on a specific module."""
    data = request.get_json(silent=True) or {}

    if not data.get("permission_types"):
        return jsonify({"error": "Missing required field: permission_types"}), 400
    if not data.get("module_code"):
        return jsonify({"error": "Missing required field: module_code"}), 400
    if not isinstance(data["permission_types"], list):
        return jsonify({"error": "permission_types must be a list"}), 400

    try:
        existing = _service.get_ta(id)
        if not existing:
            return jsonify({"error": f"TA assignment {id} not found"}), 404

        granted_by = g.current_user.get("sub", "")
        _service.set_ta_permissions(
            ta_id=id,
            permission_types=data["permission_types"],
            module_code=data["module_code"],
            granted_by=granted_by,
        )

        log_activity("update", "ta_permissions", user=granted_by)
        return jsonify({
            "message": "Permissions updated successfully",
            "ta_id": id,
            "module_code": data["module_code"],
            "permissions": data["permission_types"],
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error setting permissions for TA {id}: {e}")
        return jsonify({"error": "Failed to set TA permissions", "details": str(e)}), 500


@ta_bp.route("/<int:id>/permissions/<module_code>", methods=["GET"])
@token_required
def check_ta_permission(id: int, module_code: str):
    """Check permissions for a TA on a specific module."""
    permission_type = request.args.get("permission_type")

    try:
        ta = _service.get_ta(id)
        if not ta:
            return jsonify({"error": f"TA assignment {id} not found"}), 404

        student_id = ta.get("student_id", "")

        if permission_type:
            has_permission = _service.check_ta_permission(
                student_id=student_id,
                module_code=module_code,
                permission_type=permission_type,
            )
            log_activity("view", "ta_permission_check", user=g.current_user.get("sub"))
            return jsonify({
                "ta_id": id,
                "student_id": student_id,
                "module_code": module_code,
                "permission_type": permission_type,
                "has_permission": has_permission,
            })

        # If no specific permission_type is given, check all valid permissions
        from university_system.modules.domain.academics.services.ta_management.ta_service import (
            VALID_PERMISSION_TYPES,
        )

        permissions = {}
        for perm in VALID_PERMISSION_TYPES:
            permissions[perm] = _service.check_ta_permission(
                student_id=student_id,
                module_code=module_code,
                permission_type=perm,
            )

        log_activity("view", "ta_permissions", user=g.current_user.get("sub"))
        return jsonify({
            "ta_id": id,
            "student_id": student_id,
            "module_code": module_code,
            "permissions": permissions,
        })
    except Exception as e:
        logger.error(f"Error checking permissions for TA {id}: {e}")
        return jsonify({"error": "Failed to check TA permissions", "details": str(e)}), 500
