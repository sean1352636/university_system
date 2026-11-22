"""Attendance ↔ LMS: settings, connection test, preview, push/export, sync log.

Shared by the attendance tracker's LMS Integration window and the CLI's
"LMS integration" option, so both send the same rows.

* Settings live in ``lms_settings`` (one row, id 1). The API token is not
  kept there: it goes to ``paths.UNIVERSITY_LMS_API_TOKEN_FILE`` (owner-only)
  or the ``LMS_API_TOKEN`` environment variable. A token left in the old
  ``api_key`` column is moved to the file the next time settings are saved.
* ``test_connection`` makes one real HTTPS call to the platform's own
  "who am I / site info" endpoint and returns what it said, or the error.
* ``run_sync`` pushes attendance where the platform has a usable write API
  (Canvas gradebook via an "Attendance" assignment, or a Custom API that
  accepts a JSON POST). Everything else, and any run with no reachable LMS,
  writes the LMS-importable CSV instead. Each run is logged in
  ``lms_sync_log``.
"""

from __future__ import annotations

import base64
import csv
import datetime
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15
PLATFORMS = ("Moodle", "Canvas", "Blackboard", "Google Classroom",
             "Microsoft Teams", "Custom API")
# Platforms whose fixed API host is used when no URL is given.
DEFAULT_URLS = {
    "Google Classroom": "https://classroom.googleapis.com",
    "Microsoft Teams": "https://graph.microsoft.com",
}
# Platforms with a live attendance push; the rest get the CSV export.
PUSH_PLATFORMS = ("Canvas", "Custom API")
# Same rule as the attendance notifications: late still counts as attended.
ATTENDED = ("present", "late")
CANVAS_ASSIGNMENT_NAME = "Attendance"

_RECORDS_SQL = """
    SELECT ar.student_id AS student_id,
           TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) AS name,
           s.email_address AS email,
           ar.module_code AS module_code,
           ar.date AS session_date,
           ar.session_id AS session_id,
           ar.status AS status
    FROM attendance_records ar
    LEFT JOIN students s ON ar.student_id = s.student_id
"""
RECORD_COLUMNS = ("student_id", "name", "email", "module_code",
                  "session_date", "session_id", "status")


def _paths():
    import education_system.paths as paths
    return paths


def _connect(conn):
    """Use the caller's connection, or open one we must close."""
    return (conn, False) if conn is not None else (get_connection(), True)


# ── schema ──────────────────────────────────────────────────────────────


def ensure_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lms_settings (
            id INTEGER PRIMARY KEY,
            platform TEXT,
            api_url TEXT,
            api_key TEXT,
            username TEXT,
            auto_sync INTEGER,
            sync_grades INTEGER,
            bidirectional INTEGER,
            sync_frequency TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lms_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            direction TEXT,
            platform TEXT,
            mode TEXT,
            status TEXT NOT NULL,
            records_synced INTEGER NOT NULL DEFAULT 0,
            errors INTEGER NOT NULL DEFAULT 0,
            duration_seconds REAL,
            date_from TEXT,
            date_to TEXT,
            module_code TEXT,
            export_path TEXT,
            detail TEXT,
            run_by TEXT
        )
    """)


# ── token (secrets file, never the DB) ──────────────────────────────────


def token_file() -> Path:
    return Path(_paths().UNIVERSITY_LMS_API_TOKEN_FILE)


def read_token() -> str:
    value = os.environ.get("LMS_API_TOKEN")
    if value:
        return value.strip()
    try:
        return token_file().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_token(token: str) -> Path:
    """Write the token to the secrets file, readable by its owner only."""
    path = token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(token)
    os.chmod(path, 0o600)
    return path


# ── settings ────────────────────────────────────────────────────────────


def load_settings(conn=None) -> dict:
    """The saved settings (token excluded), or {} when none are saved."""
    conn, own = _connect(conn)
    try:
        ensure_tables(conn)
        row = conn.execute(
            "SELECT platform, api_url, username, auto_sync, sync_grades, "
            "bidirectional, sync_frequency FROM lms_settings WHERE id = 1"
        ).fetchone()
    finally:
        if own:
            conn.close()
    if not row:
        return {}
    keys = ("platform", "api_url", "username", "auto_sync", "sync_grades",
            "bidirectional", "sync_frequency")
    return dict(zip(keys, tuple(row)))


def save_settings(settings: dict, token: Optional[str], conn=None) -> None:
    """Save *settings*; *token* goes to the secrets file.

    A blank *token* keeps the stored one. A plaintext token still in the
    ``api_key`` column (written by older versions) is moved to the file
    when no token is stored yet, and the column is cleared either way.
    """
    conn, own = _connect(conn)
    try:
        ensure_tables(conn)
        token = (token or "").strip()
        if not token and not read_token():
            row = conn.execute(
                "SELECT api_key FROM lms_settings WHERE id = 1").fetchone()
            legacy = (row[0] or "").strip() if row else ""
            if legacy:
                token = legacy
        if token:
            write_token(token)
        conn.execute("""
            INSERT OR REPLACE INTO lms_settings
                (id, platform, api_url, api_key, username, auto_sync,
                 sync_grades, bidirectional, sync_frequency)
            VALUES (1, ?, ?, '', ?, ?, ?, ?, ?)
        """, (
            settings.get("platform") or "",
            (settings.get("api_url") or "").strip(),
            (settings.get("username") or "").strip(),
            1 if settings.get("auto_sync") else 0,
            1 if settings.get("sync_grades") else 0,
            1 if settings.get("bidirectional") else 0,
            settings.get("sync_frequency") or "",
        ))
        conn.commit()
    finally:
        if own:
            conn.close()


# ── HTTP ────────────────────────────────────────────────────────────────


class LMSError(Exception):
    """A failed LMS call, with a message fit to show the user."""


def _base_url(platform: str, api_url: str) -> str:
    url = (api_url or "").strip() or DEFAULT_URLS.get(platform, "")
    if not url:
        raise LMSError("No API endpoint URL is configured.")
    parts = urllib.parse.urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if parts.scheme != "https" and not (parts.scheme == "http" and local):
        raise LMSError("The API endpoint must be an https:// URL.")
    if not parts.netloc:
        raise LMSError(f"Not a valid URL: {url}")
    return url.rstrip("/")


def _request(url: str, *, method: str = "GET", headers=None, data=None,
             timeout: float = TIMEOUT_SECONDS):
    """Make one HTTP call and return (status, decoded JSON or text)."""
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Accept": "application/json",
                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - scheme checked in _base_url
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()[:500].decode("utf-8", "replace")
        raise LMSError(f"HTTP {exc.code} {exc.reason} from {url.split('?')[0]}"
                       + (f": {body}" if body else "")) from exc
    except urllib.error.URLError as exc:
        raise LMSError(f"Could not reach {url.split('?')[0]}: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:
        raise LMSError(f"Could not reach {url.split('?')[0]}: {exc}") from exc
    text = body.decode("utf-8", "replace")
    try:
        return status, json.loads(text) if text else None
    except ValueError:
        return status, text


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _moodle_call(base: str, token: str, function: str, **params):
    query = urllib.parse.urlencode({"wstoken": token, "wsfunction": function,
                                    "moodlewsrestformat": "json", **params})
    _status, body = _request(f"{base}/webservice/rest/server.php?{query}")
    if isinstance(body, dict) and body.get("exception"):
        raise LMSError(f"Moodle refused {function}: {body.get('message') or body.get('errorcode')}")
    return body


def _blackboard_token(base: str, key: str, secret: str) -> str:
    if not key:
        raise LMSError("Blackboard needs the REST application key in the Username field "
                       "and its secret as the API key.")
    basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
    _status, body = _request(
        f"{base}/learn/api/public/v1/oauth2/token", method="POST",
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data=b"grant_type=client_credentials")
    if not isinstance(body, dict) or not body.get("access_token"):
        raise LMSError("Blackboard did not return an access token.")
    return body["access_token"]


def test_connection(platform: str, api_url: str, token: str,
                    username: str = "") -> list:
    """Call the platform's site-info endpoint; return (label, value) lines.

    Raises LMSError with the real reason when the call fails.
    """
    if not token:
        raise LMSError("No API key/token is configured.")
    base = _base_url(platform, api_url)
    if platform == "Moodle":
        info = _moodle_call(base, token, "core_webservice_get_site_info")
        return [("Site", info.get("sitename")),
                ("Moodle release", info.get("release")),
                ("Signed in as", info.get("username")),
                ("Web-service functions allowed", len(info.get("functions") or []))]
    if platform == "Canvas":
        _s, me = _request(f"{base}/api/v1/users/self", headers=_bearer(token))
        return [("Signed in as", (me or {}).get("name")),
                ("Canvas user id", (me or {}).get("id"))]
    if platform == "Blackboard":
        access = _blackboard_token(base, username, token)
        _s, ver = _request(f"{base}/learn/api/public/v1/system/version",
                           headers=_bearer(access))
        learn = (ver or {}).get("learn") or {}
        version = ".".join(str(learn.get(k)) for k in ("major", "minor", "patch")
                           if learn.get(k) is not None)
        return [("Blackboard Learn version", version or "unknown"),
                ("OAuth token", "issued")]
    if platform == "Google Classroom":
        _s, body = _request(f"{base}/v1/courses?pageSize=50", headers=_bearer(token))
        return [("Courses visible to this token", len((body or {}).get("courses") or []))]
    if platform == "Microsoft Teams":
        _s, me = _request(f"{base}/v1.0/me", headers=_bearer(token))
        return [("Signed in as", (me or {}).get("displayName")),
                ("User principal", (me or {}).get("userPrincipalName"))]
    status, _body = _request(base, headers=_bearer(token))
    return [("Endpoint", base), ("HTTP status", status)]


# ── records ─────────────────────────────────────────────────────────────


def module_codes(conn=None) -> list:
    """Module codes that have attendance recorded."""
    conn, own = _connect(conn)
    try:
        rows = conn.execute(
            "SELECT DISTINCT module_code FROM attendance_records "
            "WHERE module_code IS NOT NULL AND module_code <> '' ORDER BY 1"
        ).fetchall()
    finally:
        if own:
            conn.close()
    return [r[0] for r in rows]


def collect_records(date_from: Optional[str] = None, date_to: Optional[str] = None,
                    module_code: Optional[str] = None, conn=None) -> list:
    """The attendance rows a sync would send, newest first, as dicts."""
    clauses, params = [], []
    if date_from:
        clauses.append("ar.date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("ar.date <= ?")
        params.append(date_to)
    if module_code:
        clauses.append("ar.module_code = ?")
        params.append(module_code)
    sql = _RECORDS_SQL + (" WHERE " + " AND ".join(clauses) if clauses else "")
    sql += " ORDER BY ar.date DESC, ar.module_code, ar.student_id"
    conn, own = _connect(conn)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        if own:
            conn.close()
    return [dict(zip(RECORD_COLUMNS, tuple(r))) for r in rows]


def attendance_grades(records: list) -> list:
    """Per student per module: sessions, attended and percentage."""
    totals: dict = {}
    for rec in records:
        key = (rec["module_code"], rec["student_id"])
        entry = totals.setdefault(key, {"module_code": key[0], "student_id": key[1],
                                        "sessions": 0, "attended": 0})
        entry["sessions"] += 1
        if (rec.get("status") or "").lower() in ATTENDED:
            entry["attended"] += 1
    for entry in totals.values():
        entry["percentage"] = round(100.0 * entry["attended"] / entry["sessions"], 1)
    return sorted(totals.values(), key=lambda e: (e["module_code"], e["student_id"]))


def export_csv(records: list) -> Path:
    """Write *records* as the Moodle/Canvas-importable CSV; return its path."""
    export_dir = Path(_paths().UNIVERSITY_EXPORTS_DIR) / "lms"
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = export_dir / f"lms_attendance_{stamp}.csv"
    # A standard, comma-separated file with a header row: the shape Moodle
    # ("Import > CSV") and Canvas ("Gradebook > Import") both accept.
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RECORD_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    return path


# ── push ────────────────────────────────────────────────────────────────


def _push_canvas(base, token, records, log, cancelled):
    """Post each student's attendance % to the course's "Attendance" assignment.

    Courses are addressed by SIS id (= module code) and students by SIS user
    id (= student id), so no id mapping table is needed.
    """
    pushed = errors = 0
    by_module: dict = {}
    for grade in attendance_grades(records):
        by_module.setdefault(grade["module_code"], []).append(grade)
    for mc, grades in by_module.items():
        if cancelled():
            log("Cancelled before module %s." % mc)
            break
        course = "sis_course_id:" + urllib.parse.quote(str(mc), safe="")
        try:
            _s, found = _request(
                f"{base}/api/v1/courses/{course}/assignments?"
                + urllib.parse.urlencode({"search_term": CANVAS_ASSIGNMENT_NAME}),
                headers=_bearer(token))
            match = [a for a in (found or [])
                     if str(a.get("name", "")).strip().lower() == CANVAS_ASSIGNMENT_NAME.lower()]
            if not match:
                raise LMSError(f'no "{CANVAS_ASSIGNMENT_NAME}" assignment in course {mc}')
            form = {f"grade_data[sis_user_id:{g['student_id']}][posted_grade]": f"{g['percentage']}%"
                    for g in grades}
            _request(f"{base}/api/v1/courses/{course}/assignments/{match[0]['id']}"
                     "/submissions/update_grades", method="POST",
                     headers={**_bearer(token),
                              "Content-Type": "application/x-www-form-urlencoded"},
                     data=urllib.parse.urlencode(form).encode())
            pushed += len(grades)
            log(f"{mc}: {len(grades)} attendance grade(s) sent.")
        except LMSError as exc:
            errors += 1
            log(f"{mc}: not sent - {exc}")
    return pushed, errors


def _push_custom(base, token, records, sync_grades, date_from, date_to):
    payload = {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
               "date_from": date_from, "date_to": date_to, "records": records}
    if sync_grades:
        payload["grades"] = attendance_grades(records)
    _request(base, method="POST",
             headers={**_bearer(token), "Content-Type": "application/json"},
             data=json.dumps(payload, default=str).encode())
    return len(records), 0


def run_sync(*, platform: str, api_url: str, token: str, username: str = "",
             direction: str = "to_lms", sync_grades: bool = True,
             date_from: Optional[str] = None, date_to: Optional[str] = None,
             module_code: Optional[str] = None, run_by: str = "",
             log: Callable[[str], None] = print,
             cancelled: Callable[[], bool] = lambda: False) -> dict:
    """Send attendance to the LMS (or export the CSV) and log the run."""
    started = time.monotonic()
    started_at = datetime.datetime.now().isoformat(timespec="seconds")
    result = {"status": "Failed", "mode": "", "records": 0, "errors": 0,
              "export_path": None, "detail": ""}
    notes = []

    def note(msg):
        notes.append(msg)
        log(msg)

    try:
        if direction in ("from_lms", "bidirectional"):
            note("Importing attendance from the LMS is not supported; "
                 "nothing is read back from the LMS.")
        if direction == "from_lms":
            result["status"] = "Not run"
            return result
        records = collect_records(date_from, date_to, module_code)
        note(f"{len(records)} attendance record(s) in range.")
        if not records:
            result["status"] = "Nothing to sync"
            return result

        live = platform in PUSH_PLATFORMS and token and (api_url or "").strip()
        if live and platform == "Canvas" and not sync_grades:
            note("Canvas only takes attendance as grades; "
                 "'Sync attendance as grades' is off, so the CSV is written instead.")
            live = False
        if live:
            try:
                base = _base_url(platform, api_url)
                note(f"Sending to {platform} at {base} ...")
                if platform == "Canvas":
                    # Reachable and authorised first, so an outage falls back to the CSV.
                    test_connection(platform, api_url, token, username)
                    sent, errors = _push_canvas(base, token, records, note, cancelled)
                else:
                    sent, errors = _push_custom(base, token, records, sync_grades,
                                                date_from, date_to)
                result.update(mode="push", records=sent, errors=errors)
                result["status"] = ("Cancelled" if cancelled() else
                                    "Success" if not errors else
                                    "Partial" if sent else "Failed")
                return result
            except LMSError as exc:
                note(f"{platform} could not be reached ({exc}); writing the CSV instead.")
        elif platform not in PUSH_PLATFORMS:
            note(f"{platform} has no attendance push here; writing the CSV for its importer.")
        else:
            note("No LMS URL/token configured; writing the CSV instead.")
        path = export_csv(records)
        note(f"CSV written: {path}")
        result.update(mode="csv", status="Exported", records=len(records),
                      export_path=str(path))
        return result
    except Exception as exc:  # noqa: BLE001 - recorded in the log row and shown to the user
        result["errors"] += 1
        note(f"Sync failed: {exc}")
        return result
    finally:
        result["duration"] = round(time.monotonic() - started, 2)
        result["detail"] = "\n".join(notes)
        try:
            _log_run(started_at, direction, platform, result, date_from, date_to,
                     module_code, run_by)
        except Exception:  # noqa: BLE001 - the run itself already happened
            logger.exception("Could not write the LMS sync log row")


def _log_run(started_at, direction, platform, result, date_from, date_to,
             module_code, run_by) -> None:
    conn = get_connection()
    try:
        ensure_tables(conn)
        conn.execute("""
            INSERT INTO lms_sync_log
                (started_at, direction, platform, mode, status, records_synced,
                 errors, duration_seconds, date_from, date_to, module_code,
                 export_path, detail, run_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (started_at, direction, platform, result.get("mode"), result["status"],
              result["records"], result["errors"], result.get("duration"),
              date_from, date_to, module_code, result.get("export_path"),
              result.get("detail"), run_by))
        conn.commit()
    finally:
        conn.close()


def sync_history(days: Optional[int] = 30, conn=None) -> list:
    """Logged runs, newest first; *days* None means all."""
    conn, own = _connect(conn)
    try:
        ensure_tables(conn)
        sql = ("SELECT started_at, direction, status, records_synced, errors, "
               "duration_seconds, mode, export_path FROM lms_sync_log")
        params = []
        if days:
            sql += " WHERE started_at >= ?"
            params.append((datetime.datetime.now()
                           - datetime.timedelta(days=days)).isoformat(timespec="seconds"))
        rows = conn.execute(sql + " ORDER BY started_at DESC, id DESC", params).fetchall()
    finally:
        if own:
            conn.close()
    keys = ("started_at", "direction", "status", "records", "errors",
            "duration", "mode", "export_path")
    return [dict(zip(keys, tuple(r))) for r in rows]


__all__ = [
    "PLATFORMS", "LMSError", "ensure_tables", "read_token", "write_token",
    "load_settings", "save_settings", "test_connection", "module_codes",
    "collect_records", "attendance_grades", "export_csv", "run_sync",
    "sync_history",
]
