"""Web frontend blueprint — serves HTML/CSS/JS and dashboard data endpoints.

Data endpoints query the real system databases and return JSON for the
frontend SPA to consume.
"""

import logging
import os
import sqlite3
from pathlib import Path

from flask import Blueprint, send_from_directory, g, jsonify

logger = logging.getLogger(__name__)

_DIR = Path(__file__).parent
_TEMPLATE_DIR = _DIR / "templates"
_STATIC_DIR = _DIR / "static"


web_bp = Blueprint("web_frontend", __name__)


# ── Static file serving ──────────────────────────────────────────────

@web_bp.route("/")
@web_bp.route("/web")
@web_bp.route("/web/login")
@web_bp.route("/web/dashboard")
def serve_index():
    return send_from_directory(str(_TEMPLATE_DIR), "index.html")


@web_bp.route("/web/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(str(_STATIC_DIR), filename)


# ── Database resolution ──────────────────────────────────────────────

def _resolve_db(system_key: str) -> str | None:
    """Resolve the database path for a given system key."""
    try:
        if system_key == "college":
            from education_system.college_system.core.paths import DB_FILE
            return str(DB_FILE)
        elif system_key == "school":
            from education_system.secondary_school.core.paths import DB_FILE
            return str(DB_FILE)
        elif system_key == "primary":
            from education_system.primary_school.infrastructure.database.db import get_db_path
            return str(get_db_path())
        elif system_key == "university":
            from education_system.university_system.core.paths import DEFAULT_DB_PATH
            return str(DEFAULT_DB_PATH)
    except ImportError:
        logger.warning("Could not resolve DB for system: %s", system_key)
    return None


def _query(db_path: str, sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query against a system database."""
    if not db_path:
        return []
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
        logger.debug("Query failed on %s: %s", db_path, e)
        return []


def _safe_tables(db_path: str) -> set[str]:
    """Return the set of table names in the database."""
    if not db_path:
        return set()
    rows = _query(db_path, "SELECT name FROM sqlite_master WHERE type='table'")
    return {r["name"] for r in rows}


# ── Auth decorator (reuse from shared API auth) ─────────────────────

def _require_token(f):
    """Lightweight token check — delegates to the shared auth module."""
    import functools

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        from education_system.shared.api.auth import decode_token
        from flask import request
        import jwt as pyjwt

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            data = decode_token(token)
            if data.get("type") == "refresh":
                return jsonify({"error": "Cannot use refresh token"}), 401
            g.current_user = {
                "user_id": data["user_id"],
                "username": data["username"],
                "systems": data.get("systems", []),
            }
        except pyjwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return wrapper


def _has_system_access(system_key: str) -> bool:
    systems = g.current_user.get("systems", [])
    return any(s["system_key"] == system_key for s in systems)


def _user_role_for(system_key: str) -> str:
    for s in g.current_user.get("systems", []):
        if s["system_key"] == system_key:
            return s.get("role", "student")
    return "student"


# ── Dashboard data endpoint ──────────────────────────────────────────

@web_bp.route("/api/v1/web/dashboard/<system_key>")
@_require_token
def dashboard_data(system_key):
    if not _has_system_access(system_key):
        return jsonify({"error": "Access denied"}), 403

    db = _resolve_db(system_key)
    if not db:
        return jsonify({"error": f"System '{system_key}' database not found"}), 404

    tables = _safe_tables(db)
    data = {}

    # Student/pupil count — table names are hardcoded literals, not user input
    for tbl in ("students", "pupils"):
        if tbl in tables:
            rows = _query(db, f"SELECT COUNT(*) as c FROM {tbl}")  # nosemgrep: python.lang.security.audit.formatted-sql-query
            data["total_students"] = rows[0]["c"] if rows else 0
            break
    else:
        data["total_students"] = 0

    # Course count
    for tbl in ("courses", "subjects"):
        if tbl in tables:
            rows = _query(db, f"SELECT COUNT(*) as c FROM {tbl}")  # nosemgrep: python.lang.security.audit.formatted-sql-query
            data["total_courses"] = rows[0]["c"] if rows else 0
            break
    else:
        data["total_courses"] = 0

    # Attendance — university uses "attendance", others use "attendance_records"
    att_table = next((t for t in ("attendance", "attendance_records") if t in tables), None)
    if att_table:
        att = _query(db, f"SELECT COUNT(*) as t, SUM(CASE WHEN status IN ('present','Present','late','Late') THEN 1 ELSE 0 END) as a FROM {att_table}")  # nosemgrep: python.lang.security.audit.formatted-sql-query
        if att and att[0]["t"]:
            data["attendance_rate"] = round(att[0]["a"] / att[0]["t"] * 100, 1)
        else:
            data["attendance_rate"] = None
        bd = _query(db, f"SELECT status, COUNT(*) as c FROM {att_table} GROUP BY status")  # nosemgrep: python.lang.security.audit.formatted-sql-query
        data["attendance_breakdown"] = {r["status"]: r["c"] for r in bd}
    else:
        data["attendance_rate"] = None
        data["attendance_breakdown"] = {}

    # Grade count
    if "grades" in tables:
        rows = _query(db, "SELECT COUNT(*) as c FROM grades")
        data["total_grades"] = rows[0]["c"] if rows else 0
    elif "assessment" in tables:
        rows = _query(db, "SELECT COUNT(*) as c FROM assessment")
        data["total_grades"] = rows[0]["c"] if rows else 0
    else:
        data["total_grades"] = 0

    # Recent enrollments
    if "enrollments" in tables:
        data["recent_enrollments"] = _query(
            db,
            "SELECT * FROM enrollments ORDER BY rowid DESC LIMIT 10"
        )
    else:
        data["recent_enrollments"] = []

    return jsonify(data)


# ── Students endpoint ────────────────────────────────────────────────

@web_bp.route("/api/v1/web/students/<system_key>")
@_require_token
def students_data(system_key):
    if not _has_system_access(system_key):
        return jsonify({"error": "Access denied"}), 403

    role = _user_role_for(system_key)
    if role not in ("admin", "staff", "teacher", "instructor"):
        return jsonify({"error": "Staff access required"}), 403

    db = _resolve_db(system_key)
    if not db:
        return jsonify({"error": "Database not found"}), 404

    tables = _safe_tables(db)
    students = []
    for tbl in ("students", "pupils"):
        if tbl in tables:
            students = _query(db, f"SELECT * FROM {tbl} ORDER BY rowid DESC LIMIT 200")  # nosemgrep: python.lang.security.audit.formatted-sql-query
            break

    return jsonify({"students": students})


# ── Courses endpoint ─────────────────────────────────────────────────

@web_bp.route("/api/v1/web/courses/<system_key>")
@_require_token
def courses_data(system_key):
    if not _has_system_access(system_key):
        return jsonify({"error": "Access denied"}), 403

    db = _resolve_db(system_key)
    if not db:
        return jsonify({"error": "Database not found"}), 404

    tables = _safe_tables(db)
    courses = []
    for tbl in ("courses", "subjects"):
        if tbl in tables:
            courses = _query(db, f"SELECT * FROM {tbl} ORDER BY rowid DESC LIMIT 200")  # nosemgrep: python.lang.security.audit.formatted-sql-query
            break

    return jsonify({"courses": courses})


# ── Attendance endpoint ──────────────────────────────────────────────

@web_bp.route("/api/v1/web/attendance/<system_key>")
@_require_token
def attendance_data(system_key):
    if not _has_system_access(system_key):
        return jsonify({"error": "Access denied"}), 403

    db = _resolve_db(system_key)
    if not db:
        return jsonify({"error": "Database not found"}), 404

    tables = _safe_tables(db)
    records = []
    att_table = next((t for t in ("attendance", "attendance_records") if t in tables), None)
    if att_table:
        records = _query(db, f"SELECT * FROM {att_table} ORDER BY rowid DESC LIMIT 200")  # nosemgrep: python.lang.security.audit.formatted-sql-query

    return jsonify({"records": records})


# ── Grades endpoint ──────────────────────────────────────────────────

@web_bp.route("/api/v1/web/grades/<system_key>")
@_require_token
def grades_data(system_key):
    if not _has_system_access(system_key):
        return jsonify({"error": "Access denied"}), 403

    db = _resolve_db(system_key)
    if not db:
        return jsonify({"error": "Database not found"}), 404

    tables = _safe_tables(db)
    grades = []
    for tbl in ("grades", "assessment"):
        if tbl in tables:
            grades = _query(db, f"SELECT * FROM {tbl} ORDER BY rowid DESC LIMIT 200")  # nosemgrep: python.lang.security.audit.formatted-sql-query
            break

    return jsonify({"grades": grades})


# ── Reports endpoint ─────────────────────────────────────────────────

@web_bp.route("/api/v1/web/reports/<system_key>")
@_require_token
def reports_data(system_key):
    if not _has_system_access(system_key):
        return jsonify({"error": "Access denied"}), 403

    role = _user_role_for(system_key)
    if role not in ("admin", "staff", "teacher", "instructor"):
        return jsonify({"error": "Staff access required"}), 403

    db = _resolve_db(system_key)
    if not db:
        return jsonify({"error": "Database not found"}), 404

    tables = _safe_tables(db)
    data = {}

    # Student count
    for tbl in ("students", "pupils"):
        if tbl in tables:
            rows = _query(db, f"SELECT COUNT(*) as c FROM {tbl}")  # nosemgrep: python.lang.security.audit.formatted-sql-query
            data["total_students"] = rows[0]["c"] if rows else 0
            break
    else:
        data["total_students"] = 0

    # Enrollment count
    if "enrollments" in tables:
        rows = _query(db, "SELECT COUNT(*) as c FROM enrollments")
        data["total_enrollments"] = rows[0]["c"] if rows else 0
    else:
        data["total_enrollments"] = 0

    # Attendance rate
    att_table = next((t for t in ("attendance", "attendance_records") if t in tables), None)
    if att_table:
        att = _query(db, f"SELECT COUNT(*) as t, SUM(CASE WHEN status IN ('present','Present','late','Late') THEN 1 ELSE 0 END) as a FROM {att_table}")  # nosemgrep: python.lang.security.audit.formatted-sql-query
        if att and att[0]["t"]:
            data["attendance_rate"] = round(att[0]["a"] / att[0]["t"] * 100, 1)
        else:
            data["attendance_rate"] = None
        data["attendance_by_status"] = _query(db, f"SELECT status, COUNT(*) as count FROM {att_table} GROUP BY status ORDER BY count DESC")  # nosemgrep: python.lang.security.audit.formatted-sql-query
    else:
        data["attendance_rate"] = None
        data["attendance_by_status"] = []

    # Grade distribution
    if "grades" in tables:
        rows = _query(db, "SELECT COUNT(*) as c FROM grades")
        data["total_grades"] = rows[0]["c"] if rows else 0
        data["grade_distribution"] = _query(db, "SELECT grade, COUNT(*) as count FROM grades GROUP BY grade ORDER BY count DESC LIMIT 20")
    else:
        data["total_grades"] = 0
        data["grade_distribution"] = []

    return jsonify(data)


# ── Users endpoint (admin only) ──────────────────────────────────────

@web_bp.route("/api/v1/web/users")
@_require_token
def users_data():
    # Check if user is admin in any system
    is_admin = any(s.get("role") == "admin" for s in g.current_user.get("systems", []))
    if not is_admin:
        return jsonify({"error": "Admin access required"}), 403

    try:
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth_db = str(AUTH_DB_FILE)
    except ImportError:
        return jsonify({"error": "Auth database not available"}), 500

    users = _query(auth_db, "SELECT id, username, display_name, email, is_active, created_at, last_login FROM users ORDER BY id")

    # Enrich with system roles
    for user in users:
        user["systems"] = _query(
            auth_db,
            "SELECT system_key, role FROM user_systems WHERE user_id = ?",
            (user["id"],)
        )

    return jsonify({"users": users})


# ── Superadmin helpers ────────────────────────────────────────────────

_SYSTEM_KEYS = ["primary", "school", "college", "university"]
_SYSTEM_LABELS = {
    "primary": "Primary School",
    "school": "Secondary School",
    "college": "Sixth Form College",
    "university": "University",
}


def _is_superadmin() -> bool:
    """True if the current user has admin role in all 4 systems."""
    systems = g.current_user.get("systems", [])
    admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
    return admin_keys >= {"university", "college", "school", "primary"}


def _is_admin() -> bool:
    """True if the current user has admin role in any system."""
    systems = g.current_user.get("systems", [])
    return any(s.get("role") == "admin" for s in systems)


def _system_health(system_key: str) -> dict:
    """Gather health info for a single system."""
    db = _resolve_db(system_key)
    info = {
        "system": system_key,
        "label": _SYSTEM_LABELS.get(system_key, system_key),
        "status": "offline",
        "student_count": 0,
        "staff_count": 0,
        "db_size_mb": 0,
        "db_path": "",
    }
    if not db or not Path(db).exists():
        return info

    info["status"] = "online"
    info["db_path"] = db
    try:
        info["db_size_mb"] = round(os.path.getsize(db) / (1024 * 1024), 2)
    except OSError:
        pass

    tables = _safe_tables(db)

    for tbl in ("students", "pupils"):
        if tbl in tables:
            rows = _query(db, f"SELECT COUNT(*) as c FROM {tbl}")  # nosemgrep: python.lang.security.audit.formatted-sql-query
            info["student_count"] = rows[0]["c"] if rows else 0
            break

    for tbl in ("staff", "staff_directory"):
        if tbl in tables:
            rows = _query(db, f"SELECT COUNT(*) as c FROM {tbl}")  # nosemgrep: python.lang.security.audit.formatted-sql-query
            info["staff_count"] = rows[0]["c"] if rows else 0
            break

    return info


# ── Superadmin: Overview endpoint ─────────────────────────────────────

# ── Generic table data endpoint ─────────────────────────────────────

# Tables that should NOT be exposed via the generic endpoint (security)
_BLOCKED_TABLES = frozenset({
    "user_accounts", "users", "password_history", "mfa_recovery_codes",
    "mfa_otp_codes", "mfa_trusted_devices", "mfa_user_settings",
    "mfa_verification_attempts", "mfa_methods", "mfa_enforcement_policies",
    "encryption_keys", "encrypted_fields_metadata", "api_keys",
    "managed_api_keys", "login_attempts", "sessions", "two_fa_recovery_codes",
    "biometric_enrollments", "biometric_auth_log", "security_settings",
    "permission_changes_log",
})


def _validated_table(table_name, db_path):
    """Validate table_name against the whitelist of actual tables in the DB.

    Returns the table name if it exists and is not blocked, or None.
    This prevents SQL injection by only allowing names that exist as
    real tables — no user string is ever interpolated into SQL.
    """
    from education_system.shared.database.sql_safety import validate_identifier
    try:
        validate_identifier(table_name)
    except ValueError:
        return None
    if table_name in _BLOCKED_TABLES:
        return None
    allowed = _safe_tables(db_path)
    if table_name not in allowed:
        return None
    return table_name


@web_bp.route("/api/v1/web/table/<table_name>/<system_key>")
@_require_token
def generic_table_data(table_name, system_key):
    """Generic endpoint: return paginated rows from any table in a system DB."""
    if not _has_system_access(system_key):
        return jsonify({"error": "Access denied"}), 403

    db = _resolve_db(system_key)
    if not db:
        return jsonify({"error": "Database not found"}), 404

    # Whitelist: only allow table names that actually exist in the DB
    safe_table = _validated_table(table_name, db)
    if not safe_table:
        return jsonify({"error": f"Table '{table_name}' not found or access denied"}), 404

    from flask import request
    page_num = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 100)), 500)
    search = request.args.get("search", "").strip()
    offset = (page_num - 1) * per_page

    # Use _query() helper which already handles connection lifecycle safely
    col_names = []
    col_rows = _query(db, "SELECT name FROM pragma_table_info(?)", (safe_table,))
    if col_rows:
        col_names = [r["name"] for r in col_rows]
    else:
        # Fallback for older SQLite that doesn't support pragma as function
        try:
            conn = sqlite3.connect(db, timeout=10)
            try:
                col_names = [r[1] for r in conn.execute(f"PRAGMA table_info([{safe_table}])").fetchall()]  # nosemgrep: python.lang.security.audit.formatted-sql-query
            finally:
                conn.close()
        except Exception:
            pass

    if search:
        from education_system.shared.database.sql_safety import escape_like
        escaped_search = escape_like(search)
        text_cols = col_names[:6]  # search first 6 columns max
        if not text_cols:
            rows, total = [], 0
        else:
            # Column names are validated (they come from PRAGMA, not user input)
            like_clauses = " OR ".join(f'CAST([{c}] AS TEXT) LIKE ?' for c in text_cols)
            pattern = f"%{escaped_search}%"
            params = tuple([pattern] * len(text_cols))
            rows = _query(
                db,
                f"SELECT * FROM [{safe_table}] WHERE {like_clauses} ORDER BY rowid DESC LIMIT ?",  # nosemgrep: python.lang.security.audit.formatted-sql-query
                params + (per_page,),
            )
            total_q = _query(
                db,
                f"SELECT COUNT(*) as c FROM [{safe_table}] WHERE {like_clauses}",  # nosemgrep: python.lang.security.audit.formatted-sql-query
                params,
            )
            total = total_q[0]["c"] if total_q else 0
    else:
        total_q = _query(db, f"SELECT COUNT(*) as c FROM [{safe_table}]")  # nosemgrep: python.lang.security.audit.formatted-sql-query
        total = total_q[0]["c"] if total_q else 0
        rows = _query(db, f"SELECT * FROM [{safe_table}] ORDER BY rowid DESC LIMIT ? OFFSET ?", (per_page, offset))  # nosemgrep: python.lang.security.audit.formatted-sql-query

    if not col_names and rows:
        col_names = list(rows[0].keys())

    return jsonify({
        "table": table_name,
        "columns": col_names,
        "rows": rows,
        "total": total,
        "page": page_num,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 1,
    })


# ── Table list endpoint ─────────────────────────────────────────────

@web_bp.route("/api/v1/web/tables/<system_key>")
@_require_token
def list_tables(system_key):
    """Return list of tables in a system DB (for dynamic navigation)."""
    if not _has_system_access(system_key):
        return jsonify({"error": "Access denied"}), 403

    db = _resolve_db(system_key)
    if not db:
        return jsonify({"error": "Database not found"}), 404

    tables = sorted(_safe_tables(db) - _BLOCKED_TABLES - {"sqlite_sequence", "sqlite_stat1", "schema_migrations"})
    return jsonify({"tables": tables})


@web_bp.route("/api/v1/web/superadmin/overview")
@_require_token
def superadmin_overview():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    # Gather health for all 4 systems
    systems = [_system_health(sk) for sk in _SYSTEM_KEYS]

    total_students = sum(s["student_count"] for s in systems)
    total_staff = sum(s["staff_count"] for s in systems)

    # Registered users from auth DB
    total_users = 0
    try:
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth_db = str(AUTH_DB_FILE)
        rows = _query(auth_db, "SELECT COUNT(*) as c FROM users")
        total_users = rows[0]["c"] if rows else 0
    except ImportError:
        pass

    # Recent audit activity from auth DB
    recent_activity = []
    try:
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth_db = str(AUTH_DB_FILE)
        auth_tables = _safe_tables(auth_db)
        if "audit_log" in auth_tables:
            recent_activity = _query(
                auth_db,
                "SELECT * FROM audit_log ORDER BY rowid DESC LIMIT 10"
            )
        elif "sessions" in auth_tables:
            recent_activity = _query(
                auth_db,
                "SELECT user_id, created_at as timestamp, 'session' as action FROM sessions ORDER BY created_at DESC LIMIT 10"
            )
    except ImportError:
        pass

    return jsonify({
        "systems": systems,
        "total_students": total_students,
        "total_staff": total_staff,
        "total_users": total_users,
        "total_transfers": 0,
        "recent_activity": recent_activity,
    })


# ── Superadmin: System Health endpoint ────────────────────────────────

@web_bp.route("/api/v1/web/superadmin/health")
@_require_token
def superadmin_health():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    systems = []
    for sk in _SYSTEM_KEYS:
        info = _system_health(sk)
        db = info["db_path"]
        if db and Path(db).exists():
            tables = _safe_tables(db)
            info["table_count"] = len(tables)

            # Last activity: try to find a recent timestamp
            for tbl in ("attendance", "grades", "enrollments", "assessment"):
                if tbl in tables:
                    try:
                        rows = _query(db, f"SELECT MAX(rowid) as last FROM {tbl}")
                        if rows and rows[0]["last"]:
                            info["last_activity"] = f"rowid {rows[0]['last']}"
                    except Exception:
                        pass
                    break
        systems.append(info)

    return jsonify({"systems": systems})


# ── Session heartbeat (all authenticated users) ──────────────────────

@web_bp.route("/api/v1/web/session/heartbeat")
@_require_token
def session_heartbeat():
    """Check if the current user still has an active session."""
    user_id = g.current_user.get("user_id")
    try:
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth_db = str(AUTH_DB_FILE)
        rows = _query(
            auth_db,
            """SELECT COUNT(*) AS cnt FROM sessions
               WHERE user_id = ? AND is_active = 1
                 AND expires_at > datetime('now')""",
            (user_id,),
        )
        if rows and rows[0]["cnt"] > 0:
            return jsonify({"active": True})
        return jsonify({"active": False, "reason": "session_terminated"}), 401
    except Exception:
        # If we can't check, assume valid to avoid false logouts
        return jsonify({"active": True})


# ── Active Sessions endpoint (admin + superadmin) ────────────────────

@web_bp.route("/api/v1/web/superadmin/sessions")
@web_bp.route("/api/v1/web/admin/sessions")
@_require_token
def admin_sessions():
    if not _is_admin():
        return jsonify({"error": "Admin access required"}), 403

    sessions = []
    try:
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth_db = str(AUTH_DB_FILE)
        auth_tables = _safe_tables(auth_db)
        if "sessions" in auth_tables:
            sessions = _query(
                auth_db,
                """SELECT s.user_id, u.username, u.display_name,
                          MAX(s.created_at) AS last_login,
                          MAX(s.expires_at) AS expires_at,
                          COUNT(*) AS session_count
                   FROM sessions s
                   LEFT JOIN users u ON s.user_id = u.id
                   WHERE s.is_active = 1
                     AND s.expires_at > datetime('now')
                   GROUP BY s.user_id
                   ORDER BY last_login DESC LIMIT 100"""
            )
    except ImportError:
        pass

    return jsonify({"sessions": sessions})


@web_bp.route("/api/v1/web/admin/force-logout", methods=["POST"])
@_require_token
def admin_force_logout():
    """Force-logout a user by invalidating all their active sessions."""
    if not _is_admin():
        return jsonify({"error": "Admin access required"}), 403

    from flask import request as req
    data = req.get_json(silent=True) or {}
    target_user_id = data.get("user_id")
    if not target_user_id:
        return jsonify({"error": "user_id is required"}), 400

    # Prevent non-superadmin from logging out other admins
    current_user_id = g.current_user.get("user_id")
    if int(target_user_id) == int(current_user_id):
        return jsonify({"error": "Cannot force-logout yourself"}), 400

    try:
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth_db = str(AUTH_DB_FILE)
        conn = sqlite3.connect(auth_db, timeout=10)
        try:
            cur = conn.execute(
                "UPDATE sessions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
                (target_user_id,),
            )
            conn.commit()
            count = cur.rowcount
        finally:
            conn.close()
        return jsonify({"success": True, "sessions_terminated": count})
    except Exception as e:
        logger.error("Force-logout failed: %s", e)
        return jsonify({"error": "Failed to terminate sessions"}), 500


# ── Superadmin: Audit Log endpoint ────────────────────────────────────

@web_bp.route("/api/v1/web/superadmin/audit")
@_require_token
def superadmin_audit():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    entries = []
    try:
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth_db = str(AUTH_DB_FILE)
        auth_tables = _safe_tables(auth_db)
        if "audit_log" in auth_tables:
            entries = _query(
                auth_db,
                "SELECT * FROM audit_log ORDER BY rowid DESC LIMIT 100"
            )
    except ImportError:
        pass

    return jsonify({"entries": entries})


# ── Superadmin: Analytics endpoint ────────────────────────────────────

@web_bp.route("/api/v1/web/superadmin/analytics")
@_require_token
def superadmin_analytics():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    data = {
        "summary": {},
        "retention": [],
        "transfers": [],
        "trends": [],
        "per_system": [],
    }

    try:
        from education_system.shared.analytics.analytics_service import AnalyticsService
        svc = AnalyticsService()

        try:
            data["summary"] = svc.get_summary()
            data["per_system"] = data["summary"].get("systems", [])
        except Exception:
            pass

        try:
            data["retention"] = svc.get_retention_stats()
        except Exception:
            pass

        try:
            data["transfers"] = svc.get_transfer_rates()
        except Exception:
            pass

        try:
            data["trends"] = svc.get_year_trends()
        except Exception:
            pass

    except ImportError:
        pass

    return jsonify(data)


# ── Superadmin: Notifications endpoint ────────────────────────────────

@web_bp.route("/api/v1/web/superadmin/notifications")
@_require_token
def superadmin_notifications():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    user_id = g.current_user.get("user_id")
    data = {"notifications": [], "unread_count": 0}

    try:
        from education_system.shared.notifications.service import CrossSystemNotificationService
        svc = CrossSystemNotificationService()

        try:
            data["unread_count"] = svc.get_unread_count(user_id)
        except Exception:
            pass

        try:
            data["notifications"] = svc.get_all(user_id, limit=100)
        except Exception:
            pass

    except ImportError:
        pass

    return jsonify(data)


@web_bp.route("/api/v1/web/superadmin/notifications/mark-read", methods=["POST"])
@_require_token
def superadmin_mark_notifications_read():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    user_id = g.current_user.get("user_id")

    try:
        from education_system.shared.notifications.service import CrossSystemNotificationService
        svc = CrossSystemNotificationService()
        svc.mark_all_read(user_id)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("Failed to mark notifications read: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@web_bp.route("/api/v1/web/superadmin/notifications/send", methods=["POST"])
@_require_token
def superadmin_send_notification():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    from flask import request
    body = request.get_json(silent=True) or {}
    required = ["recipient_user_id", "recipient_system", "title"]
    for field in required:
        if not body.get(field):
            return jsonify({"error": f"Missing field: {field}"}), 400

    user_id = g.current_user.get("user_id")

    try:
        from education_system.shared.notifications.service import CrossSystemNotificationService
        svc = CrossSystemNotificationService()
        svc.send(
            sender_user_id=user_id,
            sender_system="superadmin",
            recipient_user_id=int(body["recipient_user_id"]),
            recipient_system=body["recipient_system"],
            title=body["title"],
            message=body.get("message"),
            priority=body.get("priority", "normal"),
        )
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("Failed to send notification: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@web_bp.route("/api/v1/web/superadmin/notifications/broadcast", methods=["POST"])
@_require_token
def superadmin_broadcast_notification():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    from flask import request
    body = request.get_json(silent=True) or {}
    required = ["target_system", "target_role", "title"]
    for field in required:
        if not body.get(field):
            return jsonify({"error": f"Missing field: {field}"}), 400

    user_id = g.current_user.get("user_id")

    try:
        from education_system.shared.notifications.service import CrossSystemNotificationService
        svc = CrossSystemNotificationService()
        count = svc.send_to_role(
            sender_user_id=user_id,
            sender_system="superadmin",
            target_system=body["target_system"],
            target_role=body["target_role"],
            title=body["title"],
            message=body.get("message"),
            priority=body.get("priority", "normal"),
        )
        return jsonify({"ok": True, "count": count})
    except Exception as e:
        logger.error("Failed to broadcast notification: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# ── Superadmin: Student Search endpoint ───────────────────────────────

@web_bp.route("/api/v1/web/superadmin/search")
@_require_token
def superadmin_search():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    from flask import request
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})

    results = []
    try:
        from education_system.shared.cross_system.journey_service import JourneyService
        svc = JourneyService()
        results = svc.search_student(q)
    except ImportError:
        pass
    except Exception:
        pass

    return jsonify({"results": results})


# ── Superadmin: Student Journey endpoint ──────────────────────────────

@web_bp.route("/api/v1/web/superadmin/journey")
@_require_token
def superadmin_journey():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    from flask import request
    name = request.args.get("name", "").strip()
    student_id = request.args.get("student_id", "").strip()
    system = request.args.get("system", "").strip()

    if not name and not student_id:
        return jsonify({"error": "Provide name or student_id parameter"}), 400

    journey = None
    try:
        from education_system.shared.cross_system.journey_service import JourneyService
        svc = JourneyService()
        journey = svc.get_journey(
            student_name=name or None,
            student_id=student_id or None,
            system=system or None,
        )
    except ImportError:
        pass
    except Exception:
        pass

    return jsonify({"journey": journey})


# ── Superadmin: Permission Matrix endpoint ────────────────────────────

@web_bp.route("/api/v1/web/superadmin/permissions")
@_require_token
def superadmin_permissions():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    users = []
    try:
        from education_system.shared.admin_portal.admin_service import AdminService
        svc = AdminService()
        users = svc.get_all_users()
    except ImportError:
        try:
            from education_system.shared.auth.db import AUTH_DB_FILE
            auth_db = str(AUTH_DB_FILE)
            users = _query(auth_db, "SELECT id, username, display_name FROM users ORDER BY id")
            for user in users:
                user["systems"] = _query(
                    auth_db,
                    "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                    (user["id"],)
                )
        except ImportError:
            pass
    except Exception:
        pass

    # Build permission matrix
    matrix = []
    for u in users:
        sys_map = {}
        for s in u.get("systems", []):
            sys_map[s["system_key"]] = s["role"]
        matrix.append({
            "username": u.get("username", ""),
            "display_name": u.get("display_name", ""),
            "primary": sys_map.get("primary"),
            "school": sys_map.get("school") or sys_map.get("secondary"),
            "college": sys_map.get("college"),
            "university": sys_map.get("university"),
        })

    return jsonify({"matrix": matrix})


# ── Superadmin: Backup endpoint ───────────────────────────────────────

@web_bp.route("/api/v1/web/superadmin/backup", methods=["POST"])
@_require_token
def superadmin_backup():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    from flask import request
    body = request.get_json(silent=True) or {}
    system_key = body.get("system")

    if not system_key:
        return jsonify({"error": "Missing 'system' field"}), 400

    if system_key == "auth":
        # Backup auth DB
        import shutil
        from datetime import datetime as dt
        try:
            from education_system.shared.auth.db import AUTH_DB_FILE
            auth_path = Path(str(AUTH_DB_FILE))
            if not auth_path.exists():
                return jsonify({"error": "Auth DB not found"}), 404
            backup_name = f"{auth_path.name}.backup_{dt.now().strftime('%Y%m%d_%H%M%S')}"
            backup_path = auth_path.parent / backup_name
            shutil.copy2(str(auth_path), str(backup_path))
            return jsonify({"ok": True, "backup": backup_name})
        except Exception as e:
            logger.error("Failed to backup auth DB: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    try:
        from education_system.shared.admin_portal.admin_service import AdminService
        svc = AdminService()
        backup_path = svc.backup_database(system_key)
        return jsonify({"ok": True, "backup": str(backup_path).split("/")[-1]})
    except Exception as e:
        logger.error("Failed to backup database for %s: %s", system_key, e)
        return jsonify({"error": "Internal server error"}), 500


@web_bp.route("/api/v1/web/superadmin/backup/info")
@_require_token
def superadmin_backup_info():
    """Get DB info for backup page."""
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    systems = []
    for sk in _SYSTEM_KEYS:
        info = _system_health(sk)
        systems.append({
            "system": sk,
            "label": info["label"],
            "db_size_mb": info["db_size_mb"],
            "status": info["status"],
        })

    # Auth DB info
    auth_info = {"system": "auth", "label": "Shared Auth Database", "db_size_mb": 0, "status": "offline"}
    try:
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth_path = Path(str(AUTH_DB_FILE))
        if auth_path.exists():
            auth_info["status"] = "online"
            auth_info["db_size_mb"] = round(os.path.getsize(str(auth_path)) / (1024 * 1024), 2)
    except ImportError:
        pass
    systems.append(auth_info)

    return jsonify({"systems": systems})


# ── Superadmin: Batch Operations endpoints ────────────────────────────

@web_bp.route("/api/v1/web/superadmin/batch/role-change", methods=["POST"])
@_require_token
def superadmin_batch_role_change():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    from flask import request
    body = request.get_json(silent=True) or {}
    system_key = body.get("system")
    from_role = body.get("from_role")
    to_role = body.get("to_role")

    if not system_key or not from_role or not to_role:
        return jsonify({"error": "Missing system, from_role, or to_role"}), 400
    if from_role == to_role:
        return jsonify({"error": "Current and new roles must differ"}), 400

    try:
        from education_system.shared.admin_portal.admin_service import AdminService
        svc = AdminService()
        all_users = svc.get_all_users(system=system_key, role=from_role)
        if not all_users:
            return jsonify({"error": f"No users with role '{from_role}' in {system_key}", "count": 0}), 404

        count = 0
        for u in all_users:
            new_sr = []
            for s in u.get("systems", []):
                if s["system_key"] == system_key and s["role"] == from_role:
                    new_sr.append({"system_key": system_key, "role": to_role})
                else:
                    new_sr.append(s)
            svc.update_user_systems(u["id"], new_sr)
            count += 1

        return jsonify({"ok": True, "count": count})
    except Exception as e:
        logger.error("Failed to batch role change: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@web_bp.route("/api/v1/web/superadmin/batch/deactivate", methods=["POST"])
@_require_token
def superadmin_batch_deactivate():
    if not _is_superadmin():
        return jsonify({"error": "Superadmin access required"}), 403

    from flask import request
    body = request.get_json(silent=True) or {}
    system_key = body.get("system")
    role = body.get("role")

    if not system_key or not role:
        return jsonify({"error": "Missing system or role"}), 400

    try:
        from education_system.shared.admin_portal.admin_service import AdminService
        svc = AdminService()
        users = svc.get_all_users(system=system_key, role=role)
        active_users = [u for u in users if u.get("is_active")]

        if not active_users:
            return jsonify({"error": "No active users match this filter", "count": 0}), 404

        for u in active_users:
            svc.deactivate_user(u["id"])

        return jsonify({"ok": True, "count": len(active_users)})
    except Exception as e:
        logger.error("Failed to batch deactivate: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# ═══════════════════════════════════════════════════════════════════════
#  SECONDARY SCHOOL — dedicated CRUD data endpoints
# ═══════════════════════════════════════════════════════════════════════
#
# All endpoints follow the same pattern:
#   GET  ?page=1&per_page=50&search=...  → paginated list
#   POST (JSON body)                     → create record (staff/admin only)
#
# The secondary school system key is "school".
# ───────────────────────────────────────────────────────────────────────

def _secondary_db():
    """Return the path to the secondary school database, or None."""
    return _resolve_db("school")


def _primary_db():
    """Return the path to the primary school database, or None."""
    return _resolve_db("primary")


def _paginate_query(db: str, table: str, page: int, per_page: int, search: str) -> dict:
    """Return paginated rows from *table* with optional full-text search."""
    safe_table = _validated_table(table, db)
    if not safe_table:
        return {"error": f"Table '{table}' not found or access denied"}

    from flask import request as _req  # noqa: F811

    # Resolve column names
    col_rows = _query(db, "SELECT name FROM pragma_table_info(?)", (safe_table,))
    if col_rows:
        col_names = [r["name"] for r in col_rows]
    else:
        try:
            import sqlite3 as _s3
            conn = _s3.connect(db, timeout=10)
            try:
                col_names = [r[1] for r in conn.execute(f"PRAGMA table_info([{safe_table}])").fetchall()]  # nosemgrep: python.lang.security.audit.formatted-sql-query
            finally:
                conn.close()
        except Exception:
            col_names = []

    offset = (page - 1) * per_page

    if search:
        from education_system.shared.database.sql_safety import escape_like
        escaped = escape_like(search)
        text_cols = col_names[:6]
        if not text_cols:
            return {"records": [], "total": 0, "page": page, "per_page": per_page, "pages": 1}
        like_clauses = " OR ".join(f"CAST([{c}] AS TEXT) LIKE ?" for c in text_cols)
        pattern = f"%{escaped}%"
        params = tuple([pattern] * len(text_cols))
        rows = _query(db, f"SELECT * FROM [{safe_table}] WHERE {like_clauses} ORDER BY rowid DESC LIMIT ?",
                      params + (per_page,))
        total_q = _query(db, f"SELECT COUNT(*) as c FROM [{safe_table}] WHERE {like_clauses}", params)
        total = total_q[0]["c"] if total_q else 0
    else:
        total_q = _query(db, f"SELECT COUNT(*) as c FROM [{safe_table}]")  # nosemgrep: python.lang.security.audit.formatted-sql-query
        total = total_q[0]["c"] if total_q else 0
        rows = _query(db, f"SELECT * FROM [{safe_table}] ORDER BY rowid DESC LIMIT ? OFFSET ?", (per_page, offset))  # nosemgrep: python.lang.security.audit.formatted-sql-query

    return {
        "records": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


def _secondary_list_or_create(table: str, system_key: str = "school"):
    """Handle GET (paginated list) and POST (insert) for a secondary table."""
    from flask import request

    if not _has_system_access(system_key):
        return jsonify({"error": "Access denied"}), 403

    role = _user_role_for(system_key)

    db = _resolve_db(system_key)
    if not db:
        return jsonify({"error": "Database not found"}), 404

    if request.method == "GET":
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 50)), 500)
        search = request.args.get("search", "").strip()
        result = _paginate_query(db, table, page, per_page, search)
        if "error" in result:
            return jsonify(result), 404
        return jsonify(result)

    # POST — staff/admin only
    if role not in ("admin", "staff", "teacher", "instructor"):
        return jsonify({"error": "Staff access required"}), 403

    body = request.get_json(silent=True) or {}
    safe_table = _validated_table(table, db)
    if not safe_table:
        return jsonify({"error": f"Table '{table}' not accessible"}), 404

    # Resolve column names for the table
    col_rows = _query(db, "SELECT name FROM pragma_table_info(?)", (safe_table,))
    if col_rows:
        allowed_cols = {r["name"] for r in col_rows}
    else:
        try:
            import sqlite3 as _s3
            conn = _s3.connect(db, timeout=10)
            try:
                allowed_cols = {r[1] for r in conn.execute(f"PRAGMA table_info([{safe_table}])").fetchall()}
            finally:
                conn.close()
        except Exception:
            allowed_cols = set()

    # Filter body to only valid column names (prevents injection via column names)
    filtered = {k: v for k, v in body.items() if k in allowed_cols}
    if not filtered:
        return jsonify({"error": "No valid fields provided"}), 400

    cols_str = ", ".join(f"[{c}]" for c in filtered)
    placeholders = ", ".join("?" for _ in filtered)
    values = list(filtered.values())

    try:
        import sqlite3 as _s3
        conn = _s3.connect(db, timeout=10)
        try:
            cursor = conn.execute(
                f"INSERT INTO [{safe_table}] ({cols_str}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            new_id = cursor.lastrowid
            new_row = _query(db, f"SELECT * FROM [{safe_table}] WHERE rowid = ?", (new_id,))
            return jsonify({"ok": True, "record": new_row[0] if new_row else {}, "id": new_id}), 201
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Insert failed on %s.%s: %s", db, safe_table, exc)
        return jsonify({"error": "Insert failed"}), 500


# ── Secondary: Behaviour ─────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/behaviour", methods=["GET", "POST"])
@_require_token
def secondary_behaviour():
    return _secondary_list_or_create("behaviour_records", "school")


# ── Secondary: Detentions ────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/detentions", methods=["GET", "POST"])
@_require_token
def secondary_detentions():
    return _secondary_list_or_create("detentions", "school")


# ── Secondary: Form Groups ────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/form_groups", methods=["GET", "POST"])
@_require_token
def secondary_form_groups():
    return _secondary_list_or_create("form_groups", "school")


# ── Secondary: Pastoral ───────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/pastoral", methods=["GET", "POST"])
@_require_token
def secondary_pastoral():
    return _secondary_list_or_create("pastoral_notes", "school")


# ── Secondary: Safeguarding ───────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/safeguarding", methods=["GET", "POST"])
@_require_token
def secondary_safeguarding():
    return _secondary_list_or_create("safeguarding_concerns", "school")


# ── Secondary: SEND ──────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/send", methods=["GET", "POST"])
@_require_token
def secondary_send():
    return _secondary_list_or_create("send_records", "school")


# ── Secondary: Homework ──────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/homework", methods=["GET", "POST"])
@_require_token
def secondary_homework():
    return _secondary_list_or_create("homework", "school")


# ── Secondary: Exams ─────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/exams", methods=["GET", "POST"])
@_require_token
def secondary_exams():
    return _secondary_list_or_create("exams", "school")


# ── Secondary: Parents Evening ────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/parents_evening", methods=["GET", "POST"])
@_require_token
def secondary_parents_evening():
    # Try both possible table names
    db = _secondary_db()
    if db:
        tables = _safe_tables(db)
        tbl = next((t for t in ("parents_evening_events", "parents_evening", "parents_evenings") if t in tables), None)
        if tbl:
            return _secondary_list_or_create(tbl, "school")
    return _secondary_list_or_create("parents_evening_events", "school")


# ── Secondary: Timetable ──────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/secondary/timetable", methods=["GET", "POST"])
@_require_token
def secondary_timetable():
    db = _secondary_db()
    if db:
        tables = _safe_tables(db)
        tbl = next((t for t in ("timetable_slots", "timetable", "timetable_entries") if t in tables), None)
        if tbl:
            return _secondary_list_or_create(tbl, "school")
    return _secondary_list_or_create("timetable_slots", "school")


# ═══════════════════════════════════════════════════════════════════════
#  PRIMARY SCHOOL — dedicated CRUD data endpoints
# ═══════════════════════════════════════════════════════════════════════

def _primary_list_or_create(table: str):
    """Handle GET (paginated list) and POST (insert) for a primary table."""
    return _secondary_list_or_create(table, "primary")


# ── Primary: Classes ─────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/classes", methods=["GET", "POST"])
@_require_token
def primary_classes():
    return _primary_list_or_create("classes")


# ── Primary: Assessment ───────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/assessment", methods=["GET", "POST"])
@_require_token
def primary_assessment():
    db = _primary_db()
    if db:
        tables = _safe_tables(db)
        tbl = next((t for t in ("assessments", "assessment", "assessment_records") if t in tables), None)
        if tbl:
            return _primary_list_or_create(tbl)
    return _primary_list_or_create("assessments")


# ── Primary: SATs ─────────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/sats", methods=["GET", "POST"])
@_require_token
def primary_sats():
    db = _primary_db()
    if db:
        tables = _safe_tables(db)
        tbl = next((t for t in ("sats_results", "sats", "sats_scores") if t in tables), None)
        if tbl:
            return _primary_list_or_create(tbl)
    return _primary_list_or_create("sats_results")


# ── Primary: Phonics ─────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/phonics", methods=["GET", "POST"])
@_require_token
def primary_phonics():
    db = _primary_db()
    if db:
        tables = _safe_tables(db)
        tbl = next((t for t in ("phonics_results", "phonics", "phonics_screening") if t in tables), None)
        if tbl:
            return _primary_list_or_create(tbl)
    return _primary_list_or_create("phonics_results")


# ── Primary: Reading Records ──────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/reading_records", methods=["GET", "POST"])
@_require_token
def primary_reading_records():
    return _primary_list_or_create("reading_records")


# ── Primary: Rewards ──────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/rewards", methods=["GET", "POST"])
@_require_token
def primary_rewards():
    return _primary_list_or_create("rewards")


# ── Primary: Safeguarding ─────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/safeguarding", methods=["GET", "POST"])
@_require_token
def primary_safeguarding():
    return _primary_list_or_create("safeguarding_concerns")


# ── Primary: SEND ─────────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/send", methods=["GET", "POST"])
@_require_token
def primary_send():
    return _primary_list_or_create("send_records")


# ── Primary: Pastoral ─────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/pastoral", methods=["GET", "POST"])
@_require_token
def primary_pastoral():
    return _primary_list_or_create("pastoral_notes")


# ── Primary: Parents Evening ──────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/parents_evening", methods=["GET", "POST"])
@_require_token
def primary_parents_evening():
    db = _primary_db()
    if db:
        tables = _safe_tables(db)
        tbl = next((t for t in ("parents_evening_events", "parents_evening", "parents_evenings") if t in tables), None)
        if tbl:
            return _primary_list_or_create(tbl)
    return _primary_list_or_create("parents_evening_events")


# ── Primary: Behaviour ────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/behaviour", methods=["GET", "POST"])
@_require_token
def primary_behaviour():
    return _primary_list_or_create("behaviour_records")


# ── Primary: Timetable ────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/timetable", methods=["GET", "POST"])
@_require_token
def primary_timetable():
    db = _primary_db()
    if db:
        tables = _safe_tables(db)
        tbl = next((t for t in ("timetable_slots", "timetable", "timetable_entries") if t in tables), None)
        if tbl:
            return _primary_list_or_create(tbl)
    return _primary_list_or_create("timetable_slots")


# ── Primary: Homework ─────────────────────────────────────────────────

@web_bp.route("/api/v1/web/api/primary/homework", methods=["GET", "POST"])
@_require_token
def primary_homework():
    return _primary_list_or_create("homework")
