"""Read the university's real audit and activity records for the admin viewer.

The university writes audit history to several stores, each with its own
shape; this module reads them all (read-only) into one row format so a viewer
can filter them together:

==========================  ======================  ==============================
store                       written by              table
==========================  ======================  ==============================
student_records.db          activity logger         ``activity_log``
student_records.db          security audit trail    ``audit_trail``
student_records.db          immutable audit chain   ``immutable_audit_log``
student_records.db          legacy GUI audit        ``audit_log``
platform audit.db           platform governance     ``audit_log`` (university +
                                                    shared security events)
==========================  ======================  ==============================

Every row is returned as a dict with ``timestamp`` (``YYYY-MM-DD HH:MM:SS``),
``level`` (INFO/WARNING/ERROR/CRITICAL), ``category`` (Authentication,
Database, API, User Actions, System), ``user``, ``action``, ``ip``,
``details`` and ``source``.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

LEVELS = ("INFO", "WARNING", "ERROR", "CRITICAL")
CATEGORIES = ("Authentication", "Database", "API", "User Actions", "System")

#: (table, timestamp, user, action, resource, ip, details, outcome) per store.
#: Each entry is SQL text over that table's known columns - literals only.
_UNIVERSITY_SOURCES = (
    ("activity_log",
     "SELECT timestamp AS ts, COALESCE(username, CAST(user_id AS TEXT)) AS usr, action AS act, "
     "COALESCE(entity_type, '') AS res, ip_address AS ip, details AS det, NULL AS ok, "
     "NULL AS sev FROM activity_log"),
    ("audit_trail",
     "SELECT timestamp AS ts, COALESCE(username, CAST(user_id AS TEXT)) AS usr, action AS act, "
     "COALESCE(resource_type, module_name, '') AS res, ip_address AS ip, "
     "COALESCE(details, error_message) AS det, success AS ok, "
     "CASE WHEN error_message IS NOT NULL AND error_message != '' THEN 'error' END AS sev "
     "FROM audit_trail"),
    ("immutable_audit_log",
     "SELECT timestamp AS ts, CAST(user_id AS TEXT) AS usr, action AS act, "
     "COALESCE(resource_type, '') AS res, ip_address AS ip, details AS det, NULL AS ok, "
     "NULL AS sev FROM immutable_audit_log"),
    ("audit_log",
     "SELECT timestamp AS ts, COALESCE(user_name, CAST(user_id AS TEXT)) AS usr, action AS act, "
     "COALESCE(table_name, table_affected, entity_type, '') AS res, ip_address AS ip, "
     "COALESCE(details, new_values) AS det, success AS ok, NULL AS sev FROM audit_log"),
)

_PLATFORM_SOURCE = (
    "SELECT timestamp AS ts, COALESCE(username, CAST(user_id AS TEXT)) AS usr, action AS act, "
    "COALESCE(resource_type, '') AS res, ip_address AS ip, details AS det, NULL AS ok, "
    "severity AS sev, system_key AS sys FROM audit_log "
    "WHERE system_key IN ('university', 'shared')"
)

# Normalised timestamp: '2026-10-27T08:00:01.235Z' -> '2026-10-27 08:00:01'.
_TS = "REPLACE(SUBSTR(ts, 1, 19), 'T', ' ')"

_AUTH_WORDS = ("login", "logout", "log in", "log out", "sign in", "sign-in", "password",
               "mfa", "totp", "session", "auth", "token", "lockout", "locked",
               "sq_", "security_question", "security question", "reset")
_DB_WORDS = ("backup", "restore", "database", "vacuum", "migration", "schema", "import",
             "export", "integrity")
_API_WORDS = ("api", "webhook", "endpoint", "oauth")
_FAIL_WORDS = ("fail", "denied", "invalid", "locked", "lockout", "rejected", "unauthor",
               "forbidden", "breach", "suspicious")


def _db_path_defaults():
    from education_system.paths import PLATFORM_AUDIT_DB_FILE, UNIVERSITY_DEFAULT_DB_PATH
    return str(UNIVERSITY_DEFAULT_DB_PATH), str(PLATFORM_AUDIT_DB_FILE)


def _open_ro(path: str):
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error:
        return None
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn, table: str) -> set[str]:
    try:
        # db-audit: ignore[DBW001] - table names are the module's literals
        return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
    except sqlite3.Error:
        return set()


def categorise(action: str, resource: str, source: str, user: str) -> str:
    text = f"{action} {resource}".lower()
    if any(w in text for w in _AUTH_WORDS):
        return "Authentication"
    if any(w in text for w in _API_WORDS):
        return "API"
    if any(w in text for w in _DB_WORDS):
        return "Database"
    if (user or "").lower() in ("", "system", "none", "scheduler"):
        return "System"
    return "User Actions"


def level_for(action: str, ok, severity) -> str:
    sev = (str(severity).lower() if severity is not None else "")
    if sev in ("critical",):
        return "CRITICAL"
    if sev in ("error",):
        return "ERROR"
    if sev == "warning":
        return "WARNING"
    if ok is not None and str(ok).strip().lower() in ("0", "false", "no"):
        return "WARNING"
    if any(w in (action or "").lower() for w in _FAIL_WORDS):
        return "WARNING"
    # 'security' severity marks the kind of event, not a problem: a
    # successful security-question reset is still INFO.
    return "INFO"


def _details_text(value, default_user):
    """Return (details string, username found in JSON details or None)."""
    if value is None:
        return "", None
    text = str(value)
    user = None
    if text[:1] in "{[":
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                user = data.get("username") or data.get("user")
                # The activity logger packs its fields as {"message": ...,
                # "module": ..., ...}; show the message first.
                desc = data.get("description") or data.get("message")
                if desc:
                    rest = {k: v for k, v in data.items()
                            if k not in ("description", "message") and v not in (None, "")}
                    text = str(desc) + (f"  {json.dumps(rest, default=str)}" if rest else "")
        except ValueError:
            pass
    return ("" if text == "None" else text), user


def since_for(range_key: str, now: datetime | None = None) -> str | None:
    """Map a date-range choice ('24h', '7d', '30d', 'all') to a lower bound."""
    now = now or datetime.now()
    delta = {"24h": timedelta(hours=24), "7d": timedelta(days=7),
             "30d": timedelta(days=30)}.get(range_key)
    return (now - delta).strftime("%Y-%m-%d %H:%M:%S") if delta else None


def _query(conn, base_sql, since, until, limit, source, extra_cols=()):
    where = []
    params = []
    if since:
        where.append(_TS + " >= ?")
        params.append(since)
    if until:
        where.append(_TS + " <= ?")
        params.append(until)
    sql = "SELECT * FROM (" + base_sql + ")"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY " + _TS + " DESC LIMIT ?"
    params.append(int(limit))
    out = []
    for row in conn.execute(sql, params):
        ts = (row["ts"] or "")
        ts = str(ts)[:19].replace("T", " ")
        details, json_user = _details_text(row["det"], row["usr"])
        user = str(json_user or row["usr"] or "system")
        action = str(row["act"] or "")
        resource = str(row["res"] or "")
        label = source
        if "sys" in row.keys() and row["sys"]:
            label = f"platform:{row['sys']}"
        out.append({
            "timestamp": ts,
            "level": level_for(action, row["ok"], row["sev"]),
            "category": categorise(action, resource, source, user),
            "user": user,
            "action": action,
            "resource": resource,
            "ip": str(row["ip"] or ""),
            "details": details,
            "source": label,
        })
    return out


def read_audit_entries(*, since: str | None = None, until: str | None = None,
                       level: str | None = None, category: str | None = None,
                       search: str | None = None, limit: int = 5000,
                       university_db: str | None = None, platform_db: str | None = None,
                       errors: list | None = None) -> list[dict]:
    """Merged, newest-first audit entries from every store, filtered.

    *level* / *category* are one of :data:`LEVELS` / :data:`CATEGORIES` (or
    None for all). *search* matches user, action, resource, IP and details,
    case-insensitively. Stores that are missing are skipped; problems are
    appended to *errors* when given.
    """
    default_uni, default_platform = _db_path_defaults()
    errors = errors if errors is not None else []
    entries: list[dict] = []

    conn = _open_ro(university_db or default_uni)
    if conn is not None:
        try:
            for table, sql in _UNIVERSITY_SOURCES:
                if not _table_columns(conn, table):
                    continue
                try:
                    entries.extend(_query(conn, sql, since, until, limit, table))
                except sqlite3.Error as exc:
                    errors.append(f"{table}: {exc}")
        finally:
            conn.close()
    else:
        errors.append("university database could not be opened")

    conn = _open_ro(platform_db or default_platform)
    if conn is not None:
        try:
            if _table_columns(conn, "audit_log"):
                entries.extend(_query(conn, _PLATFORM_SOURCE, since, until, limit, "platform"))
        except sqlite3.Error as exc:
            errors.append(f"platform audit: {exc}")
        finally:
            conn.close()

    if level:
        entries = [e for e in entries if e["level"] == level]
    if category:
        entries = [e for e in entries if e["category"] == category]
    if search:
        needle = search.lower()
        entries = [e for e in entries if needle in " ".join(
            (e["user"], e["action"], e["resource"], e["ip"], e["details"], e["source"])).lower()]

    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return entries[:limit]
