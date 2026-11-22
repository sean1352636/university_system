"""Who may use the restaurant, and what they may do there.

A login is linked to one ``restaurant_staff`` record and given one restaurant
role. Employment details stay on the staff record; this module only holds
access.

Restaurant roles are deliberately never added to the login session. Names such
as ``manage_finances`` are also checked by the university's own finance
screens, so a session grant would let a restaurant Finance user into those too.
Restaurant screens ask :func:`can` instead, which applies these rules:

* an administrator keeps their normal permissions;
* anyone with an access row is decided by that row alone, so removing access
  takes everything away, including what their login role would normally allow;
* access only counts while the linked staff record is Active;
* anyone with no row keeps what their login role already gives them.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from education_system.platform.identity.auth import db as auth_db
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from education_system.systems.university.infrastructure.sql_safety import escape_like

logger = logging.getLogger(__name__)

MANAGER = "Manager"
ROLE_PERMISSIONS = {
    MANAGER: frozenset({
        "manage_menu", "manage_inventory", "manage_reservations", "manage_finances",
        "manage_takeaway_restaurants", "update_takeaway_order_status",
    }),
    "Supervisor": frozenset({
        "manage_menu", "manage_inventory", "manage_reservations",
        "update_takeaway_order_status",
    }),
    "Server": frozenset({"manage_reservations", "update_takeaway_order_status"}),
    "Kitchen": frozenset({"manage_inventory", "update_takeaway_order_status"}),
    "Finance": frozenset({"manage_finances"}),
}
ROLES = tuple(ROLE_PERMISSIONS)

# The permission each section of the restaurant window needs.
SECTION_PERMISSIONS = {
    "menu": "manage_menu",
    "place_order": "update_takeaway_order_status",
    "orders": "update_takeaway_order_status",
    "refunds": "manage_finances",
    "customers": "manage_reservations",
    "tables": "manage_reservations",
    "staff": "manage_takeaway_restaurants",
    "inventory": "manage_inventory",
    "reports": "manage_finances",
}
USERS_SECTION = "users"

# Only these logins can open the restaurant from the main window, so only they
# can be given access. Administrators already have everything.
ELIGIBLE_LOGIN_ROLES = ("staff",)

AUDIT_TABLE = "restaurant_user_access"
ACCESS_DDL = """
    CREATE TABLE IF NOT EXISTS restaurant_user_access (
        access_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL COLLATE NOCASE UNIQUE,
        staff_id INTEGER REFERENCES restaurant_staff (staff_id) ON DELETE SET NULL,
        staff_name TEXT,
        role TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        granted_by TEXT,
        granted_at TEXT,
        removed_by TEXT,
        removed_at TEXT,
        removed_reason TEXT
    )
"""
ACCESS_STAFF_INDEX_DDL = """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_restaurant_user_access_active_staff
    ON restaurant_user_access (staff_id) WHERE active = 1
"""
AUDIT_DDL = """
    CREATE TABLE IF NOT EXISTS restaurant_audit_logs (
        log_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        action TEXT NOT NULL,
        table_name TEXT,
        record_id TEXT,
        old_values TEXT,
        new_values TEXT,
        timestamp TEXT NOT NULL,
        ip_address TEXT,
        user_agent TEXT
    )
"""


class AccessError(Exception):
    """A change that was refused; the message is written for the person using the screen."""


def _connect():
    conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _auth_connect():
    return auth_db.connect()


def _ensure_schema(conn) -> None:
    conn.execute(ACCESS_DDL)
    conn.execute(ACCESS_STAFF_INDEX_DDL)
    conn.execute(AUDIT_DDL)


def _username(auth) -> str | None:
    user = getattr(auth, "current_user", None)
    name = user.get("username") if isinstance(user, dict) else None
    return name if isinstance(name, str) and name else None


def _access_row(username: str):
    """The person's access row with their staff status, or None if they have none."""
    conn = _connect()
    try:
        return conn.execute(
            """SELECT a.role, a.active, s.status AS staff_status, s.is_active AS staff_active,
                      s.staff_id AS linked_staff
               FROM restaurant_user_access a
               LEFT JOIN restaurant_staff s ON s.staff_id = a.staff_id
               WHERE a.username = ?""",
            (username,),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return None
        raise
    finally:
        conn.close()


def _row_is_effective(row) -> bool:
    return bool(
        row["active"]
        and row["linked_staff"] is not None
        and (row["staff_status"] or "Active") == "Active"
        and row["staff_active"] != 0
    )


def can(auth, permission: str, check=None) -> bool:
    """Whether the signed-in person may do *permission* in the restaurant.

    ``check`` replaces ``auth.check_permission`` for callers that use a
    different login check. A database failure refuses non-administrators.
    """
    if auth is None:
        return False
    check = check or auth.check_permission
    allowed_by_login = bool(check(permission))
    username = _username(auth)
    if username is None or check("system_config"):
        return allowed_by_login
    try:
        row = _access_row(username)
    except sqlite3.Error as exc:
        logger.error("Could not read restaurant access for %s: %s", username, exc)
        return False
    if row is None:
        return allowed_by_login
    return _row_is_effective(row) and permission in ROLE_PERMISSIONS.get(row["role"], ())


def _is_admin(auth) -> bool:
    return auth is not None and bool(auth.check_permission("system_config"))


def can_manage(auth) -> bool:
    """Administrators and active restaurant Managers may manage access."""
    if _is_admin(auth):
        return True
    username = _username(auth)
    if username is None:
        return False
    try:
        row = _access_row(username)
    except sqlite3.Error as exc:
        logger.error("Could not read restaurant access for %s: %s", username, exc)
        return False
    return bool(row and _row_is_effective(row) and row["role"] == MANAGER)


def allowed_sections(auth) -> set:
    """The sections of the restaurant window this person may open."""
    allowed = {section for section, permission in SECTION_PERMISSIONS.items()
               if can(auth, permission)}
    if can_manage(auth):
        allowed.add(USERS_SECTION)
    return allowed


def _audit(conn, actor, action, username, old_values, new_values) -> None:
    """Written in the same transaction as the change, so neither can exist alone."""
    now = datetime.now()
    conn.execute(
        "INSERT INTO restaurant_audit_logs (log_id, user_id, action, table_name, record_id,"
        " old_values, new_values, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (f"AUDIT{now:%Y%m%d%H%M%S}{uuid.uuid4().hex[:8]}", actor, action, AUDIT_TABLE, username,
         json.dumps(old_values) if old_values else None,
         json.dumps(new_values) if new_values else None,
         now.strftime("%Y-%m-%d %H:%M:%S")),
    )


def _authorize_change(auth, target: str, *roles_involved) -> str:
    """Refuse changes the signed-in person may not make; return their username."""
    if not can_manage(auth):
        raise AccessError("Only an administrator or restaurant Manager can change access.")
    actor = _username(auth)
    if not actor:
        raise AccessError("You must be signed in to change access.")
    if actor.casefold() == target.casefold():
        raise AccessError("You can't change your own access. Ask another manager or an administrator.")
    if MANAGER in roles_involved and not _is_admin(auth):
        raise AccessError("Only an administrator can give, change or remove the Manager role.")
    return actor


def _existing(conn, username: str):
    return conn.execute(
        "SELECT * FROM restaurant_user_access WHERE username = ?", (username,)).fetchone()


def _eligible_login(username: str):
    conn = _auth_connect()
    try:
        marks = ",".join("?" * len(ELIGIBLE_LOGIN_ROLES))
        # db-audit: ignore[DBW001] - marks is only question marks
        return conn.execute(
            f"""SELECT u.username FROM users u
                JOIN user_systems us ON us.user_id = u.id
                WHERE u.username = ? COLLATE NOCASE AND u.is_active = 1
                  AND us.system_key = 'university' AND us.role IN ({marks})""",
            (username, *ELIGIBLE_LOGIN_ROLES),
        ).fetchone()
    finally:
        conn.close()


def grant_access(auth, username: str, staff_id: int, role: str) -> None:
    """Link a login to a staff member with a role; also restores removed access."""
    username = (username or "").strip()
    if not username:
        raise AccessError("Choose a login.")
    if role not in ROLE_PERMISSIONS:
        raise AccessError("Choose a restaurant role.")
    actor = _authorize_change(auth, username, role)
    login = _eligible_login(username)
    if login is None:
        raise AccessError(f"{username} isn't an active university staff login.")
    username = login[0]

    conn = _connect()
    try:
        _ensure_schema(conn)
        staff = conn.execute(
            "SELECT staff_id, name, status, is_active FROM restaurant_staff WHERE staff_id = ?",
            (staff_id,),
        ).fetchone()
        if staff is None:
            raise AccessError("That staff member no longer exists.")
        if (staff["status"] or "Active") != "Active" or staff["is_active"] == 0:
            raise AccessError(f"{staff['name']} isn't an active staff member.")
        taken = conn.execute(
            "SELECT username FROM restaurant_user_access"
            " WHERE staff_id = ? AND active = 1 AND username <> ?",
            (staff_id, username),
        ).fetchone()
        if taken:
            raise AccessError(f"{staff['name']} is already linked to the login {taken[0]}.")

        existing = _existing(conn, username)
        if existing is not None and existing["active"]:
            raise AccessError(f"{username} already has access. Change their role instead.")
        if existing is not None:
            _authorize_change(auth, username, existing["role"], role)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """INSERT INTO restaurant_user_access
                   (username, staff_id, staff_name, role, active, granted_by, granted_at)
               VALUES (?, ?, ?, ?, 1, ?, ?)
               ON CONFLICT (username) DO UPDATE SET
                   staff_id = excluded.staff_id, staff_name = excluded.staff_name,
                   role = excluded.role, active = 1,
                   granted_by = excluded.granted_by, granted_at = excluded.granted_at,
                   removed_by = NULL, removed_at = NULL, removed_reason = NULL""",
            (username, staff_id, staff["name"], role, actor, now),
        )
        _audit(conn, actor, "GRANT_ACCESS", username,
               {"role": existing["role"], "active": 0} if existing is not None else None,
               {"role": role, "staff_id": staff_id, "staff_name": staff["name"], "active": 1})
        conn.commit()
    finally:
        conn.close()


def change_role(auth, username: str, role: str) -> None:
    if role not in ROLE_PERMISSIONS:
        raise AccessError("Choose a restaurant role.")
    conn = _connect()
    try:
        _ensure_schema(conn)
        existing = _existing(conn, username)
        if existing is None or not existing["active"]:
            raise AccessError(f"{username} doesn't have access.")
        actor = _authorize_change(auth, username, existing["role"], role)
        if existing["role"] == role:
            return
        conn.execute("UPDATE restaurant_user_access SET role = ? WHERE username = ?",
                     (role, username))
        _audit(conn, actor, "CHANGE_ACCESS_ROLE", existing["username"],
               {"role": existing["role"]}, {"role": role})
        conn.commit()
    finally:
        conn.close()


def _mark_removed(conn, existing, actor: str, reason: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE restaurant_user_access SET active = 0, removed_by = ?, removed_at = ?,"
        " removed_reason = ? WHERE username = ?",
        (actor, now, reason, existing["username"]),
    )
    _audit(conn, actor, "REMOVE_ACCESS", existing["username"],
           {"role": existing["role"], "active": 1}, {"active": 0, "reason": reason})


def remove_access(auth, username: str, reason: str = "") -> None:
    """Take away access. The staff record and its history are not touched."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        existing = _existing(conn, username)
        if existing is None or not existing["active"]:
            raise AccessError(f"{username} doesn't have access.")
        actor = _authorize_change(auth, username, existing["role"])
        _mark_removed(conn, existing, actor, (reason or "").strip() or "Access removed")
        conn.commit()
    finally:
        conn.close()


def remove_for_leaver(staff_id, actor: str) -> None:
    """Called when a staff member is terminated, by whoever was allowed to do that."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT * FROM restaurant_user_access WHERE staff_id = ? AND active = 1",
            (staff_id,),
        ).fetchall()
        for existing in rows:
            _mark_removed(conn, existing, actor or "system", "Staff member left")
        conn.commit()
    finally:
        conn.close()


def _login_details(usernames) -> dict:
    """Name and active flag for each login. The list still works if auth.db can't be read."""
    if not usernames:
        return {}
    try:
        conn = _auth_connect()
    except sqlite3.Error as exc:
        logger.warning("Could not read login details: %s", exc)
        return {}
    try:
        details = {}
        for username in usernames:
            row = conn.execute(
                "SELECT display_name, is_active FROM users WHERE username = ? COLLATE NOCASE",
                (username,),
            ).fetchone()
            if row:
                details[username] = {"name": row[0] or "", "login_active": bool(row[1])}
        return details
    except sqlite3.Error as exc:
        logger.warning("Could not read login details: %s", exc)
        return {}
    finally:
        conn.close()


def _state(row) -> str:
    if not row["active"]:
        return "Removed"
    if row["current_staff_id"] is None:
        return "Staff record missing"
    status = row["staff_status"] or "Active"
    if status != "Active":
        return f"Blocked: staff {status.lower()}"
    if row["staff_is_active"] == 0:
        return "Blocked: staff inactive"
    return "Active"


def list_access(auth) -> list:
    """Everyone with restaurant access, including people whose access was removed."""
    if not can_manage(auth):
        raise AccessError("Only an administrator or restaurant Manager can view access.")
    conn = _connect()
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """SELECT a.*, s.staff_id AS current_staff_id, s.status AS staff_status,
                      s.is_active AS staff_is_active, COALESCE(s.name, a.staff_name) AS staff_label
               FROM restaurant_user_access a
               LEFT JOIN restaurant_staff s ON s.staff_id = a.staff_id
               ORDER BY a.active DESC, a.username"""
        ).fetchall()
    finally:
        conn.close()
    logins = _login_details([row["username"] for row in rows])
    result = []
    for row in rows:
        login = logins.get(row["username"], {})
        state = _state(row)
        if state == "Active" and login.get("login_active") is False:
            state = "Blocked: login disabled"
        result.append({
            "username": row["username"],
            "name": login.get("name", ""),
            "staff_id": row["staff_id"],
            "staff_name": row["staff_label"] or "",
            "role": row["role"],
            "active": bool(row["active"]),
            "state": state,
            "granted_by": row["granted_by"] or "",
            "granted_at": row["granted_at"] or "",
            "removed_by": row["removed_by"] or "",
            "removed_at": row["removed_at"] or "",
            "removed_reason": row["removed_reason"] or "",
        })
    return result


def find_logins(auth, query: str = "", limit: int = 50) -> list:
    """Staff logins without current access, matching *query* on username or name."""
    if not can_manage(auth):
        raise AccessError("Only an administrator or restaurant Manager can view access.")
    conn = _connect()
    try:
        _ensure_schema(conn)
        taken = {row[0].casefold() for row in conn.execute(
            "SELECT username FROM restaurant_user_access WHERE active = 1")}
    finally:
        conn.close()
    pattern = f"%{escape_like((query or '').strip())}%"
    marks = ",".join("?" * len(ELIGIBLE_LOGIN_ROLES))
    auth_conn = _auth_connect()
    try:
        # db-audit: ignore[DBW001] - marks is only question marks
        rows = auth_conn.execute(
            f"""SELECT u.username, u.display_name, u.email FROM users u
                JOIN user_systems us ON us.user_id = u.id
                WHERE us.system_key = 'university' AND us.role IN ({marks}) AND u.is_active = 1
                  AND (u.username LIKE ? ESCAPE '\\' OR COALESCE(u.display_name, '') LIKE ? ESCAPE '\\')
                ORDER BY u.username LIMIT ?""",
            (*ELIGIBLE_LOGIN_ROLES, pattern, pattern, limit + len(taken)),
        ).fetchall()
    finally:
        auth_conn.close()
    found = [{"username": row[0], "name": row[1] or "", "email": row[2] or ""}
             for row in rows if row[0].casefold() not in taken]
    return found[:limit]


def staff_available(auth) -> list:
    """Active staff not already linked to a login."""
    if not can_manage(auth):
        raise AccessError("Only an administrator or restaurant Manager can view access.")
    conn = _connect()
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """SELECT s.staff_id, s.name, s.role FROM restaurant_staff s
               WHERE COALESCE(s.status, 'Active') = 'Active' AND COALESCE(s.is_active, 1) <> 0
                 AND s.staff_id NOT IN (SELECT staff_id FROM restaurant_user_access
                                        WHERE active = 1 AND staff_id IS NOT NULL)
               ORDER BY s.name"""
        ).fetchall()
        return [{"staff_id": row[0], "name": row[1], "role": row[2] or ""} for row in rows]
    finally:
        conn.close()


def access_history(auth, username: str | None = None, limit: int = 200) -> list:
    """Who changed whose access and when, newest first, from the restaurant audit log."""
    if not can_manage(auth):
        raise AccessError("Only an administrator or restaurant Manager can view access.")
    conn = _connect()
    try:
        _ensure_schema(conn)
        sql = ("SELECT timestamp, user_id, action, record_id, old_values, new_values"
               " FROM restaurant_audit_logs WHERE table_name = ?")
        params = [AUDIT_TABLE]
        if username:
            sql += " AND record_id = ? COLLATE NOCASE"
            params.append(username)
        rows = conn.execute(sql + " ORDER BY timestamp DESC, rowid DESC LIMIT ?",
                            (*params, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
