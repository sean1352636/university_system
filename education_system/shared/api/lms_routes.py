"""Flask blueprint for the LMS integration API.

Mounted at ``/api/v1/lms/`` by the unified server.

Endpoints
---------
GET  /connections                   List all LMS connections
POST /connections                   Add a new connection
DELETE /connections/<id>            Remove a connection
POST /connections/<id>/test         Test a connection
POST /connections/<id>/sync         Trigger a synchronisation run
GET  /sync-log                      View sync history (optional ?connection_id=)
GET  /mappings/<connection_id>      View ID mappings for a connection
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

lms_bp = Blueprint("lms", __name__)

# Module-level service instance – set by init_lms_routes()
_sync_service: Any = None


def init_lms_routes(db_path: str) -> None:
    """Initialise the LMS sync service with the given database path.

    Call this once before registering the blueprint with the Flask app.

    Args:
        db_path: Filesystem path to the SQLite database used for LMS data.
    """
    global _sync_service
    from education_system.shared.integrations.lms_sync_service import LMSSyncService

    _sync_service = LMSSyncService(db_path)
    logger.info("LMS routes initialised (db=%s)", db_path)


def _service():
    """Return the initialised sync service, raising if not yet configured."""
    if _sync_service is None:
        raise RuntimeError(
            "LMS routes have not been initialised. "
            "Call init_lms_routes(db_path) before starting the server."
        )
    return _sync_service


# ------------------------------------------------------------------ #
# Helper                                                                #
# ------------------------------------------------------------------ #

def _json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


# ------------------------------------------------------------------ #
# Routes                                                                #
# ------------------------------------------------------------------ #

@lms_bp.get("/connections")
def list_connections():
    """List all configured LMS connections.

    Query params:
        system_key (str, optional) – filter by system
        active_only (bool, optional) – only return active connections
    """
    system_key = request.args.get("system_key") or None
    active_only = request.args.get("active_only", "false").lower() in ("1", "true", "yes")
    try:
        connections = _service().list_connections(
            system_key=system_key, active_only=active_only
        )
        # Strip raw config (may contain credentials) from the public response
        for c in connections:
            c.pop("config_json", None)
        return jsonify({"connections": connections, "count": len(connections)})
    except Exception as exc:
        logger.exception("Failed to list LMS connections")
        return _json_error(str(exc), 500)


@lms_bp.post("/connections")
def add_connection():
    """Add a new LMS connection.

    Expected JSON body::

        {
            "system_key": "university",
            "provider_type": "canvas",
            "config": {
                "base_url": "https://canvas.example.com",
                "access_token": "..."
            },
            "is_active": true
        }
    """
    data = request.get_json(silent=True) or {}
    system_key = data.get("system_key", "").strip()
    provider_type = data.get("provider_type", "").strip()
    config = data.get("config", {})
    is_active = bool(data.get("is_active", True))

    if not system_key:
        return _json_error("'system_key' is required")
    if not provider_type:
        return _json_error("'provider_type' is required")
    if not isinstance(config, dict):
        return _json_error("'config' must be a JSON object")

    try:
        connection_id = _service().add_connection(
            system_key=system_key,
            provider_type=provider_type,
            config=config,
            is_active=is_active,
        )
        return jsonify({"id": connection_id, "message": "Connection added"}), 201
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("Failed to add LMS connection")
        return _json_error(str(exc), 500)


@lms_bp.delete("/connections/<int:connection_id>")
def remove_connection(connection_id: int):
    """Remove a connection and its associated sync history and mappings."""
    try:
        deleted = _service().remove_connection(connection_id)
        if not deleted:
            return _json_error(f"Connection {connection_id} not found", 404)
        return jsonify({"message": f"Connection {connection_id} removed"})
    except Exception as exc:
        logger.exception("Failed to remove LMS connection %d", connection_id)
        return _json_error(str(exc), 500)


@lms_bp.post("/connections/<int:connection_id>/test")
def test_connection(connection_id: int):
    """Test whether a stored LMS connection is reachable and the credentials valid."""
    try:
        connection = _service().get_connection(connection_id)
        if not connection:
            return _json_error(f"Connection {connection_id} not found", 404)

        provider = _service().get_provider(connection)
        result = provider.test_connection()
        status_code = 200 if result.get("ok") else 502
        return jsonify(result), status_code
    except Exception as exc:
        logger.exception("Connection test failed for id=%d", connection_id)
        return _json_error(str(exc), 500)


@lms_bp.post("/connections/<int:connection_id>/sync")
def trigger_sync(connection_id: int):
    """Trigger a synchronisation run for the specified connection.

    Optional JSON body::

        {"force_external_grades": false}

    When ``force_external_grades`` is true, grades fetched from the remote
    LMS will overwrite local data.  By default, internal grades are preserved.
    """
    data = request.get_json(silent=True) or {}
    force_external_grades = bool(data.get("force_external_grades", False))

    try:
        connection = _service().get_connection(connection_id)
        if not connection:
            return _json_error(f"Connection {connection_id} not found", 404)

        result = _service().sync_connection(
            connection_id, force_external_grades=force_external_grades
        )
        status_code = 200 if result.get("status") == "success" else 207
        return jsonify(result), status_code
    except Exception as exc:
        logger.exception("Sync failed for connection id=%d", connection_id)
        return _json_error(str(exc), 500)


@lms_bp.get("/sync-log")
def sync_log():
    """Return sync history, newest first.

    Query params:
        connection_id (int, optional) – filter to a single connection
        limit (int, optional, default 50) – max rows
    """
    try:
        connection_id_str = request.args.get("connection_id")
        connection_id = int(connection_id_str) if connection_id_str else None
        limit = min(int(request.args.get("limit", 50)), 500)
        history = _service().get_sync_history(
            connection_id=connection_id, limit=limit
        )
        return jsonify({"log": history, "count": len(history)})
    except ValueError:
        return _json_error("'connection_id' and 'limit' must be integers")
    except Exception as exc:
        logger.exception("Failed to retrieve sync log")
        return _json_error(str(exc), 500)


@lms_bp.get("/mappings/<int:connection_id>")
def get_mappings(connection_id: int):
    """Return all ID mappings for a connection.

    Query params:
        entity_type (str, optional) – e.g. ``course``, ``student``
    """
    try:
        connection = _service().get_connection(connection_id)
        if not connection:
            return _json_error(f"Connection {connection_id} not found", 404)

        entity_type = request.args.get("entity_type") or None
        mappings = _service().get_mappings(connection_id, entity_type=entity_type)
        return jsonify({"mappings": mappings, "count": len(mappings)})
    except Exception as exc:
        logger.exception(
            "Failed to retrieve mappings for connection %d", connection_id
        )
        return _json_error(str(exc), 500)
