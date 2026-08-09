"""Permissions overlay for Sixth Form User Management.

The shared auth layer keeps a numeric role hierarchy (admin > staff >
teacher > … > student) but no formal permission catalogue. This
module layers one on top **without** changing the shared layer:

* a fixed ``PERMISSIONS`` catalogue covering the actions an admin
  cares about gating (manage_accommodations, run_reports, edit_user, …);
* ``role_definitions`` + ``role_permissions`` tables — *editable* role
  defs that the UI surfaces as "Role editor". Falls back to a default
  mapping if no row exists for a role yet;
* ``user_permission_overrides`` for per-user grant/revoke;
* helpers for **diff** (between two roles, or two users) and
  **explain** ("why does user X have permission Y?").

Resolution order, highest priority first:
    1. user_permission_overrides (mode='revoke')
    2. user_permission_overrides (mode='grant')
    3. role permission rows
    4. catalogue default (DEFAULT_ROLE_PERMS)
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.platform.identity.auth.role_manager import ROLE_HIERARCHY
from education_system.systems.sixth_form.domain.governance.user_management import (
    lifecycle,
)
from education_system.systems.sixth_form.interfaces import user_accounts as _ua
from education_system.systems.sixth_form.interfaces.user_accounts import (
    SYSTEM_KEY, UserAccountError,
)

logger = logging.getLogger(__name__)


# ── Catalogue ─────────────────────────────────────────────────────────

PERMISSIONS: dict[str, str] = {
    # User management itself
    "manage_users":         "Create / edit / archive / delete users",
    "manage_roles":         "Edit role definitions and grants",
    "view_user_audit":      "View user-management audit log",
    "approve_sensitive":    "Approve two-person-rule actions",
    # Academic / pastoral
    "manage_students":      "Edit student records and enrolments",
    "view_students":        "Read student records",
    "manage_attendance":    "Take and edit attendance",
    "manage_gradebook":     "Edit grades and assessments",
    "view_gradebook":       "Read grades",
    "manage_behaviour":     "Record / edit behaviour incidents",
    "view_safeguarding":    "Read safeguarding records",
    "manage_safeguarding":  "Record / edit safeguarding concerns",
    # Operations
    "manage_finance":       "Edit fees / bursaries / receipts",
    "view_finance":         "Read financial records",
    "manage_reports":       "Build and run reports",
    "manage_settings":      "Edit system settings",
    "manage_comms":         "Send broadcasts and notices",
    # Student-self-service
    "view_own_record":      "Read own profile / timetable / grades",
}


DEFAULT_ROLE_PERMS: dict[str, set[str]] = {
    "admin":   set(PERMISSIONS),
    "staff": {
        "manage_users", "manage_students", "view_students",
        "manage_attendance", "manage_gradebook", "view_gradebook",
        "manage_behaviour", "view_safeguarding", "manage_reports",
        "manage_comms", "view_finance",
    },
    "teacher": {
        "view_students", "manage_attendance", "manage_gradebook",
        "view_gradebook", "manage_behaviour", "view_safeguarding",
    },
    "instructor": {
        "view_students", "manage_attendance", "manage_gradebook",
        "view_gradebook",
    },
    "teaching_assistant": {
        "view_students", "view_gradebook",
    },
    "parent": {
        "view_own_record",
    },
    "student": {
        "view_own_record",
    },
}


# ── Schema ────────────────────────────────────────────────────────────

def init_permissions_schema(auth: Any) -> None:
    """Create the overlay tables. Idempotent."""
    try:
        conn = lifecycle._conn(auth)
        try:
            # Role definitions — additive over ROLE_HIERARCHY (a row
            # here represents an *editable* version of a built-in role
            # or an entirely new custom role).
            conn.execute('''
                CREATE TABLE IF NOT EXISTS role_definitions (
                    role_key TEXT PRIMARY KEY,
                    label TEXT,
                    description TEXT,
                    is_custom INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    created_by TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_key TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    PRIMARY KEY (role_key, permission)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_permission_overrides (
                    user_id INTEGER NOT NULL,
                    system_key TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    mode TEXT NOT NULL,        -- 'grant' | 'revoke'
                    reason TEXT,
                    set_by TEXT,
                    set_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, system_key, permission)
                )
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("permissions schema init failed")
        raise


# ── Role definition CRUD ──────────────────────────────────────────────

@dataclass
class RoleDef:
    role_key: str
    label: str
    description: str
    is_custom: bool
    permissions: set[str] = field(default_factory=set)


def list_roles(auth: Any) -> list[RoleDef]:
    """Return every known role: built-in roles (with stored or default
    permissions) and any custom roles defined in the overlay."""
    init_permissions_schema(auth)
    stored = _stored_role_defs(auth)
    stored_perms = _stored_role_perms(auth)
    out: list[RoleDef] = []
    seen: set[str] = set()
    for role_key in ROLE_HIERARCHY:
        seen.add(role_key)
        info = stored.get(role_key) or {}
        out.append(RoleDef(
            role_key=role_key,
            label=info.get('label') or role_key.replace('_', ' ').title(),
            description=info.get('description') or "",
            is_custom=False,
            permissions=stored_perms.get(role_key,
                                          set(DEFAULT_ROLE_PERMS.get(
                                              role_key, set()))),
        ))
    # Custom roles
    for role_key, info in stored.items():
        if role_key in seen:
            continue
        out.append(RoleDef(
            role_key=role_key,
            label=info.get('label') or role_key,
            description=info.get('description') or "",
            is_custom=bool(info.get('is_custom', 1)),
            permissions=stored_perms.get(role_key, set()),
        ))
    return out


def _stored_role_defs(auth: Any) -> dict[str, dict]:
    try:
        conn = lifecycle._conn(auth)
        try:
            return {r["role_key"]: dict(r) for r in conn.execute(
                "SELECT * FROM role_definitions").fetchall()}
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("_stored_role_defs failed")
        return {}


def _stored_role_perms(auth: Any) -> dict[str, set[str]]:
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute(
                "SELECT role_key, permission FROM role_permissions"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("_stored_role_perms failed")
        return {}
    out: dict[str, set[str]] = {}
    for r in rows:
        out.setdefault(r["role_key"], set()).add(r["permission"])
    return out


def get_role(auth: Any, role_key: str) -> RoleDef:
    for r in list_roles(auth):
        if r.role_key == role_key:
            return r
    raise UserAccountError(f"Unknown role: {role_key!r}")


def create_role(auth: Any, role_key: str, *,
                 label: str | None = None,
                 description: str | None = None,
                 permissions: set[str] | None = None) -> RoleDef:
    """Create a new custom role. Refuses if the key already exists or
    collides with a built-in."""
    init_permissions_schema(auth)
    if role_key in ROLE_HIERARCHY:
        raise UserAccountError(
            f"{role_key!r} is a built-in role — use update_role to "
            "change its permissions instead.")
    if role_key in {r.role_key for r in list_roles(auth)}:
        raise UserAccountError(f"Role {role_key!r} already exists.")
    perms = {p for p in (permissions or set()) if p in PERMISSIONS}
    import datetime
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute(
                "INSERT INTO role_definitions "
                "(role_key, label, description, is_custom, created_at, "
                "created_by) VALUES (?, ?, ?, 1, ?, ?)",
                (role_key, label or role_key, description, now, actor))
            for p in perms:
                conn.execute(
                    "INSERT OR IGNORE INTO role_permissions "
                    "(role_key, permission) VALUES (?, ?)",
                    (role_key, p))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("create_role failed")
        raise UserAccountError(f"Could not create role: {e}") from e
    lifecycle._audit(auth, "role_create", None,
                      {"role_key": role_key, "permissions": list(perms)})
    return get_role(auth, role_key)


def clone_role(auth: Any, source_key: str, new_key: str, *,
                label: str | None = None) -> RoleDef:
    src = get_role(auth, source_key)
    return create_role(
        auth, new_key, label=label or f"{src.label} (copy)",
        description=src.description, permissions=set(src.permissions))


def rename_role(auth: Any, role_key: str, *,
                 new_label: str | None = None,
                 new_description: str | None = None) -> RoleDef:
    init_permissions_schema(auth)
    if role_key not in {r.role_key for r in list_roles(auth)}:
        raise UserAccountError(f"Unknown role: {role_key!r}")
    try:
        conn = lifecycle._conn(auth)
        try:
            existing = conn.execute(
                "SELECT 1 FROM role_definitions WHERE role_key = ?",
                (role_key,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE role_definitions SET label = COALESCE(?, label), "
                    "description = COALESCE(?, description) WHERE role_key = ?",
                    (new_label, new_description, role_key))
            else:
                # Built-in with no row yet — write one so the edit sticks.
                import datetime
                now = datetime.datetime.now().isoformat(timespec='seconds')
                conn.execute(
                    "INSERT INTO role_definitions "
                    "(role_key, label, description, is_custom, "
                    "created_at, created_by) VALUES (?, ?, ?, 0, ?, ?)",
                    (role_key, new_label or role_key, new_description or "",
                     now, lifecycle._actor_name(auth)))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("rename_role failed")
        raise UserAccountError(f"Could not rename role: {e}") from e
    lifecycle._audit(auth, "role_rename", None,
                      {"role_key": role_key, "new_label": new_label})
    return get_role(auth, role_key)


def delete_role(auth: Any, role_key: str) -> None:
    """Delete a *custom* role. Built-ins can't be deleted."""
    if role_key in ROLE_HIERARCHY:
        raise UserAccountError(
            f"{role_key!r} is built-in and cannot be deleted.")
    init_permissions_schema(auth)
    # Block deletion if users are still assigned.
    try:
        conn = lifecycle._conn(auth)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM user_systems WHERE role = ?",
                (role_key,)).fetchone()[0]
            if n:
                raise UserAccountError(
                    f"{n} user(s) still hold this role — reassign them "
                    "first.")
            conn.execute(
                "DELETE FROM role_permissions WHERE role_key = ?",
                (role_key,))
            conn.execute(
                "DELETE FROM role_definitions WHERE role_key = ?",
                (role_key,))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("delete_role failed")
        raise UserAccountError(f"Could not delete role: {e}") from e
    lifecycle._audit(auth, "role_delete", None, {"role_key": role_key})


def set_role_permissions(auth: Any, role_key: str,
                          permissions: set[str]) -> RoleDef:
    """Replace a role's permission set."""
    init_permissions_schema(auth)
    # Validate
    bad = {p for p in permissions if p not in PERMISSIONS}
    if bad:
        raise UserAccountError(
            f"Unknown permission(s): {', '.join(sorted(bad))}")
    # Ensure the role row exists so the edit sticks for built-ins.
    if role_key not in _stored_role_defs(auth):
        try:
            conn = lifecycle._conn(auth)
            try:
                import datetime
                now = datetime.datetime.now().isoformat(timespec='seconds')
                conn.execute(
                    "INSERT OR IGNORE INTO role_definitions "
                    "(role_key, label, description, is_custom, "
                    "created_at, created_by) VALUES (?, ?, ?, ?, ?, ?)",
                    (role_key, role_key, "",
                     0 if role_key in ROLE_HIERARCHY else 1,
                     now, lifecycle._actor_name(auth)))
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error:
            logger.exception("set_role_permissions: def upsert failed")
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute(
                "DELETE FROM role_permissions WHERE role_key = ?",
                (role_key,))
            for p in permissions:
                conn.execute(
                    "INSERT INTO role_permissions "
                    "(role_key, permission) VALUES (?, ?)",
                    (role_key, p))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("set_role_permissions failed")
        raise UserAccountError(f"Could not save: {e}") from e
    lifecycle._audit(auth, "role_perms_set", None,
                      {"role_key": role_key,
                       "permissions": sorted(permissions)})
    return get_role(auth, role_key)


# ── User-level overrides ──────────────────────────────────────────────

def set_user_override(auth: Any, user_id: int, permission: str,
                       mode: str, *, system_key: str = SYSTEM_KEY,
                       reason: str | None = None) -> None:
    if permission not in PERMISSIONS:
        raise UserAccountError(f"Unknown permission: {permission!r}")
    if mode not in ("grant", "revoke"):
        raise UserAccountError("mode must be 'grant' or 'revoke'.")
    init_permissions_schema(auth)
    import datetime
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                INSERT INTO user_permission_overrides
                (user_id, system_key, permission, mode, reason, set_by,
                 set_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, system_key, permission) DO UPDATE
                SET mode=excluded.mode, reason=excluded.reason,
                    set_by=excluded.set_by, set_at=excluded.set_at
            ''', (user_id, system_key, permission, mode, reason,
                  actor, now))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("set_user_override failed")
        raise UserAccountError(f"Could not save override: {e}") from e
    lifecycle._audit(auth, "user_perm_override", user_id, {
        "system_key": system_key, "permission": permission,
        "mode": mode, "reason": reason,
    })


def clear_user_override(auth: Any, user_id: int, permission: str,
                         *, system_key: str = SYSTEM_KEY) -> bool:
    init_permissions_schema(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute(
                "DELETE FROM user_permission_overrides "
                "WHERE user_id = ? AND system_key = ? AND permission = ?",
                (user_id, system_key, permission))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("clear_user_override failed")
        return False


def list_user_overrides(auth: Any, user_id: int,
                          *, system_key: str | None = None
                          ) -> list[dict]:
    init_permissions_schema(auth)
    sql = "SELECT * FROM user_permission_overrides WHERE user_id = ?"
    args: list = [user_id]
    if system_key:
        sql += " AND system_key = ?"
        args.append(system_key)
    sql += " ORDER BY permission"
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_user_overrides failed")
        return []


# ── Resolution helpers ────────────────────────────────────────────────

@dataclass
class PermissionTrace:
    user_id: int
    permission: str
    system_key: str
    granted: bool
    source: str
    detail: str


def role_permissions(auth: Any, role_key: str) -> set[str]:
    """All permissions for a role, falling back to the catalogue
    default if no override row exists."""
    stored = _stored_role_perms(auth)
    if role_key in stored:
        return set(stored[role_key])
    return set(DEFAULT_ROLE_PERMS.get(role_key, set()))


def effective_permissions(auth: Any, user_id: int,
                           *, system_key: str = SYSTEM_KEY) -> set[str]:
    """Compute the user's effective permission set for a given
    system, applying role then overrides."""
    user = _ua.get_user(auth, user_id)
    if user is None:
        return set()
    role = user.role_for(system_key)
    perms = set(role_permissions(auth, role)) if role else set()
    for ov in list_user_overrides(auth, user_id, system_key=system_key):
        if ov["mode"] == "grant":
            perms.add(ov["permission"])
        elif ov["mode"] == "revoke":
            perms.discard(ov["permission"])
    return perms


def explain_permission(auth: Any, user_id: int, permission: str,
                        *, system_key: str = SYSTEM_KEY
                        ) -> PermissionTrace:
    """Resolution-order trace: user revoke > user grant > role > none."""
    user = _ua.get_user(auth, user_id)
    if user is None:
        return PermissionTrace(user_id, permission, system_key, False,
                                 "missing", "User not found.")
    overrides = {ov["permission"]: ov
                  for ov in list_user_overrides(
                      auth, user_id, system_key=system_key)}
    if permission in overrides:
        ov = overrides[permission]
        granted = ov["mode"] == "grant"
        return PermissionTrace(
            user_id, permission, system_key,
            granted=granted,
            source=f"user_override:{ov['mode']}",
            detail=(f"Set by {ov.get('set_by') or '?'} on "
                     f"{ov.get('set_at')}; "
                     f"reason: {ov.get('reason') or '—'}"))
    role = user.role_for(system_key)
    if not role:
        return PermissionTrace(user_id, permission, system_key, False,
                                 "no_role",
                                 f"User has no role for system "
                                 f"{system_key!r}.")
    perms = role_permissions(auth, role)
    if permission in perms:
        return PermissionTrace(user_id, permission, system_key, True,
                                 f"role:{role}",
                                 f"Inherited from role {role!r}.")
    return PermissionTrace(user_id, permission, system_key, False,
                             f"role:{role}",
                             f"Role {role!r} does not include this "
                             "permission.")


# ── Diffs ─────────────────────────────────────────────────────────────

@dataclass
class PermissionDiff:
    only_a: set[str] = field(default_factory=set)
    only_b: set[str] = field(default_factory=set)
    shared: set[str] = field(default_factory=set)


def diff_roles(auth: Any, role_a: str, role_b: str) -> PermissionDiff:
    a = role_permissions(auth, role_a)
    b = role_permissions(auth, role_b)
    return PermissionDiff(only_a=a - b, only_b=b - a, shared=a & b)


def diff_users(auth: Any, user_a: int, user_b: int,
                *, system_key: str = SYSTEM_KEY) -> PermissionDiff:
    a = effective_permissions(auth, user_a, system_key=system_key)
    b = effective_permissions(auth, user_b, system_key=system_key)
    return PermissionDiff(only_a=a - b, only_b=b - a, shared=a & b)
