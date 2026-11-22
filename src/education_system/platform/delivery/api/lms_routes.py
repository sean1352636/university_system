"""Flask blueprint for the LMS integration API.

Mounted at ``/api/v1/lms/`` by the unified server and, through
``registry.PLATFORM``, by the app factory.

A connection holds another system's credentials and a sync can overwrite local
grades, so every route needs a shared-login token, and a connection can only be
reached by an administrator of the system it belongs to. Being an administrator
of the nursery does not open the university's connections.

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
import os
from typing import Any

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.kernel.problems import problem
from education_system.platform.delivery.api.security.authentication import (
    is_superadmin_user,
    token_required,
)
from education_system.platform.kernel.core.system_keys import canonical_system_key

logger = logging.getLogger(__name__)

# The prefix is what the app factory mounts from; the unified server passes the
# same path explicitly.
lms_bp = Blueprint("lms", __name__, url_prefix="/api/lms")

# Module-level service instance – set by init_lms_routes(), or on first use
_sync_service: Any = None


def init_lms_routes(db_path: str) -> None:
    """Initialise the LMS sync service with the given database path.

    Call this once before registering the blueprint with the Flask app.

    Args:
        db_path: Filesystem path to the SQLite database used for LMS data.
    """
    global _sync_service
    from education_system.platform.integrations.external.lms_sync_service import LMSSyncService

    _sync_service = LMSSyncService(db_path)
    logger.info("LMS routes initialised (db=%s)", db_path)


def _default_db_path() -> str:
    """``LMS_DB_PATH``, else ``lms_integrations.db`` beside the auth database."""
    from education_system.platform.identity.auth.db import AUTH_DB_FILE

    return os.getenv(
        "LMS_DB_PATH", str(AUTH_DB_FILE).replace("auth.db", "lms_integrations.db"))


def _service():
    """Return the sync service, starting it on first use.

    The app factory mounts this from ``registry.PLATFORM``, which has no init
    hook, so it cannot rely on ``init_lms_routes`` having run.
    """
    if _sync_service is None:
        init_lms_routes(_default_db_path())
    return _sync_service


# ------------------------------------------------------------------ #
# Helper                                                                #
# ------------------------------------------------------------------ #

def _json_error(message: str, status: int = 400):
    return problem(status, message)


def _administers(system_key: str | None) -> bool:
    """Whether the caller may manage connections belonging to *system_key*."""
    if is_superadmin_user():
        return True
    target = canonical_system_key(system_key)
    return bool(target) and any(
        canonical_system_key(entry.get("system_key")) == target
        and str(entry.get("role") or "").lower() == "admin"
        for entry in g.current_user.get("systems") or ())


def _administered_connections(system_key=None, active_only=False) -> list[dict]:
    return [c for c in _service().list_connections(system_key=system_key,
                                                   active_only=active_only)
            if _administers(c.get("system_key"))]


def _deny_unless_lms_admin():
    """403 unless the caller administers at least one system."""
    if is_superadmin_user() or any(
            str(entry.get("role") or "").lower() == "admin"
            for entry in g.current_user.get("systems") or ()):
        return None
    return _json_error("Requires an administrator", 403)


def _connection_or_denial(connection_id: int):
    """``(connection, None)``, or ``(None, response)``.

    A connection in another system's care reads as missing, so ids cannot be
    probed across systems.
    """
    denied = _deny_unless_lms_admin()
    if denied is not None:
        return None, denied
    connection = _service().get_connection(connection_id)
    if not connection or not _administers(connection.get("system_key")):
        return None, _json_error(f"Connection {connection_id} not found", 404)
    return connection, None


# ------------------------------------------------------------------ #
# Routes                                                                #
# ------------------------------------------------------------------ #

@lms_bp.get("/connections")
@token_required
def list_connections():
    """List all configured LMS connections.

    Query params:
        system_key (str, optional) – filter by system
        active_only (bool, optional) – only return active connections
    """
    denied = _deny_unless_lms_admin()
    if denied is not None:
        return denied
    system_key = request.args.get("system_key") or None
    active_only = request.args.get("active_only", "false").lower() in ("1", "true", "yes")
    try:
        connections = _administered_connections(system_key, active_only)
        # Strip raw config (may contain credentials) from the public response
        for c in connections:
            c.pop("config_json", None)
        return jsonify({"connections": connections, "count": len(connections)})
    except Exception:
        logger.exception("Failed to list LMS connections")
        return _json_error("Failed to list LMS connections", 500)


@lms_bp.post("/connections")
@token_required
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
    denied = _deny_unless_lms_admin()
    if denied is not None:
        return denied
    data = request.get_json(silent=True) or {}
    system_key = str(data.get("system_key") or "").strip()
    provider_type = str(data.get("provider_type") or "").strip()
    config = data.get("config", {})
    is_active = bool(data.get("is_active", True))

    if not system_key:
        return _json_error("'system_key' is required")
    if not provider_type:
        return _json_error("'provider_type' is required")
    if not isinstance(config, dict):
        return _json_error("'config' must be a JSON object")
    if not _administers(system_key):
        return _json_error("You do not administer that system", 403)

    try:
        connection_id = _service().add_connection(
            system_key=system_key,
            provider_type=provider_type,
            config=config,
            is_active=is_active,
        )
        return jsonify({"id": connection_id, "message": "Connection added"}), 201
    except ValueError as exc:
        logger.warning("Invalid LMS connection request: %s", exc)
        return _json_error("Invalid connection configuration")
    except Exception:
        logger.exception("Failed to add LMS connection")
        return _json_error("Failed to add LMS connection", 500)


@lms_bp.delete("/connections/<int:connection_id>")
@token_required
def remove_connection(connection_id: int):
    """Remove a connection and its associated sync history and mappings."""
    try:
        _, denied = _connection_or_denial(connection_id)
        if denied is not None:
            return denied
        deleted = _service().remove_connection(connection_id)
        if not deleted:
            return _json_error(f"Connection {connection_id} not found", 404)
        return jsonify({"message": f"Connection {connection_id} removed"})
    except Exception:
        logger.exception("Failed to remove LMS connection %d", connection_id)
        return _json_error("Failed to remove connection", 500)


@lms_bp.post("/connections/<int:connection_id>/test")
@token_required
def test_connection(connection_id: int):
    """Test whether a stored LMS connection is reachable and the credentials valid."""
    try:
        connection, denied = _connection_or_denial(connection_id)
        if denied is not None:
            return denied

        provider = _service().get_provider(connection)
        result = provider.test_connection()
        status_code = 200 if result.get("ok") else 502
        return jsonify(result), status_code
    except Exception:
        logger.exception("Connection test failed for id=%d", connection_id)
        return _json_error("Connection test failed", 500)


@lms_bp.post("/connections/<int:connection_id>/sync")
@token_required
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
        _, denied = _connection_or_denial(connection_id)
        if denied is not None:
            return denied

        result = _service().sync_connection(
            connection_id, force_external_grades=force_external_grades
        )
        status_code = 200 if result.get("status") == "success" else 207
        return jsonify(result), status_code
    except Exception:
        logger.exception("Sync failed for connection id=%d", connection_id)
        return _json_error("Sync operation failed", 500)


@lms_bp.get("/sync-log")
@token_required
def sync_log():
    """Return sync history, newest first.

    Query params:
        connection_id (int, optional) – filter to a single connection
        limit (int, optional, default 50) – max rows
    """
    denied = _deny_unless_lms_admin()
    if denied is not None:
        return denied
    try:
        connection_id_str = request.args.get("connection_id")
        connection_id = int(connection_id_str) if connection_id_str else None
        limit = max(1, min(int(request.args.get("limit", 50)), 500))
        if connection_id is not None:
            _, denied = _connection_or_denial(connection_id)
            if denied is not None:
                return denied
            history = _service().get_sync_history(connection_id=connection_id, limit=limit)
        else:
            # Each permitted connection's newest rows, then the newest overall.
            history = []
            for connection in _administered_connections():
                history += _service().get_sync_history(
                    connection_id=connection["id"], limit=limit)
            history = sorted(history, key=lambda row: row["id"], reverse=True)[:limit]
        return jsonify({"log": history, "count": len(history)})
    except ValueError:
        return _json_error("'connection_id' and 'limit' must be integers")
    except Exception:
        logger.exception("Failed to retrieve sync log")
        return _json_error("Failed to retrieve the sync log", 500)


@lms_bp.get("/mappings/<int:connection_id>")
@token_required
def get_mappings(connection_id: int):
    """Return all ID mappings for a connection.

    Query params:
        entity_type (str, optional) – e.g. ``course``, ``student``
    """
    try:
        _, denied = _connection_or_denial(connection_id)
        if denied is not None:
            return denied

        entity_type = request.args.get("entity_type") or None
        mappings = _service().get_mappings(connection_id, entity_type=entity_type)
        return jsonify({"mappings": mappings, "count": len(mappings)})
    except Exception:
        logger.exception(
            "Failed to retrieve mappings for connection %d", connection_id
        )
        return _json_error("Failed to retrieve mappings", 500)
