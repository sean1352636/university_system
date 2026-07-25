"""Flask blueprint for GDPR data retention management API.

All endpoints are admin-only and require a valid Bearer JWT.

Endpoints
---------
GET  /api/v1/retention/policies            — list all policies
POST /api/v1/retention/policies            — create a policy
PUT  /api/v1/retention/policies/<id>       — update a policy
DELETE /api/v1/retention/policies/<id>     — deactivate a policy
POST /api/v1/retention/run                 — trigger a manual run
POST /api/v1/retention/run/<id>            — run a single policy
GET  /api/v1/retention/jobs                — job history
POST /api/v1/retention/dsar                — generate DSAR report
POST /api/v1/retention/erasure             — process erasure request
GET  /api/v1/retention/requests            — list data subject requests
"""

import logging
from flask import Blueprint, jsonify, request, g

from education_system.platform.delivery.api.auth import token_required, role_required
from education_system.platform.services.data_retention.models import init_retention_db
from education_system.platform.services.data_retention.policy_engine import RetentionPolicyEngine
from education_system.platform.services.data_retention.gdpr_report import (
    generate_dsar_report,
    process_erasure_request,
)

logger = logging.getLogger(__name__)

retention_bp = Blueprint("retention", __name__, url_prefix="/api/retention")

# Module-level engine instance (lazy-initialised on first request)
_engine: RetentionPolicyEngine | None = None


def _get_engine() -> RetentionPolicyEngine:
    global _engine
    if _engine is None:
        _engine = RetentionPolicyEngine()
    return _engine


def init_retention(db_path=None) -> None:
    """Initialise the retention DB.  Called during app startup."""
    global _engine
    init_retention_db()
    _engine = RetentionPolicyEngine()
    logger.info("Retention routes initialised.")


# ---------------------------------------------------------------------------
# Policy endpoints
# ---------------------------------------------------------------------------

@retention_bp.route("/policies", methods=["GET"])
@role_required("admin")
def list_policies():
    """Return all retention policies."""
    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    engine = _get_engine()
    if include_inactive:
        policies = engine.get_all_policies()
    else:
        policies = engine.get_active_policies()
    return jsonify({"policies": policies, "count": len(policies)}), 200


@retention_bp.route("/policies", methods=["POST"])
@role_required("admin")
def create_policy():
    """Create a new retention policy."""
    data = request.get_json(silent=True) or {}
    required = ("entity_type", "retention_days", "action")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    valid_actions = ("archive", "anonymize", "delete")
    if data["action"] not in valid_actions:
        return jsonify({"error": f"action must be one of: {', '.join(valid_actions)}"}), 400

    try:
        retention_days = int(data["retention_days"])
    except (TypeError, ValueError):
        return jsonify({"error": "retention_days must be an integer"}), 400

    try:
        engine = _get_engine()
        policy = engine.add_policy(
            entity_type=data["entity_type"],
            retention_days=retention_days,
            action=data["action"],
            system_key=data.get("system_key", "all"),
            description=data.get("description", ""),
        )
        return jsonify({"policy": policy}), 201
    except Exception as exc:
        logger.error("Failed to create policy: %s", exc)
        return jsonify({"error": "Failed to create policy"}), 500


@retention_bp.route("/policies/<int:policy_id>", methods=["PUT"])
@role_required("admin")
def update_policy(policy_id: int):
    """Update an existing retention policy."""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No update fields provided"}), 400

    try:
        engine = _get_engine()
        updated = engine.update_policy(policy_id, **data)
        if updated is None:
            return jsonify({"error": "Policy not found"}), 404
        return jsonify({"policy": updated}), 200
    except ValueError as exc:
        logger.warning("Invalid policy update for %d: %s", policy_id, exc)
        return jsonify({"error": "Invalid policy update parameters"}), 400
    except Exception as exc:
        logger.error("Failed to update policy %d: %s", policy_id, exc)
        return jsonify({"error": "Failed to update policy"}), 500


@retention_bp.route("/policies/<int:policy_id>", methods=["DELETE"])
@role_required("admin")
def deactivate_policy(policy_id: int):
    """Deactivate (soft-delete) a retention policy."""
    try:
        engine = _get_engine()
        success = engine.deactivate_policy(policy_id)
        if not success:
            return jsonify({"error": "Policy not found"}), 404
        return jsonify({"message": f"Policy {policy_id} deactivated"}), 200
    except Exception as exc:
        logger.error("Failed to deactivate policy %d: %s", policy_id, exc)
        return jsonify({"error": "Failed to deactivate policy"}), 500


# ---------------------------------------------------------------------------
# Execution endpoints
# ---------------------------------------------------------------------------

@retention_bp.route("/run", methods=["POST"])
@role_required("admin")
def run_all():
    """Trigger a manual run of all active retention policies."""
    try:
        engine = _get_engine()
        jobs = engine.run_all_policies()
        total_affected = sum(j.get("records_affected", 0) for j in jobs)
        return jsonify({
            "message": "Retention run completed",
            "jobs_executed": len(jobs),
            "total_records_affected": total_affected,
            "jobs": jobs,
        }), 200
    except Exception as exc:
        logger.error("Manual retention run failed: %s", exc)
        return jsonify({"error": "Retention run failed"}), 500


@retention_bp.route("/run/<int:policy_id>", methods=["POST"])
@role_required("admin")
def run_single(policy_id: int):
    """Trigger a manual run of a single policy by ID."""
    try:
        engine = _get_engine()
        job = engine.run_policy(policy_id)
        return jsonify({"message": "Policy executed", "job": job}), 200
    except ValueError as exc:
        logger.warning("Policy %d not found: %s", policy_id, exc)
        return jsonify({"error": "Policy not found"}), 404
    except Exception as exc:
        logger.error("Failed to run policy %d: %s", policy_id, exc)
        return jsonify({"error": "Policy execution failed"}), 500


# ---------------------------------------------------------------------------
# Job history
# ---------------------------------------------------------------------------

@retention_bp.route("/jobs", methods=["GET"])
@role_required("admin")
def job_history():
    """Return recent retention job history."""
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 500))

    try:
        engine = _get_engine()
        jobs = engine.get_job_history(limit)
        return jsonify({"jobs": jobs, "count": len(jobs)}), 200
    except Exception as exc:
        logger.error("Failed to fetch job history: %s", exc)
        return jsonify({"error": "Failed to fetch job history"}), 500


# ---------------------------------------------------------------------------
# DSAR and erasure endpoints
# ---------------------------------------------------------------------------

@retention_bp.route("/dsar", methods=["POST"])
@role_required("admin")
def dsar():
    """Generate a Data Subject Access Request report for a given email."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    if not email:
        return jsonify({"error": "email is required"}), 400

    try:
        report = generate_dsar_report(email)
        return jsonify(report), 200
    except Exception as exc:
        logger.error("DSAR generation failed for %s: %s", email, exc)
        return jsonify({"error": "DSAR generation failed"}), 500


@retention_bp.route("/erasure", methods=["POST"])
@role_required("admin")
def erasure():
    """Process a GDPR erasure (right to be forgotten) request."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    if not email:
        return jsonify({"error": "email is required"}), 400

    processed_by = (
        getattr(g, "current_user", {}).get("username", "api") if hasattr(g, "current_user") else "api"
    )

    try:
        result = process_erasure_request(email, processed_by=processed_by)
        return jsonify(result), 200
    except Exception as exc:
        logger.error("Erasure request failed for %s: %s", email, exc)
        return jsonify({"error": "Erasure request failed"}), 500


# ---------------------------------------------------------------------------
# Data subject requests list
# ---------------------------------------------------------------------------

@retention_bp.route("/requests", methods=["GET"])
@role_required("admin")
def list_requests():
    """List all data subject requests (DSAR / erasure / portability)."""
    from education_system.platform.services.data_retention.models import (
        _connect as retention_connect,
        get_retention_db_path,
    )
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 500))

    status_filter = request.args.get("status")
    request_type_filter = request.args.get("request_type")

    conn = retention_connect(get_retention_db_path())
    try:
        sql = "SELECT * FROM data_subject_requests WHERE 1=1"
        params: list = []
        if status_filter:
            sql += " AND status = ?"
            params.append(status_filter)
        if request_type_filter:
            sql += " AND request_type = ?"
            params.append(request_type_filter)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        requests_list = [dict(r) for r in rows]
        return jsonify({"requests": requests_list, "count": len(requests_list)}), 200
    except Exception as exc:
        logger.error("Failed to fetch data subject requests: %s", exc)
        return jsonify({"error": "Failed to fetch requests"}), 500
    finally:
        conn.close()
