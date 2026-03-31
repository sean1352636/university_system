"""Central Admin Portal service.

Provides a superadmin dashboard that queries all 4 education system
databases and the shared auth database to present unified administration
views: system health, user management, audit summaries, and configuration.
"""

import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import bcrypt

from education_system.shared.database.paths import SYSTEM_DB_PATHS, AUTH_DB
from education_system.shared.database.sql_safety import validate_identifier  # nosec B608

logger = logging.getLogger(__name__)


def _default_db_paths():
    return dict(SYSTEM_DB_PATHS)


def _auth_db_path():
    return AUTH_DB


def _connect(path):
    """Open a read-only connection. Returns None if the DB file is missing."""
    if not path or not Path(path).exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table_name):
    validate_identifier(table_name)
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "college": "Sixth Form College",
    "university": "University",
}


class AdminService:
    """Superadmin dashboard service querying all systems."""

    def __init__(self, db_paths=None, auth_db=None):
        self._db_paths = db_paths or _default_db_paths()
        self._auth_db = Path(auth_db) if auth_db else _auth_db_path()

    # ------------------------------------------------------------------
    # System Health
    # ------------------------------------------------------------------

    def get_system_health(self):
        """Return per-system stats: DB file size, student count, staff count,
        last activity, and online status.

        Returns a list of dicts with keys:
            system, label, db_exists, db_size_mb, student_count, staff_count,
            last_activity, status
        """
        results = []
        for system, db_path in self._db_paths.items():
            info = {
                "system": system,
                "label": SYSTEM_LABELS.get(system, system),
                "db_exists": False,
                "db_size_mb": 0.0,
                "student_count": 0,
                "staff_count": 0,
                "last_activity": "",
                "status": "offline",
            }
            path = Path(db_path)
            if path.exists():
                info["db_exists"] = True
                info["db_size_mb"] = round(path.stat().st_size / (1024 * 1024), 2)
                info["status"] = "online"
                conn = _connect(path)
                if conn:
                    try:
                        info["student_count"] = self._count_students(conn, system)
                        info["staff_count"] = self._count_staff(conn, system)
                        info["last_activity"] = self._get_last_activity(conn)
                    except Exception as e:
                        logger.warning("Error querying system %s health: %s", system, e)
                        info["status"] = "error"
                    finally:
                        conn.close()
            results.append(info)
        return results

    def _count_students(self, conn, system):
        table = "pupils" if system == "primary" else "students"
        if not _table_exists(conn, table):
            return 0
        validate_identifier(table)
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return row[0] if row else 0

    def _count_staff(self, conn, system):
        best = 0
        for table in ("staff", "staff_profiles", "instructors", "teachers"):
            if _table_exists(conn, table):
                validate_identifier(table)
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                count = row[0] if row else 0
                if count > best:
                    best = count
        return best

    def _get_last_activity(self, conn):
        """Try common audit/log tables to find the most recent timestamp."""
        for table in ("audit_log", "activity_log", "attendance"):
            if _table_exists(conn, table):
                cols = _get_columns(conn, table)
                ts_col = None
                for candidate in ("created_at", "timestamp", "date", "recorded_at"):
                    if candidate in cols:
                        ts_col = candidate
                        break
                if ts_col:
                    try:
                        validate_identifier(table)
                        validate_identifier(ts_col)
                        row = conn.execute(
                            f"SELECT {ts_col} FROM {table} ORDER BY rowid DESC LIMIT 1"
                        ).fetchone()
                        if row and row[0]:
                            return str(row[0])[:19]
                    except Exception as e:
                        logger.debug("Could not read %s from %s: %s", ts_col, table, e)
                        continue
        return ""

    # ------------------------------------------------------------------
    # User Summary
    # ------------------------------------------------------------------

    def get_user_summary(self):
        """Return user counts by system and role from the shared auth DB.

        Returns a dict:
            {
                "total_users": int,
                "by_system": {"primary": {"admin": N, "student": N, ...}, ...},
                "by_role": {"admin": N, "student": N, ...},
            }
        """
        result = {"total_users": 0, "by_system": {}, "by_role": {}}
        conn = _connect(self._auth_db)
        if not conn:
            return result
        try:
            row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
            result["total_users"] = row[0] if row else 0

            rows = conn.execute(
                """SELECT us.system_key, us.role, COUNT(*) as cnt
                   FROM user_systems us
                   JOIN users u ON u.id = us.user_id
                   WHERE u.is_active = 1
                   GROUP BY us.system_key, us.role"""
            ).fetchall()
            for r in rows:
                sys_key = r["system_key"]
                role = r["role"]
                cnt = r["cnt"]
                result["by_system"].setdefault(sys_key, {})[role] = cnt
                result["by_role"][role] = result["by_role"].get(role, 0) + cnt
        except Exception as e:
            logger.warning("Error fetching user summary: %s", e)
        finally:
            conn.close()
        return result

    # ------------------------------------------------------------------
    # All Users
    # ------------------------------------------------------------------

    def get_all_users(self, system=None, role=None):
        """Return user list from auth DB with user_systems join.

        Each dict has: id, username, display_name, email, is_active,
        last_login, systems (list of {system_key, role}).
        """
        conn = _connect(self._auth_db)
        if not conn:
            return []
        try:
            # Get all users
            rows = conn.execute(
                "SELECT id, username, display_name, email, is_active, last_login "
                "FROM users ORDER BY username"
            ).fetchall()

            users = []
            for r in rows:
                uid = r["id"]
                # Get system assignments
                sys_rows = conn.execute(
                    "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                    (uid,),
                ).fetchall()
                systems = [{"system_key": s["system_key"], "role": s["role"]} for s in sys_rows]

                # Apply filters
                if system:
                    if not any(s["system_key"] == system for s in systems):
                        continue
                if role:
                    if not any(s["role"] == role for s in systems):
                        continue

                users.append({
                    "id": uid,
                    "username": r["username"],
                    "display_name": r["display_name"] or "",
                    "email": r["email"] or "",
                    "is_active": bool(r["is_active"]),
                    "last_login": r["last_login"] or "",
                    "systems": systems,
                })
            return users
        except Exception as e:
            logger.warning("Error fetching all users: %s", e)
            return []
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # User Management
    # ------------------------------------------------------------------

    def create_user(self, username, display_name, email, password, systems_roles):
        """Create a new user with bcrypt-hashed password and system/role assignments.

        Args:
            username: Unique username string.
            display_name: User's display name.
            email: User's email address.
            password: Plain-text password to hash with bcrypt.
            systems_roles: List of dicts, e.g.
                [{"system_key": "university", "role": "admin"}, ...]

        Returns:
            The new user's id.

        Raises:
            ValueError: If username already exists or DB is unavailable.
        """
        conn = _connect(self._auth_db)
        if not conn:
            raise ValueError("Auth database is unavailable")
        try:
            # Check for duplicate username
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing:
                raise ValueError(f"Username '{username}' already exists")

            hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            cursor = conn.execute(
                """INSERT INTO users (username, display_name, email, password_hash, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                (username, display_name, email, hashed),
            )
            user_id = cursor.lastrowid

            for sr in systems_roles:
                conn.execute(
                    "INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                    (user_id, sr["system_key"], sr["role"]),
                )

            conn.commit()
            return user_id
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Failed to create user: {exc}")
        finally:
            conn.close()

    def update_user(self, user_id, display_name=None, email=None, is_active=None):
        """Update user fields. Only non-None fields are changed."""
        conn = _connect(self._auth_db)
        if not conn:
            raise ValueError("Auth database is unavailable")
        try:
            parts = []
            params = []
            if display_name is not None:
                parts.append("display_name = ?")
                params.append(display_name)
            if email is not None:
                parts.append("email = ?")
                params.append(email)
            if is_active is not None:
                parts.append("is_active = ?")
                params.append(int(is_active))
            if not parts:
                return
            params.append(user_id)
            conn.execute(
                f"UPDATE users SET {', '.join(parts)} WHERE id = ?", params
            )
            conn.commit()
        except Exception as exc:
            raise ValueError(f"Failed to update user: {exc}")
        finally:
            conn.close()

    def deactivate_user(self, user_id):
        """Set is_active = 0 for the given user."""
        conn = _connect(self._auth_db)
        if not conn:
            raise ValueError("Auth database is unavailable")
        try:
            conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
            conn.commit()
        except Exception as exc:
            raise ValueError(f"Failed to deactivate user: {exc}")
        finally:
            conn.close()

    def reset_password(self, user_id, new_password):
        """Hash new_password with bcrypt and update the user's password_hash.

        Also clears legacy_salt if present.
        """
        conn = _connect(self._auth_db)
        if not conn:
            raise ValueError("Auth database is unavailable")
        try:
            hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            cols = _get_columns(conn, "users")
            if "legacy_salt" in cols:
                conn.execute(
                    "UPDATE users SET password_hash = ?, legacy_salt = NULL WHERE id = ?",
                    (hashed, user_id),
                )
            else:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hashed, user_id),
                )
            conn.commit()
        except Exception as exc:
            raise ValueError(f"Failed to reset password: {exc}")
        finally:
            conn.close()

    def update_user_systems(self, user_id, systems_roles):
        """Replace all user_systems entries for user_id with new assignments.

        Args:
            user_id: The user's id.
            systems_roles: List of dicts, e.g.
                [{"system_key": "college", "role": "staff"}, ...]
        """
        conn = _connect(self._auth_db)
        if not conn:
            raise ValueError("Auth database is unavailable")
        try:
            conn.execute("DELETE FROM user_systems WHERE user_id = ?", (user_id,))
            for sr in systems_roles:
                conn.execute(
                    "INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                    (user_id, sr["system_key"], sr["role"]),
                )
            conn.commit()
        except Exception as exc:
            raise ValueError(f"Failed to update user systems: {exc}")
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Database Backup
    # ------------------------------------------------------------------

    def backup_database(self, system):
        """Copy the system's DB file to a timestamped backup in the same directory.

        Args:
            system: System key (e.g. "university", "college").

        Returns:
            The backup file path as a string.

        Raises:
            ValueError: If the system is unknown or its DB file doesn't exist.
        """
        db_path = self._db_paths.get(system)
        if not db_path:
            raise ValueError(f"Unknown system: {system}")
        path = Path(db_path)
        if not path.exists():
            raise ValueError(f"Database file does not exist: {path}")
        backup_path = str(path) + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(str(path), backup_path)
        return backup_path

    # ------------------------------------------------------------------
    # Audit Summary
    # ------------------------------------------------------------------

    def get_audit_summary(self, limit=50, type_filter=None, search_text=None,
                          date_from=None, date_to=None):
        """Return recent cross-system activity: transfers and notifications.

        Args:
            limit: Maximum number of entries to return (default 50).
            type_filter: Optional filter — "notification" or "transfer".
            search_text: Optional text to search in description and details.
            date_from: Optional start date string (inclusive), e.g. "2026-01-01".
            date_to: Optional end date string (inclusive), e.g. "2026-12-31".

        Returns a list of dicts with: type, timestamp, description, details.
        """
        entries = []
        conn = _connect(self._auth_db)
        if not conn:
            return entries
        try:
            # Cross-system notifications
            if type_filter is None or type_filter == "notification":
                if _table_exists(conn, "cross_system_notifications"):
                    rows = conn.execute(
                        """SELECT n.id, n.sender_system, n.recipient_system,
                                  n.title, n.created_at, u.username as sender_name
                           FROM cross_system_notifications n
                           LEFT JOIN users u ON u.id = n.sender_user_id
                           ORDER BY n.created_at DESC LIMIT ?""",
                        (limit,),
                    ).fetchall()
                    for r in rows:
                        entries.append({
                            "type": "notification",
                            "timestamp": r["created_at"] or "",
                            "description": f"Notification: {r['title']}",
                            "details": f"From {r['sender_system']} to {r['recipient_system']} "
                                       f"by {r['sender_name'] or 'unknown'}",
                        })

            # Cross-system transfers (if table exists)
            if type_filter is None or type_filter == "transfer":
                if _table_exists(conn, "cross_system_transfers"):
                    rows = conn.execute(
                        """SELECT * FROM cross_system_transfers
                           ORDER BY rowid DESC LIMIT ?""",
                        (limit,),
                    ).fetchall()
                    for r in rows:
                        rk = r.keys()
                        entries.append({
                            "type": "transfer",
                            "timestamp": r["created_at"] if "created_at" in rk else "",
                            "description": "Student transfer",
                            "details": f"From {r.get('source_system', '?')} to "
                                       f"{r.get('target_system', '?')}",
                        })

            # Apply date range filters
            if date_from:
                entries = [e for e in entries if e.get("timestamp", "") >= date_from]
            if date_to:
                # Include the entire end date by comparing with date_to + end-of-day
                date_to_end = date_to if len(date_to) > 10 else date_to + " 23:59:59"
                entries = [e for e in entries if e.get("timestamp", "") <= date_to_end]

            # Apply text search filter
            if search_text:
                search_lower = search_text.lower()
                entries = [
                    e for e in entries
                    if search_lower in e.get("description", "").lower()
                    or search_lower in e.get("details", "").lower()
                ]

            # Sort by timestamp descending
            entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            return entries[:limit]
        except Exception as e:
            logger.warning("Error fetching audit summary: %s", e)
            return entries
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def get_active_sessions(self):
        """Return a list of active sessions from the shared auth DB.

        Returns list of dicts: session_id, user_id, username, token (truncated),
        created_at, expires_at.
        """
        conn = _connect(self._auth_db)
        if not conn:
            return []
        try:
            if not _table_exists(conn, "sessions"):
                return []
            cols = _get_columns(conn, "sessions")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Build query depending on available columns
            expires_col = None
            for c in ("expires_at", "expiry", "expire_time"):
                if c in cols:
                    expires_col = c
                    break

            user_id_col = "user_id" if "user_id" in cols else "id"
            token_col = "token" if "token" in cols else "session_token" if "session_token" in cols else None

            if not token_col:
                return []

            where = f"WHERE {expires_col} > ?" if expires_col else ""
            params = (now,) if expires_col else ()

            rows = conn.execute(
                f"""SELECT s.*, u.username
                    FROM sessions s
                    LEFT JOIN users u ON u.id = s.{user_id_col}
                    {where}
                    ORDER BY s.rowid DESC LIMIT 200""",
                params,
            ).fetchall()

            sessions = []
            for r in rows:
                rk = r.keys()
                sessions.append({
                    "session_id": r["id"] if "id" in rk else r.get("rowid", ""),
                    "user_id": r[user_id_col],
                    "username": r["username"] if "username" in rk else "",
                    "token_preview": str(r[token_col])[:12] + "..." if r[token_col] else "",
                    "created_at": r["created_at"] if "created_at" in rk else "",
                    "expires_at": r[expires_col] if expires_col and expires_col in rk else "",
                })
            return sessions
        except Exception as e:
            logger.warning("Error fetching active sessions: %s", e)
            return []
        finally:
            conn.close()

    def force_logout_user(self, user_id):
        """Delete all sessions for a specific user (force logout)."""
        conn = _connect(self._auth_db)
        if not conn:
            return
        try:
            if _table_exists(conn, "sessions"):
                uid_col = "user_id" if "user_id" in _get_columns(conn, "sessions") else "id"
                conn.execute(f"DELETE FROM sessions WHERE {uid_col} = ?", (user_id,))
                conn.commit()
        except Exception as e:
            logger.warning("Error forcing logout for user %s: %s", user_id, e)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # System Config
    # ------------------------------------------------------------------

    def get_system_config(self, system):
        """Return basic config info for a system.

        Returns a dict with: system, label, db_path, db_exists, db_size_mb.
        """
        db_path = self._db_paths.get(system)
        path = Path(db_path) if db_path else None
        return {
            "system": system,
            "label": SYSTEM_LABELS.get(system, system),
            "db_path": str(db_path) if db_path else "",
            "db_exists": path.exists() if path else False,
            "db_size_mb": round(path.stat().st_size / (1024 * 1024), 2) if path and path.exists() else 0.0,
        }
