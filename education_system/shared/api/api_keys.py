"""API key authentication for service-to-service and third-party integrations.

Lower Priority #9: Static API keys that don't require JWT/user login.

API keys are stored in the shared auth database. Each key has:
- A hashed key value (bcrypt)
- A label/description
- Allowed systems (e.g. ["college", "university"])
- An optional rate limit override
- Active/revoked status

Usage:
    # In route handlers:
    from education_system.shared.api.api_keys import api_key_required

    @app.route("/api/v1/college/external/students")
    @api_key_required("college")
    def external_students():
        # g.api_key_info has key metadata
        ...

    # Admin: create a key
    from education_system.shared.api.api_keys import APIKeyManager
    mgr = APIKeyManager(db_path)
    raw_key = mgr.create_key("MIS Integration", systems=["college"])
    # raw_key is shown once, then only the hash is stored
"""

import hashlib
import logging
import secrets
import sqlite3
import functools
from datetime import datetime

from flask import request, jsonify, g

logger = logging.getLogger(__name__)

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    label TEXT NOT NULL,
    systems TEXT NOT NULL DEFAULT '[]',
    rate_limit INTEGER,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    created_by INTEGER
);
CREATE INDEX IF NOT EXISTS idx_api_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_key_prefix ON api_keys(key_prefix);
"""


def _hash_key(raw_key: str) -> str:
    """Hash an API key using HMAC-SHA256 (fast lookup, key is already high-entropy)."""
    import hmac
    return hmac.new(b'api-key-hash', raw_key.encode(), hashlib.sha256).hexdigest()


class APIKeyManager:
    """Manage API keys in the auth database."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._conn()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    def create_key(self, label: str, systems: list[str] | None = None,
                   rate_limit: int | None = None, created_by: int | None = None) -> str:
        """Create a new API key. Returns the raw key (shown once)."""
        import json
        raw_key = f"edusys_{secrets.token_urlsafe(32)}"
        key_hash = _hash_key(raw_key)
        key_prefix = raw_key[:12]
        systems_json = json.dumps(systems or [])

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO api_keys (key_hash, key_prefix, label, systems,
                   rate_limit, created_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (key_hash, key_prefix, label, systems_json, rate_limit,
                 datetime.utcnow().isoformat(), created_by),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info("API auth handle created: %s... (%s)", key_prefix, label)  # nosemgrep: python-logger-credential-disclosure
        return raw_key

    def validate_key(self, raw_key: str) -> dict | None:
        """Validate an API key. Returns key info or None."""
        import json
        key_hash = _hash_key(raw_key)
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE key_hash = ? AND active = 1",
                (key_hash,),
            ).fetchone()
            if not row:
                return None
            # Update last_used_at
            conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), row["id"]),
            )
            conn.commit()
            return {
                "id": row["id"],
                "label": row["label"],
                "systems": json.loads(row["systems"]),
                "rate_limit": row["rate_limit"],
                "prefix": row["key_prefix"],
            }
        finally:
            conn.close()

    def list_keys(self) -> list[dict]:
        """List all API keys (without hashes)."""
        import json
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, key_prefix, label, systems, rate_limit, active, "
                "created_at, last_used_at FROM api_keys ORDER BY created_at DESC"
            ).fetchall()
            return [{
                "id": r["id"],
                "prefix": r["key_prefix"],
                "label": r["label"],
                "systems": json.loads(r["systems"]),
                "rate_limit": r["rate_limit"],
                "active": bool(r["active"]),
                "created_at": r["created_at"],
                "last_used_at": r["last_used_at"],
            } for r in rows]
        finally:
            conn.close()

    def revoke_key(self, key_id: int) -> bool:
        """Revoke an API key by ID."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "UPDATE api_keys SET active = 0 WHERE id = ?", (key_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


# ── Singleton manager (initialised lazily) ───────────────────────────────

_manager: APIKeyManager | None = None


def init_api_keys(db_path: str) -> None:
    """Initialise the API key manager. Call once during app setup."""
    global _manager
    _manager = APIKeyManager(db_path)


def get_manager() -> APIKeyManager:
    """Get the API key manager instance."""
    if _manager is None:
        raise RuntimeError("API key manager not initialised. Call init_api_keys() first.")
    return _manager


# ── Decorator ────────────────────────────────────────────────────────────

def api_key_required(system: str | None = None):
    """Decorator to require a valid API key via X-API-Key header.

    Can be used alongside or instead of JWT auth. If both an API key and
    a JWT are present, the API key takes precedence.

    Args:
        system: If set, the API key must have access to this system.
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            raw_key = request.headers.get("X-API-Key")
            if not raw_key:
                return jsonify({"error": "API key required (X-API-Key header)"}), 401

            if _manager is None:
                return jsonify({"error": "API key authentication not configured"}), 500

            info = _manager.validate_key(raw_key)
            if not info:
                return jsonify({"error": "Invalid or revoked API key"}), 401

            if system and info["systems"] and system not in info["systems"]:
                return jsonify({
                    "error": "API key does not have access to this system",
                    "system": system,
                }), 403

            g.api_key_info = info
            return f(*args, **kwargs)
        return decorated
    return decorator


def api_key_or_token(system: str | None = None):
    """Accept either an API key (X-API-Key) or a JWT Bearer token.

    Sets g.api_key_info if API key used, g.current_user if JWT used.
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            # Try API key first
            raw_key = request.headers.get("X-API-Key")
            if raw_key and _manager:
                info = _manager.validate_key(raw_key)
                if info:
                    if system and info["systems"] and system not in info["systems"]:
                        return jsonify({"error": "API key does not have access to this system"}), 403
                    g.api_key_info = info
                    return f(*args, **kwargs)

            # Fall back to JWT
            from education_system.shared.api.auth import token_required
            @functools.wraps(f)
            @token_required
            def jwt_wrapper(*a, **kw):
                return f(*a, **kw)
            return jwt_wrapper(*args, **kwargs)
        return decorated
    return decorator
