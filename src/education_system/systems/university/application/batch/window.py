"""What the Batch Operations window shows beyond the importers themselves:
its settings, the dashboard, the database it works on, a preview of a bulk
update, "undo the last operation", the history (jobs and exports
together) and the e-mail that tells someone a job has finished.

Settings (``batch_settings``, administrators change them) are all honoured:

* ``backup_before_import`` - a full backup is taken before a real import,
  bulk run or undo (``backup_needed``; the window takes it).
* ``duplicate_rule`` - ``name_dob`` (the student service's rule) or
  ``name_dob_email``, which also treats a new row whose e-mail address
  belongs to an existing student as a duplicate (``batch_imports``).
* ``notify_addresses`` - who is e-mailed when a job finishes
  (``job_notice_emails``).
* ``default_mapping_<kind>`` - the saved column mapping chosen first for
  that kind of import.
* ``history_days`` - how far back the History tab looks by default.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from education_system.systems.university.application.batch import reports as batch_reports

ADMIN_ROLES = ("admin", "administrator", "superadmin")
KINDS = ("students", "marks", "staff", "enrolments")
DUPLICATE_RULES = {"name_dob": "Same name and date of birth",
                   "name_dob_email": "Same name and date of birth, or the same e-mail address"}
DEFAULTS = {"backup_before_import": "0", "duplicate_rule": "name_dob", "notify_addresses": "",
            "history_days": "90", **{f"default_mapping_{k}": "" for k in KINDS}}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CLI_COMMAND = "python -m education_system --university --cli   (then: Batch operations)"


def _ensure(conn):
    from education_system.systems.university.infrastructure.database.schemas import (
        batch_jobs_schema,
    )
    batch_jobs_schema.apply_to_connection(conn)


# ── settings ────────────────────────────────────────────────────────────


def settings(conn) -> dict:
    _ensure(conn)
    out = dict(DEFAULTS)
    out.update({k: v for k, v in conn.execute("SELECT key, value FROM batch_settings")})
    return out


def setting(conn, key) -> str:
    return settings(conn).get(key, DEFAULTS.get(key, ""))


def _check(conn, key, value) -> str:
    value = str(value if value is not None else "").strip()
    if key not in DEFAULTS:
        raise ValueError(f"Unknown setting {key!r}")
    if key == "backup_before_import":
        value = "1" if value.lower() in ("1", "true", "yes", "on") else "0"
    elif key == "duplicate_rule" and value not in DUPLICATE_RULES:
        raise ValueError("Choose one of the duplicate rules")
    elif key == "history_days":
        if not value.isdigit() or not 1 <= int(value) <= 3650:
            raise ValueError("History days must be a whole number from 1 to 3650")
    elif key == "notify_addresses":
        addresses = [a.strip() for a in re.split(r"[,;\s]+", value) if a.strip()]
        bad = [a for a in addresses if not _EMAIL.match(a)]
        if bad:
            raise ValueError("Not e-mail addresses: " + ", ".join(bad))
        value = ", ".join(addresses)
    elif key.startswith("default_mapping_") and value:
        if not value.isdigit() or not conn.execute(
                "SELECT 1 FROM batch_import_mappings WHERE id = ?", (int(value),)).fetchone():
            raise ValueError("That saved mapping no longer exists")
    return value


def save_settings(conn, viewer, values: dict) -> dict:
    """Change settings (administrators). Returns the settings now in force."""
    if str(viewer.role or "").lower() not in ADMIN_ROLES:
        raise ValueError("Only an administrator can change the batch settings")
    _ensure(conn)
    for key, value in values.items():
        clean = _check(conn, key, value)
        conn.execute("INSERT INTO batch_settings (key, value, updated_by, updated_at) VALUES "
                     "(?, ?, ?, datetime('now')) ON CONFLICT(key) DO UPDATE SET value = "
                     "excluded.value, updated_by = excluded.updated_by, updated_at = "
                     "excluded.updated_at", (key, clean, viewer.username))
    return settings(conn)


def backup_needed(conn) -> bool:
    return setting(conn, "backup_before_import") == "1"


def duplicate_by_email(conn) -> bool:
    return setting(conn, "duplicate_rule") == "name_dob_email"


def default_mapping(conn, kind) -> int | None:
    value = setting(conn, f"default_mapping_{kind}")
    return int(value) if value.isdigit() else None


# ── the database ────────────────────────────────────────────────────────


def database_info(conn, db_path=None) -> dict:
    """The university database the window works on (it never switches)."""
    path = db_path or conn.execute("PRAGMA database_list").fetchone()[2]
    size = os.path.getsize(path) if path and os.path.exists(path) else 0
    tables = {}
    for name in ("students", "staff", "student_modules", "module_grades", "batch_jobs",
                 "batch_job_rows", "batch_watch_folders"):
        try:
            tables[name] = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]  # nosec B608
        except Exception:
            tables[name] = None
    page = conn.execute("PRAGMA page_size").fetchone()[0]
    free = conn.execute("PRAGMA freelist_count").fetchone()[0]
    return {"path": path, "size_mb": round(size / 1048576, 2),
            "modified": (datetime.fromtimestamp(os.path.getmtime(path)).isoformat(
                timespec="seconds") if path and os.path.exists(path) else None),
            "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
            "tables": conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
                                   ).fetchone()[0],
            "free_mb": round(page * free / 1048576, 2), "counts": tables}


def integrity_check(conn) -> list[str]:
    """``PRAGMA quick_check`` (read-only); ``["ok"]`` when sound."""
    return [r[0] for r in conn.execute("PRAGMA quick_check(50)").fetchall()]


# ── the dashboard ───────────────────────────────────────────────────────


def dashboard(conn, viewer, days=30) -> dict:
    """Real figures for the Dashboard: recent jobs, success, rows, failures,
    scheduled runs, the database."""
    from education_system.systems.university.application.batch import schedule as batch_schedule
    _ensure(conn)
    since = f"-{int(days)} days"
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(total), 0), COALESCE(SUM(succeeded), 0), "
        "COALESCE(SUM(skipped), 0), COALESCE(SUM(failed), 0) FROM batch_jobs WHERE "
        "started_at >= datetime('now', ?)", (since,)).fetchone()
    jobs, rows, ok, skipped, failed = (int(v or 0) for v in row)
    running = conn.execute("SELECT COUNT(*) FROM batch_jobs WHERE status = 'running'"
                           ).fetchone()[0]
    try:
        scheduled = batch_schedule.scheduled_tasks(conn, viewer)
    except ValueError:
        scheduled = []
    exports = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(result_count), 0) FROM student_search_audit WHERE "
        "action = 'export' AND at >= datetime('now', ?)", (since,)).fetchone() \
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'student_search_audit'"
                        ).fetchone() else (0, 0)
    info = database_info(conn)
    return {"days": days, "jobs": jobs, "rows": rows, "succeeded": ok, "skipped": skipped,
            "failed": failed, "running": running,
            "success_rate": round(100.0 * ok / (ok + failed), 1) if ok + failed else None,
            "exports": exports[0], "rows_exported": exports[1],
            "scheduled": scheduled, "recent": batch_reports.history(conn)[:10],
            "database": info}


# ── a bulk update, before it runs ───────────────────────────────────────

_RECORD = ("first_name", "last_name", "course", "status", "mode_of_study", "fee_status",
           "email_address")


def _record(conn, sid):
    row = conn.execute(f"SELECT {', '.join(_RECORD)} FROM students WHERE "  # nosec B608
                       "student_id = ?", (sid,)).fetchone()
    return dict(zip(_RECORD, tuple(row))) if row else None


def _on_module(conn, sid, module):
    return conn.execute("SELECT 1 FROM student_modules WHERE student_id = ? AND module_code = ? "
                        "AND LOWER(COALESCE(status, 'enrolled')) IN ('enrolled', 'active', "
                        "'registered')", (sid, module)).fetchone() is not None


def _now_and_after(conn, sid, record, action, value):
    """(value now, value after) of what ``action`` changes for one student."""
    if action == "set_field":
        return record.get(value[0]) if value else None, value[1] if value else None
    if action == "transfer":
        return record["course"], value
    if action in ("withdraw", "reinstate"):
        return record["status"], "Withdrawn" if action == "withdraw" else "Active"
    if action in ("enrol_module", "unenrol_module"):
        now = "enrolled" if _on_module(conn, sid, value) else "not enrolled"
        return now, "enrolled" if action == "enrol_module" else "not enrolled"
    return record["email_address"] or "(no address)", "e-mailed"


def _check_preview(viewer, action, value, bulk):
    if action not in bulk.ACTIONS:
        raise ValueError("Choose an action")
    if not (viewer.can_update or viewer.can_withdraw):
        raise ValueError("You do not have permission to change students in bulk")
    if action == "set_field" and (not value or value[0] not in bulk.SETTABLE):
        raise ValueError(f"Only {', '.join(bulk.SETTABLE)} can be set in bulk")


def preview_actions(conn, viewer, ids, action, value=None) -> list[dict]:
    """What a bulk action would change for each chosen student, from their
    current record. Writes nothing."""
    from education_system.systems.university.application.students import bulk_actions as bulk
    _check_preview(viewer, action, value, bulk)
    out = []
    for sid in [str(i).strip() for i in ids if str(i).strip()][:bulk.MAX_STUDENTS]:
        record = _record(conn, sid)
        if record is None:
            out.append({"student_id": sid, "name": "(no such student)", "now": "",
                        "after": "", "change": "refused"})
            continue
        now, after = _now_and_after(conn, sid, record, action, value)
        change = "no change" if str(now or "") == str(after or "") else "will change"
        if action == "email" and not record["email_address"]:
            change = "refused"
        out.append({"student_id": sid,
                    "name": f"{record['first_name'] or ''} {record['last_name'] or ''}".strip(),
                    "now": now or "", "after": after or "", "change": change})
    return out


# ── undo the last operation ─────────────────────────────────────────────


def last_undoable(conn, viewer) -> dict | None:
    """The newest finished job ``viewer`` started that can still be undone."""
    from education_system.systems.university.application.batch import jobs as batch_jobs
    _ensure(conn)
    for (job_id,) in conn.execute("SELECT id FROM batch_jobs WHERE actor = ? AND status = "
                                  "'done' ORDER BY id DESC LIMIT 20", (viewer.username,)):
        try:
            j = batch_jobs._undoable(conn, job_id, viewer)
        except ValueError:
            continue
        if conn.execute("SELECT 1 FROM batch_job_rows WHERE job_id = ? AND undo_json IS NOT "
                        "NULL", (job_id,)).fetchone():
            return j
    return None


# ── history: jobs and exports ───────────────────────────────────────────

HISTORY_FILTERS = ("All", "Imports", "Updates", "Exports")


def history(conn, shown="All", days=None) -> list[dict]:
    """Jobs (imports and updates) and exports, newest first, in the old
    History columns."""
    _ensure(conn)
    out = []
    if shown in ("All", "Imports", "Updates"):
        for j in batch_reports.history(conn, days=days):
            update = j["shown_kind"] == "actions" or (j["shown_kind"] == "students"
                                                     and j["mode"] in ("update", "both"))
            if shown == "Imports" and update or shown == "Updates" and not update:
                continue
            out.append({"key": f"job:{j['id']}", "when": j["started_at"],
                        "operation": f"{'Update' if update else 'Import'} - {j['shown_kind']}"
                                     f" (job #{j['id']}, {j['status']})",
                        "records": j["total"], "success": j["succeeded"], "errors": j["failed"],
                        "by": j["actor"], "detail": f"{j['source'] or ''} {j['reason'] or ''}"
                        .strip()})
    if shown in ("All", "Exports") and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'student_search_audit'").fetchone():
        sql = ("SELECT id, at, actor, result_count, detail FROM student_search_audit WHERE "
               "action = 'export'")
        args: list = []
        if days:
            sql += " AND at >= datetime('now', ?)"
            args.append(f"-{int(days)} days")
        for aid, at, actor, count, detail in conn.execute(sql, args):
            out.append({"key": f"export:{aid}", "when": at, "operation": "Export - students",
                        "records": count or 0, "success": count or 0, "errors": 0,
                        "by": actor, "detail": detail or ""})
    out.sort(key=lambda r: str(r["when"] or ""), reverse=True)
    return out


def export_history_rows(rows, path) -> int:
    import csv
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["when", "operation", "records", "success",
                                                    "errors", "by", "detail"],
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# ── telling someone a job finished ──────────────────────────────────────


def job_notice_emails(conn, job_id) -> list[tuple]:
    """``(address, subject, body)`` for each ``notify_addresses`` entry about
    job ``job_id`` (send after commit). Counts and the reason only, never
    the rows' personal data."""
    addresses = [a.strip() for a in setting(conn, "notify_addresses").split(",") if a.strip()]
    if not addresses or not job_id:
        return []
    row = conn.execute("SELECT kind, mode, actor, reason, source, status, total, succeeded, "
                       "skipped, failed, started_at, finished_at FROM batch_jobs WHERE id = ?",
                       (job_id,)).fetchone()
    if not row:
        return []
    (kind, mode, actor, reason, source, status, total, ok, skipped, failed, started,
     finished) = row
    subject = f"Batch job #{job_id} ({kind}) finished: {ok} done, {failed} failed"
    body = (f"Batch job #{job_id}\n\nKind: {kind}{f' ({mode})' if mode else ''}\n"
            f"Started by: {actor}\nReason: {reason or '-'}\nSource: {source or '-'}\n"
            f"Status: {status}\nStarted: {started}\nFinished: {finished or '-'}\n\n"
            f"Rows: {total}\nDone: {ok}\nSkipped: {skipped}\nFailed: {failed}\n\n"
            "Details, errors and undo are in Batch Operations, History.")
    return [(address, subject, body) for address in addresses]
