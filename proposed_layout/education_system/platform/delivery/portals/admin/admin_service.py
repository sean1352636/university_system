"""Central Admin Portal service.

Provides a superadmin dashboard that queries all 5 education system
databases and the shared auth database to present unified administration
views: system health, user management, audit summaries, and configuration.
"""

import logging
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt

from education_system.platform.kernel.database.paths import SYSTEM_DB_PATHS, AUTH_DB
from education_system.platform.kernel.database.sql_safety import validate_identifier  # nosec B608

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
    "nursery": "Nursery",
    "primary": "Primary School",
    "secondary": "Secondary School",
    "sixth_form": "Sixth Form College",
    "university": "University",
}

_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


def _parse_timestamp(value):
    """Best-effort parse of a stored timestamp string into a datetime, or None."""
    if not value:
        return None
    text = str(value).strip()
    if "." in text:  # drop fractional seconds
        text = text.split(".", 1)[0]
    text = text.replace("Z", "").strip()
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


# Headline metrics tracked for trend sparklines, in display order.
_TREND_METRICS = [
    ("students", "Total Students"),
    ("staff", "Total Staff"),
    ("users", "Registered Users"),
    ("storage_mb", "Storage (MB)"),
]


def _alert(severity, category, system, label, message, action=None):
    """Build a single alert dict for the 'Needs Attention' feed."""
    return {
        "severity": severity,
        "category": category,
        "system": system,
        "label": label,
        "message": message,
        "action": action,
    }


class AdminService:
    """Superadmin dashboard service querying all systems."""

    def __init__(self, db_paths=None, auth_db=None, misconduct_db=None,
                 journey_service=None, metrics_db=None):
        self._db_paths = db_paths or _default_db_paths()
        self._auth_db = Path(auth_db) if auth_db else _auth_db_path()
        self._misconduct_db = Path(misconduct_db) if misconduct_db else None
        self._metrics_db = Path(metrics_db) if metrics_db else None
        # Used for the student side of unified search; lazily built if not given.
        self._journey_service = journey_service
        self._journey_tried = journey_service is not None

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
        # Each system names its learner table differently: primary/nursery use
        # ``pupils``; everything else uses ``students``.
        if system in ("primary", "nursery"):
            table = "pupils"
        else:
            table = "students"
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
    # Cross-system comparison
    # ------------------------------------------------------------------

    def get_comparison(self):
        """Return one comparable row per system for a side-by-side table.

        Combines health, per-system user counts, backup recency, and the count
        of open infrastructure alerts so outliers (a system that hasn't been
        backed up, has no students, or is offline) stand out in a single view.

        Returns a list of dicts (in configured system order) with keys:
            system, label, status, student_count, staff_count, user_count,
            db_size_mb, last_backup_days (int or None = never), open_issues.
        """
        now = datetime.now()
        health = {h["system"]: h for h in self.get_system_health()}
        by_system = self.get_user_summary().get("by_system", {})

        # Count only system-attributable alerts (health/storage/backup carry a
        # system key; sessions/security/misconduct are global and excluded).
        issues_by_system = {}
        try:
            for a in self.get_alerts():
                sys_key = a.get("system")
                if sys_key:
                    issues_by_system[sys_key] = issues_by_system.get(sys_key, 0) + 1
        except Exception as e:
            logger.warning("Error counting per-system issues: %s", e)

        rows = []
        for system in self._db_paths:
            h = health.get(system, {})
            user_count = sum(by_system.get(system, {}).values())
            rows.append({
                "system": system,
                "label": h.get("label", SYSTEM_LABELS.get(system, system)),
                "status": h.get("status", "offline"),
                "student_count": h.get("student_count", 0),
                "staff_count": h.get("staff_count", 0),
                "user_count": user_count,
                "db_size_mb": h.get("db_size_mb", 0.0),
                "last_backup_days": self._latest_backup_age_days(system, now),
                "open_issues": issues_by_system.get(system, 0),
            })
        return rows

    # ------------------------------------------------------------------
    # Trends (point-in-time metric history)
    # ------------------------------------------------------------------

    def _metrics_db_path(self):
        """Resolve the metrics-history DB (sibling of auth.db by default)."""
        if self._metrics_db is not None:
            return self._metrics_db
        return self._auth_db.parent / "metrics.db"

    @staticmethod
    def _ensure_metrics_table(conn):
        conn.execute(
            "CREATE TABLE IF NOT EXISTS metric_history ("
            "captured_date TEXT NOT NULL, metric TEXT NOT NULL, "
            "system TEXT NOT NULL DEFAULT '_all', value REAL NOT NULL, "
            "PRIMARY KEY (captured_date, metric, system))"
        )

    def _current_aggregate_metrics(self):
        """Snapshot the platform-wide totals tracked for trends."""
        health = self.get_system_health()
        return {
            "students": sum(h.get("student_count", 0) for h in health),
            "staff": sum(h.get("staff_count", 0) for h in health),
            "users": self.get_user_summary().get("total_users", 0),
            "storage_mb": round(sum(h.get("db_size_mb", 0.0) for h in health), 2),
        }

    def record_metrics_snapshot(self, as_of=None):
        """Capture today's aggregate metrics into history (one row per metric).

        Idempotent per day: re-running on the same date overwrites that day's
        values rather than appending, so callers (e.g. the dashboard on load)
        can record freely without bloating the table.

        Returns the number of metrics written.
        """
        date = as_of or datetime.now().strftime("%Y-%m-%d")
        metrics = self._current_aggregate_metrics()
        try:
            path = self._metrics_db_path()
            conn = sqlite3.connect(str(path))
        except Exception as e:
            logger.warning("Could not open metrics DB: %s", e)
            return 0
        try:
            self._ensure_metrics_table(conn)
            for metric, value in metrics.items():
                conn.execute(
                    "INSERT OR REPLACE INTO metric_history "
                    "(captured_date, metric, system, value) VALUES (?, ?, '_all', ?)",
                    (date, metric, float(value)),
                )
            conn.commit()
            return len(metrics)
        except Exception as e:
            logger.warning("Error recording metrics snapshot: %s", e)
            return 0
        finally:
            conn.close()

    def get_metric_series(self, metric, system="_all", limit=30):
        """Return the most recent *limit* points for a metric, oldest first.

        Each point is {date, value}. Empty list if no history exists yet.
        """
        path = self._metrics_db_path()
        if not Path(path).exists():
            return []
        conn = _connect(path)
        if not conn:
            return []
        try:
            if not _table_exists(conn, "metric_history"):
                return []
            rows = conn.execute(
                "SELECT captured_date, value FROM metric_history "
                "WHERE metric = ? AND system = ? "
                "ORDER BY captured_date DESC LIMIT ?",
                (metric, system, limit),
            ).fetchall()
            return [
                {"date": r["captured_date"], "value": r["value"]}
                for r in reversed(rows)
            ]
        except Exception as e:
            logger.warning("Error reading metric series: %s", e)
            return []
        finally:
            conn.close()

    def get_trends(self, limit=30):
        """Return trend series for the headline metrics, for sparklines.

        Each entry: {metric, label, points, values, current, change,
        change_pct, count}. ``change`` compares the latest point to the
        first point in the window.
        """
        out = []
        for metric, label in _TREND_METRICS:
            points = self.get_metric_series(metric, "_all", limit)
            values = [p["value"] for p in points]
            current = values[-1] if values else 0
            first = values[0] if values else 0
            change = current - first
            out.append({
                "metric": metric,
                "label": label,
                "points": points,
                "values": values,
                "current": current,
                "change": change,
                "change_pct": round(change / first * 100, 1) if first else 0.0,
                "count": len(values),
            })
        return out

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
    # Unified cross-system search ("where is this person?")
    # ------------------------------------------------------------------

    def search(self, query, limit=50):
        """Find anyone — staff/admin accounts and students — in one pass.

        Answers "which system(s), which role, account status, last login" for
        user accounts, and "which system" for student records, from a single
        query. Results are ranked so exact and prefix matches surface first.

        Returns a dict:
            query: the trimmed query
            users: [{id, username, display_name, email, status
                     ('active'|'inactive'|'locked'), last_login,
                     systems: [{system_key, role}]}]
            students: [{system, id, student_id, name, status, year_group}]
        """
        query = (query or "").strip()
        result = {"query": query, "users": [], "students": []}
        if not query:
            return result

        result["users"] = self._search_users(query, limit)

        journey = self._get_journey()
        if journey:
            try:
                result["students"] = journey.search_student(query)[:limit]
            except Exception as e:
                logger.warning("Student search failed: %s", e)
        return result

    def _get_journey(self):
        """Return a JourneyService for student search (lazy, best-effort)."""
        if self._journey_service is None and not self._journey_tried:
            self._journey_tried = True
            try:
                from education_system.platform.cross_system.journey_service import (
                    JourneyService,
                )
                self._journey_service = JourneyService()
            except Exception:
                self._journey_service = None
        return self._journey_service

    def _search_users(self, query, limit):
        conn = _connect(self._auth_db)
        if not conn:
            return []
        try:
            if not _table_exists(conn, "users"):
                return []
            cols = _get_columns(conn, "users")
            has_locked = "locked_until" in cols
            like = f"%{query}%"
            select = "SELECT id, username, display_name, email, is_active, last_login"
            if has_locked:
                select += ", locked_until"
            rows = conn.execute(
                select + " FROM users "
                "WHERE username LIKE ? OR display_name LIKE ? OR email LIKE ?",
                (like, like, like),
            ).fetchall()

            now_iso = datetime.utcnow().isoformat()
            users = []
            for r in rows:
                rk = r.keys()
                sys_rows = conn.execute(
                    "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                    (r["id"],),
                ).fetchall()
                systems = [
                    {"system_key": s["system_key"], "role": s["role"]} for s in sys_rows
                ]
                locked = bool(
                    has_locked and "locked_until" in rk
                    and r["locked_until"] and r["locked_until"] > now_iso
                )
                status = "locked" if locked else (
                    "active" if r["is_active"] else "inactive")
                users.append({
                    "id": r["id"],
                    "username": r["username"],
                    "display_name": r["display_name"] or "",
                    "email": r["email"] or "",
                    "status": status,
                    "last_login": r["last_login"] or "",
                    "systems": systems,
                })
            users.sort(key=lambda u: self._match_rank(query, u))
            return users[:limit]
        except Exception as e:
            logger.warning("User search failed: %s", e)
            return []
        finally:
            conn.close()

    @staticmethod
    def _match_rank(query, user):
        """Sort key: exact match first, then prefix, then substring; A→Z tiebreak."""
        q = query.lower()
        fields = [
            user["username"].lower(),
            user["display_name"].lower(),
            user["email"].lower(),
        ]
        if any(f == q for f in fields):
            tier = 0
        elif any(f.startswith(q) for f in fields):
            tier = 1
        else:
            tier = 2
        return (tier, user["username"].lower())

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
                [{"system_key": "sixth_form", "role": "staff"}, ...]
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
            system: System key (e.g. "university", "sixth_form").

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

    # ------------------------------------------------------------------
    # Alerts ("Needs Attention")
    # ------------------------------------------------------------------

    def get_alerts(self, backup_max_age_days=7, db_size_warn_mb=500,
                   session_max_age_hours=12, misconduct_sla_days=30):
        """Roll up operational exceptions across all systems into one feed.

        Surfaces things a superadmin should act on now: databases that are
        offline or erroring, systems with overdue or missing backups,
        databases growing past a size threshold, sessions that have been open
        far longer than expected, accounts locked out by failed logins, and
        academic-misconduct cases left unresolved past their SLA.

        Args:
            backup_max_age_days: Flag a system whose newest backup is older
                than this many days (or that has no backup at all).
            db_size_warn_mb: Flag a system whose DB file is at least this big.
                Set falsy to disable the size check.
            session_max_age_hours: Flag sessions still active after this many
                hours since creation.
            misconduct_sla_days: Flag unresolved misconduct cases open longer
                than this many days.

        Returns a list of alert dicts (most severe first), each with keys:
            severity ("critical" | "warning" | "info"), category, system
            (key or None), label, message, action (dashboard section key to
            jump to, or None).
        """
        alerts = []
        now = datetime.now()

        for info in self.get_system_health():
            system = info.get("system", "")
            label = info.get("label", system)

            if not info.get("db_exists"):
                alerts.append(_alert(
                    "critical", "health", system, label,
                    f"{label}: database file is missing — system is offline.",
                    action="health",
                ))
                continue

            if info.get("status") == "error":
                alerts.append(_alert(
                    "critical", "health", system, label,
                    f"{label}: errors while querying the database.",
                    action="health",
                ))

            size_mb = info.get("db_size_mb", 0) or 0
            if db_size_warn_mb and size_mb >= db_size_warn_mb:
                alerts.append(_alert(
                    "warning", "storage", system, label,
                    f"{label}: database is {size_mb} MB (over {db_size_warn_mb} MB).",
                    action="health",
                ))

            age = self._latest_backup_age_days(system, now)
            if age is None:
                alerts.append(_alert(
                    "warning", "backup", system, label,
                    f"{label}: no backup found — data is unprotected.",
                    action="backup",
                ))
            elif age >= backup_max_age_days:
                day_word = "day" if age == 1 else "days"
                alerts.append(_alert(
                    "warning", "backup", system, label,
                    f"{label}: last backup was {age} {day_word} ago.",
                    action="backup",
                ))

        stale = self._count_stale_sessions(session_max_age_hours, now)
        if stale:
            s_word = "session" if stale == 1 else "sessions"
            alerts.append(_alert(
                "warning", "sessions", None, "",
                f"{stale} active {s_word} open longer than {session_max_age_hours}h.",
                action="sessions",
            ))

        locked = self._count_locked_accounts()
        if locked:
            a_word = "account" if locked == 1 else "accounts"
            alerts.append(_alert(
                "warning", "security", None, "",
                f"{locked} {a_word} locked out by failed login attempts.",
                action="users",
            ))

        overdue, critical_open = self._misconduct_attention(misconduct_sla_days)
        if overdue:
            c_word = "case" if overdue == 1 else "cases"
            alerts.append(_alert(
                "warning", "misconduct", None, "",
                f"{overdue} misconduct {c_word} unresolved for over "
                f"{misconduct_sla_days} days.",
                action="misconduct",
            ))
        if critical_open:
            c_word = "case" if critical_open == 1 else "cases"
            alerts.append(_alert(
                "warning", "misconduct", None, "",
                f"{critical_open} critical misconduct {c_word} still open.",
                action="misconduct",
            ))

        severity_rank = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda a: severity_rank.get(a["severity"], 3))
        return alerts

    def _latest_backup_age_days(self, system, now):
        """Return whole days since the newest backup of *system*, or None.

        Backups are the timestamped copies written by ``backup_database`` —
        ``<db_name>.backup_YYYYMMDD_HHMMSS`` beside the live DB file.
        Returns None when the system is unknown or no backup exists.
        """
        db_path = self._db_paths.get(system)
        if not db_path:
            return None
        path = Path(db_path)
        parent = path.parent
        if not parent.exists():
            return None
        prefix = path.name + ".backup_"
        latest = None
        for f in parent.glob(path.name + ".backup_*"):
            stamp = f.name[len(prefix):][:15]  # YYYYMMDD_HHMMSS
            try:
                ts = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
            except ValueError:
                try:
                    ts = datetime.fromtimestamp(f.stat().st_mtime)
                except OSError:
                    continue
            if latest is None or ts > latest:
                latest = ts
        if latest is None:
            return None
        return max(0, (now - latest).days)

    def _count_stale_sessions(self, max_age_hours, now):
        """Count still-active sessions created more than *max_age_hours* ago."""
        conn = _connect(self._auth_db)
        if not conn:
            return 0
        try:
            if not _table_exists(conn, "sessions"):
                return 0
            cols = _get_columns(conn, "sessions")
            if "created_at" not in cols:
                return 0

            expires_col = None
            for c in ("expires_at", "expiry", "expire_time"):
                if c in cols:
                    expires_col = c
                    break

            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            if expires_col:
                validate_identifier(expires_col)
                where = f"WHERE {expires_col} > ?"
                params = (now_str,)
            else:
                where = ""
                params = ()
            rows = conn.execute(
                f"SELECT created_at FROM sessions {where}", params
            ).fetchall()

            cutoff = now - timedelta(hours=max_age_hours)
            count = 0
            for r in rows:
                ts = _parse_timestamp(r[0])
                if ts and ts < cutoff:
                    count += 1
            return count
        except Exception as e:
            logger.warning("Error counting stale sessions: %s", e)
            return 0
        finally:
            conn.close()

    def _count_locked_accounts(self):
        """Count accounts currently locked out by failed login attempts.

        Reads the shared auth ``users`` table, where the auth layer stores an
        ISO ``locked_until`` timestamp (UTC) while a lockout is in force.
        Returns 0 if the column is absent (older schemas) or the DB is down.
        """
        conn = _connect(self._auth_db)
        if not conn:
            return 0
        try:
            if not _table_exists(conn, "users"):
                return 0
            if "locked_until" not in _get_columns(conn, "users"):
                return 0
            now_iso = datetime.utcnow().isoformat()
            row = conn.execute(
                "SELECT COUNT(*) FROM users "
                "WHERE locked_until IS NOT NULL AND locked_until > ?",
                (now_iso,),
            ).fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.warning("Error counting locked accounts: %s", e)
            return 0
        finally:
            conn.close()

    def _misconduct_db_path(self):
        """Resolve the DB that holds academic-misconduct cases.

        Mirrors the misconduct module's own resolution (its ``DEFAULT_DB_PATH``,
        which in practice is the university DB), with the university system DB
        as a fallback and an explicit constructor override for tests.
        """
        if self._misconduct_db is not None:
            return self._misconduct_db
        try:
            from education_system.platform.governance.academic_misconduct._imports import (
                DEFAULT_DB_PATH,
            )
            if DEFAULT_DB_PATH:
                return Path(DEFAULT_DB_PATH)
        except Exception:
            pass
        uni = self._db_paths.get("university")
        return Path(uni) if uni else None

    def _misconduct_attention(self, sla_days):
        """Return (overdue_count, critical_open_count) for misconduct cases.

        ``overdue`` = unresolved cases filed more than *sla_days* ago.
        ``critical_open`` = unresolved cases flagged Critical severity.
        Returns (0, 0) when the table or DB is unavailable.
        """
        conn = _connect(self._misconduct_db_path())
        if not conn:
            return 0, 0
        try:
            if not _table_exists(conn, "academic_misconduct_cases"):
                return 0, 0
            row = conn.execute(
                """SELECT
                       SUM(CASE WHEN status != 'Resolved'
                                AND julianday('now') - julianday(date_filed) > ?
                           THEN 1 ELSE 0 END),
                       SUM(CASE WHEN status != 'Resolved' AND severity = 'Critical'
                           THEN 1 ELSE 0 END)
                   FROM academic_misconduct_cases""",
                (sla_days,),
            ).fetchone()
            if not row:
                return 0, 0
            return (row[0] or 0), (row[1] or 0)
        except Exception as e:
            logger.warning("Error querying misconduct attention: %s", e)
            return 0, 0
        finally:
            conn.close()
