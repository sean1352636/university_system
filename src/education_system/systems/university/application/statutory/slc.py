"""Student Loans Company: attendance confirmation per census point and
change-of-circumstance notices.

* **Census points** are the academic calendar's ``census_slc`` key dates
  (``application/academic_calendar``); there is no separate SLC calendar.
* **Worklist** - for a census point, every student registered at that date
  with a suggested decision on the same rules as the attendance office's
  per-term funding confirmation (``application/attendance/engagement``):
  withdrawn record -> withdrawn; open engagement case at formal warning or
  beyond -> held; registers taken but no attendance in the
  ``window_days`` before the census -> held; otherwise confirmed.
* **Decisions** - confirm / hold / not attending / withdrawn per student,
  kept in ``slc_census_confirmations`` (a hold needs a reason).
* **Changes of circumstance** - withdrawals, interruptions, suspensions,
  deferrals, returns, transfers, mode changes and repeat years from
  ``student_lifecycle_history`` become ``slc_change_notifications``.
* **Export** - decided confirmations (not holds) and pending notices are
  written as CSV into the ``slc`` connector's batch folder for staff to
  upload through the SLC's provider portal. Nothing is sent from here.

The SLC customer reference number (CRN / SSN) is not held in this system,
so the file identifies students by our student id, name, date of birth and
programme, which is what the portal matches on when staff upload it.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from education_system.systems.university.application import connectors
from education_system.systems.university.application.attendance import registers
from education_system.systems.university.application.statutory import access as sa

CONNECTOR = "slc"
STATUSES = ("confirmed", "held", "not_attending", "withdrawn")
CHANGE_ACTIONS = {
    "withdraw": "Withdrawal", "interrupt": "Interruption (suspension of study)",
    "suspend": "Suspension", "defer": "Deferral", "resume": "Return from interruption",
    "reinstate": "Reinstatement", "programme_transfer": "Change of course",
    "mode_change": "Change of mode of study", "repeat_year": "Repeat year",
}
_STAGES = ("tutor_contact", "formal_warning", "final_warning", "withdrawal_recommended",
           "withdrawn")


def census_points(current, year_code=None) -> list[dict]:
    sa.officer(current)
    with sa.session() as conn:
        if not sa.has_table(conn, "calendar_key_dates"):
            return []
        sql = ("SELECT key_date_id, year_code, title, start_date FROM calendar_key_dates "
               "WHERE kind = 'census_slc'")
        params: tuple = ()
        if year_code:
            sql += " AND year_code = ?"
            params = (year_code,)
        return sa.dicts(conn.execute(sql + " ORDER BY start_date", params))


def _census(conn, census_date) -> dict:
    day = sa.iso_date(census_date, "Census date")
    row = sa.one(conn, "SELECT year_code, title FROM calendar_key_dates WHERE kind = 'census_slc' "
                 "AND substr(start_date, 1, 10) = ?", (day,)) \
        if sa.has_table(conn, "calendar_key_dates") else None
    if not row:
        raise ValueError(f"{day} is not an SLC census date in the academic calendar "
                         "(add a 'census_slc' key date first)")
    return {"date": day, **row}


def _registered(conn, day) -> dict[str, dict]:
    """Students registered on a programme at *day* (or Active with modules
    when no programme registration exists)."""
    out: dict[str, dict] = {}
    if sa.has_table(conn, "programme_registrations"):
        for row in sa.dicts(conn.execute(
                "SELECT student_id, programme_code, status FROM programme_registrations "
                "WHERE substr(effective_from, 1, 10) <= ? AND (effective_to IS NULL OR "
                "substr(effective_to, 1, 10) >= ?) AND status NOT IN ('registration_pending', "
                "'cancelled')", (day, day))):
            out.setdefault(row["student_id"], row)
    if sa.has_table(conn, "student_modules"):
        for sid, course in conn.execute(
                "SELECT DISTINCT s.student_id, s.course FROM students s JOIN student_modules sm "
                "ON sm.student_id = s.student_id WHERE LOWER(COALESCE(s.status, '')) = 'active'"):
            out.setdefault(sid, {"student_id": sid, "programme_code": course,
                                 "status": "active"})
    return out


def _suggest(status, stage, summary) -> tuple[str, str]:
    if str(status or "").lower() in ("withdrawn", "inactive"):
        return "withdrawn", "student record withdrawn"
    if stage in _STAGES and _STAGES.index(stage) >= _STAGES.index("formal_warning"):
        return "held", f"engagement case at {stage.replace('_', ' ')}"
    if summary["registered"] and not (summary["present"] + summary["late"]):
        return "held", "no recorded attendance before the census date"
    return "confirmed", ""


def worklist(current, census_date, window_days=28) -> dict:
    """The census point and one row per registered student with the
    suggested decision and any decision already recorded."""
    sa.officer(current)
    with sa.session() as conn:
        census = _census(conn, census_date)
        day = date.fromisoformat(census["date"])
        start = day - timedelta(days=int(window_days))
        stages = {} if not sa.has_table(conn, "engagement_cases") else dict(conn.execute(
            "SELECT student_id, stage FROM engagement_cases WHERE status = 'open'").fetchall())
        decided = {r["student_id"]: r for r in sa.dicts(conn.execute(
            "SELECT * FROM slc_census_confirmations WHERE census_date = ?", (census["date"],)))}
        students = {r["student_id"]: r for r in sa.dicts(conn.execute(
            "SELECT student_id, first_name, last_name, status FROM students"))}
        rows = []
        for sid, reg in sorted(_registered(conn, census["date"]).items()):
            person = students.get(sid, {})
            summary = registers.student_summary(conn, sid, start, day)
            suggested, why = _suggest(person.get("status"), stages.get(sid), summary)
            done = decided.get(sid) or {}
            rows.append({"student_id": sid, "name": sa.student_name(person),
                         "programme": reg.get("programme_code"),
                         "attendance_pct": summary["attendance_pct"], "suggested": suggested,
                         "why": why, "decision": done.get("status"), "reason": done.get("reason"),
                         "batch_id": done.get("batch_id")})
    return {"census": census, "rows": rows}


def decide(current, census_date, decisions: dict) -> int:
    """Record ``{student_id: status}`` or ``{student_id: (status, reason)}``.
    A decision already exported cannot be changed."""
    who = sa.officer(current)
    with sa.session() as conn:
        census = _census(conn, census_date)
        for sid, value in decisions.items():
            status, reason = value if isinstance(value, (tuple, list)) else (value, None)
            if status not in STATUSES:
                raise ValueError(f"Decision must be one of {', '.join(STATUSES)}")
            if status == "held" and not str(reason or "").strip():
                raise ValueError(f"Say why {sid} is held")
            if conn.execute("SELECT 1 FROM slc_census_confirmations WHERE census_date = ? AND "
                            "student_id = ? AND batch_id IS NOT NULL",
                            (census["date"], str(sid))).fetchone():
                raise ValueError(f"{sid}'s decision has already been exported")
            conn.execute(
                "INSERT INTO slc_census_confirmations (census_date, year_code, census_title, "
                "student_id, status, reason, decided_by, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(census_date, student_id) DO UPDATE SET status = excluded.status, "
                "reason = excluded.reason, decided_by = excluded.decided_by, "
                "decided_at = excluded.decided_at",
                (census["date"], census.get("year_code"), census.get("title"), str(sid), status,
                 reason, who.username, sa.now()))
            sa.audit(conn, who, "slc", "census_confirmation", f"{census['date']}:{sid}", status,
                     {"reason": reason})
    return len(decisions)


# ── changes of circumstance ─────────────────────────────────────────────


def _change_details(row) -> str:
    parts = []
    if row.get("new_programme"):
        parts.append(f"course {row.get('old_programme') or '?'} -> {row['new_programme']}")
    if row.get("new_mode"):
        parts.append(f"mode {row.get('old_mode') or '?'} -> {row['new_mode']}")
    if row.get("expected_return_date"):
        parts.append(f"expected return {row['expected_return_date']}")
    if row.get("reason"):
        parts.append(f"reason: {row['reason']}")
    return "; ".join(parts)


def sync_changes(current) -> int:
    """Raise a notice for every lifecycle change the SLC needs to hear about
    that has not got one yet. Returns how many were added."""
    who = sa.officer(current)
    added = 0
    with sa.session() as conn:
        if not sa.has_table(conn, "student_lifecycle_history"):
            return 0
        for row in sa.dicts(conn.execute(
                "SELECT h.* FROM student_lifecycle_history h LEFT JOIN slc_change_notifications n "
                "ON n.history_id = h.history_id WHERE n.history_id IS NULL "
                "ORDER BY h.history_id")):
            action = str(row["action"])
            label = CHANGE_ACTIONS.get(action.removeprefix("reverse:"))
            if not label:
                continue
            if action.startswith("reverse:"):
                label = f"Reversal of {label.lower()}"
            conn.execute(
                "INSERT INTO slc_change_notifications (history_id, student_id, change_type, "
                "effective_date, from_status, to_status, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["history_id"], row["student_id"], label, row["effective_date"],
                 row.get("from_status"), row.get("to_status"), _change_details(row)))
            added += 1
        if added:
            sa.audit(conn, who, "slc", "change_notifications", None, "synced", {"added": added})
    return added


def changes(current, status=None) -> list[dict]:
    sa.officer(current)
    with sa.session() as conn:
        sql = ("SELECT n.*, s.first_name, s.last_name FROM slc_change_notifications n "
               "LEFT JOIN students s ON s.student_id = n.student_id")
        if status:
            return sa.dicts(conn.execute(sql + " WHERE n.status = ? ORDER BY n.effective_date",
                                         (status,)))
        return sa.dicts(conn.execute(sql + " ORDER BY n.effective_date DESC"))


def set_change_status(current, notification_id, status, slc_reference=None) -> None:
    """Mark a notice acknowledged by the SLC (with its reference) or not
    required (e.g. the student has no SLC funding)."""
    who = sa.officer(current)
    if status not in ("acknowledged", "not_required", "pending"):
        raise ValueError("Status must be acknowledged, not_required or pending")
    if status == "acknowledged" and not str(slc_reference or "").strip():
        raise ValueError("Enter the SLC reference for the acknowledgement")
    with sa.session() as conn:
        if not conn.execute(
                "UPDATE slc_change_notifications SET status = ?, slc_reference = COALESCE(?, "
                "slc_reference), updated_by = ?, updated_at = ? WHERE notification_id = ?",
                (status, slc_reference, who.username, sa.now(), notification_id)).rowcount:
            raise ValueError(f"No notice {notification_id}")
        sa.audit(conn, who, "slc", "change_notification", notification_id, status,
                 {"slc_reference": slc_reference})


# ── export ──────────────────────────────────────────────────────────────

_HEADER = ["RecordType", "ProviderStudentID", "Surname", "Forenames", "DateOfBirth",
           "CourseCode", "CensusDate", "AttendanceStatus", "ChangeType", "EffectiveDate",
           "Details"]
_STATUS_OUT = {"confirmed": "Attending", "not_attending": "Not attending",
               "withdrawn": "Withdrawn"}


def _person(conn, sid) -> dict:
    return sa.one(conn, "SELECT last_name, first_name, dob, course FROM students "
                  "WHERE student_id = ?", (sid,)) or {}


def export(current, census_date=None, include_changes=True) -> dict:
    """Write the SLC batch: decided confirmations for *census_date* (holds
    stay back) and, optionally, every pending change notice. Returns the
    file path and counts; nothing new to send -> no file."""
    who = sa.officer(current)
    batch_id = f"SLC-{sa.stamp()}"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADER)
    confirmed_ids: list[int] = []
    notices = 0
    with sa.session() as conn:
        if census_date:
            census = _census(conn, census_date)
            for row in sa.dicts(conn.execute(
                    "SELECT * FROM slc_census_confirmations WHERE census_date = ? AND "
                    "batch_id IS NULL AND status != 'held' ORDER BY student_id",
                    (census["date"],))):
                p = _person(conn, row["student_id"])
                writer.writerow(["ATTENDANCE", row["student_id"], p.get("last_name"),
                                 p.get("first_name"), p.get("dob"), p.get("course"),
                                 census["date"], _STATUS_OUT[row["status"]], "", "", ""])
                confirmed_ids.append(row["confirmation_id"])
        pending = sa.dicts(conn.execute(
            "SELECT * FROM slc_change_notifications WHERE status = 'pending' ORDER BY "
            "effective_date")) if include_changes else []
        for row in pending:
            p = _person(conn, row["student_id"])
            writer.writerow(["CHANGE", row["student_id"], p.get("last_name"), p.get("first_name"),
                             p.get("dob"), p.get("course"), "", "", row["change_type"],
                             row["effective_date"], row.get("details") or ""])
            notices += 1
    confirmations = len(confirmed_ids)
    if not (confirmations or notices):
        return {"path": None, "confirmations": 0, "changes": 0, "batch_id": None}
    path = connectors.write_batch(CONNECTOR, batch_id, f"{batch_id}.csv", buf.getvalue())
    with sa.session() as conn:
        for cid in confirmed_ids:
            conn.execute("UPDATE slc_census_confirmations SET batch_id = ? WHERE "
                         "confirmation_id = ?", (batch_id, cid))
        for row in pending:
            conn.execute("UPDATE slc_change_notifications SET status = 'exported', batch_id = ?, "
                         "updated_by = ?, updated_at = ? WHERE notification_id = ?",
                         (batch_id, who.username, sa.now(), row["notification_id"]))
        sa.audit(conn, who, "slc", "batch", batch_id, "file_written",
                 {"path": path, "confirmations": confirmations, "changes": notices})
    return {"path": path, "confirmations": confirmations, "changes": notices,
            "batch_id": batch_id}


__all__ = ["CHANGE_ACTIONS", "CONNECTOR", "STATUSES", "census_points", "changes", "decide",
           "export", "set_change_status", "sync_changes", "worklist"]
