"""ORM-style helpers for the central tenants database.

All tenant metadata is stored in a single SQLite database at::

    education_system/shared/data/db_files/tenants.db

Tables
------
tenants       — one row per institution / tenant
tenant_users  — maps auth ``users.id`` values to tenants with a per-tenant role
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from education_system.shared.core.tenant import Tenant

logger = logging.getLogger(__name__)

# ── Default path for the central tenants DB ──────────────────────────────────

_SHARED_ROOT = Path(__file__).resolve().parent.parent   # …/shared/
_DEFAULT_TENANTS_DB = _SHARED_ROOT / "data" / "db_files" / "tenants.db"


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or str(_DEFAULT_TENANTS_DB)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema initialisation ────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tenants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    slug        TEXT    NOT NULL UNIQUE,
    subdomain   TEXT    NOT NULL UNIQUE,
    config_json TEXT    NOT NULL DEFAULT '{}',
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'member',
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL,
    UNIQUE (tenant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_tenants_slug      ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_subdomain ON tenants(subdomain);
CREATE INDEX IF NOT EXISTS idx_tenant_users_tid  ON tenant_users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_uid  ON tenant_users(user_id);
"""


def init_tenant_db(db_path: str | None = None) -> None:
    """Create the tenants schema if it does not already exist.

    Safe to call repeatedly — uses ``CREATE TABLE IF NOT EXISTS``.
    """
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        logger.debug("Tenant DB schema verified at %s", db_path or _DEFAULT_TENANTS_DB)
    finally:
        conn.close()


# ── Row → Tenant helper ───────────────────────────────────────────────────────

def _row_to_tenant(row: sqlite3.Row) -> Tenant:
    config: dict = {}
    try:
        config = json.loads(row["config_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        pass
    return Tenant(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        subdomain=row["subdomain"],
        config=config,
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
    )


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_tenant_by_slug(slug: str, db_path: str | None = None) -> Optional[Tenant]:
    """Return the Tenant with the given slug, or None if not found."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tenants WHERE slug = ?", (slug,)
        ).fetchone()
        return _row_to_tenant(row) if row else None
    finally:
        conn.close()


def get_tenant_by_subdomain(subdomain: str, db_path: str | None = None) -> Optional[Tenant]:
    """Return the Tenant matching *subdomain*, or None."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tenants WHERE subdomain = ?", (subdomain,)
        ).fetchone()
        return _row_to_tenant(row) if row else None
    finally:
        conn.close()


def get_tenant_by_id(tenant_id: int, db_path: str | None = None) -> Optional[Tenant]:
    """Return the Tenant with *tenant_id*, or None."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tenants WHERE id = ?", (tenant_id,)
        ).fetchone()
        return _row_to_tenant(row) if row else None
    finally:
        conn.close()


def get_all_tenants(
    active_only: bool = False,
    db_path: str | None = None,
) -> list[Tenant]:
    """Return all tenants, optionally filtering to active ones only."""
    conn = _connect(db_path)
    try:
        sql = "SELECT * FROM tenants"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY name"
        rows = conn.execute(sql).fetchall()
        return [_row_to_tenant(r) for r in rows]
    finally:
        conn.close()


# ── Write helpers ─────────────────────────────────────────────────────────────

def create_tenant(
    name: str,
    slug: str,
    subdomain: str | None = None,
    config: dict | None = None,
    db_path: str | None = None,
) -> Tenant:
    """Insert a new tenant row and return the created Tenant.

    *subdomain* defaults to *slug* if not provided.
    """
    subdomain = subdomain or slug
    config_json = json.dumps(config or {})
    now = datetime.utcnow().isoformat()
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO tenants (name, slug, subdomain, config_json, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (name, slug, subdomain, config_json, now, now),
        )
        conn.commit()
        tenant_id = cursor.lastrowid
        logger.info("Created tenant id=%d slug=%r", tenant_id, slug)
        return Tenant(
            id=tenant_id,
            name=name,
            slug=slug,
            subdomain=subdomain,
            config=config or {},
            is_active=True,
            created_at=now,
        )
    finally:
        conn.close()


def update_tenant(
    tenant_id: int,
    *,
    name: str | None = None,
    config: dict | None = None,
    subdomain: str | None = None,
    db_path: str | None = None,
) -> bool:
    """Update mutable fields on an existing tenant.

    Only non-None keyword arguments are applied. Returns True if a row was
    updated.
    """
    now = datetime.utcnow().isoformat()
    conn = _connect(db_path)
    try:
        # Fetch current values first
        row = conn.execute(
            "SELECT * FROM tenants WHERE id = ?", (tenant_id,)
        ).fetchone()
        if not row:
            return False

        new_name = name if name is not None else row["name"]
        new_subdomain = subdomain if subdomain is not None else row["subdomain"]
        if config is not None:
            new_config_json = json.dumps(config)
        else:
            new_config_json = row["config_json"]

        conn.execute(
            """UPDATE tenants
               SET name = ?, subdomain = ?, config_json = ?, updated_at = ?
               WHERE id = ?""",
            (new_name, new_subdomain, new_config_json, now, tenant_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def deactivate_tenant(tenant_id: int, db_path: str | None = None) -> bool:
    """Mark a tenant as inactive (soft delete). Returns True if found."""
    now = datetime.utcnow().isoformat()
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE tenants SET is_active = 0, updated_at = ? WHERE id = ?",
            (now, tenant_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def reactivate_tenant(tenant_id: int, db_path: str | None = None) -> bool:
    """Re-enable a previously deactivated tenant. Returns True if found."""
    now = datetime.utcnow().isoformat()
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE tenants SET is_active = 1, updated_at = ? WHERE id = ?",
            (now, tenant_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Tenant–user mapping ───────────────────────────────────────────────────────

def add_user_to_tenant(
    tenant_id: int,
    user_id: int,
    role: str = "member",
    db_path: str | None = None,
) -> bool:
    """Assign *user_id* to *tenant_id* with *role*.

    If the mapping already exists it is updated (role + is_active).
    Returns True on success.
    """
    now = datetime.utcnow().isoformat()
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO tenant_users (tenant_id, user_id, role, is_active, created_at)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT (tenant_id, user_id) DO UPDATE
               SET role = excluded.role, is_active = 1""",
            (tenant_id, user_id, role, now),
        )
        conn.commit()
        return True
    except sqlite3.Error as exc:
        logger.error("add_user_to_tenant failed: %s", exc)
        return False
    finally:
        conn.close()


def get_tenant_users(
    tenant_id: int,
    active_only: bool = True,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Return user records for all members of *tenant_id*."""
    conn = _connect(db_path)
    try:
        sql = "SELECT * FROM tenant_users WHERE tenant_id = ?"
        params: tuple = (tenant_id,)
        if active_only:
            sql += " AND is_active = 1"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_tenants(
    user_id: int,
    active_only: bool = True,
    db_path: str | None = None,
) -> list[Tenant]:
    """Return all Tenant objects that *user_id* belongs to."""
    conn = _connect(db_path)
    try:
        sql = """
            SELECT t.* FROM tenants t
            JOIN tenant_users tu ON tu.tenant_id = t.id
            WHERE tu.user_id = ?
        """
        params: tuple = (user_id,)
        if active_only:
            sql += " AND tu.is_active = 1 AND t.is_active = 1"
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_tenant(r) for r in rows]
    finally:
        conn.close()
