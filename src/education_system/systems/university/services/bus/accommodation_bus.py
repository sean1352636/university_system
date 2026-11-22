"""Medical accommodations → exams, assessments and module staff.

An accommodation the health portal approves (``accommodations``, status
``active`` / ``approved``) has to reach the places that act on it. It
previously stopped at the health portal: exams read ``exam_accommodations``
/ ``student_accommodations`` and assessments read ``extension_requests``,
and nothing wrote them.

:func:`reconcile` makes those tables agree with ``accommodations``. It is
idempotent and diff-based, so every writer (GUI, CLI, accessibility
service, imports, bulk edits, deletes) can call it after committing, and
the daily health job calls it to catch expiries:

* expired accommodations (``end_date`` / ``expiration_date`` past) become
  ``expired``;
* each active one gets, as its type and description imply, an
  ``exam_accommodations`` row (extra time per hour, separate room,
  reader/scribe, assistive technology; ``exam_id`` NULL = every exam), a
  ``student_accommodations`` row, and approved extensions on the student's
  upcoming assignments for extension-type accommodations;
* anything derived from an accommodation that is no longer active (withdrawn,
  rejected, expired, edited away or deleted) is withdrawn: exam rows to
  ``withdrawn``, register rows inactive, not-yet-due extensions
  ``withdrawn``;
* module staff of the student's enrolled modules are told — only with the
  student's ``share_with_accommodation`` consent, through the outbox, with a
  need-to-know summary (the adjustments, never the condition or the
  description) — and told again when it stops applying or consent is
  withdrawn.

Derived rows carry ``source_accommodation_id``
(``pastoral/infrastructure/health/accommodation_schema``).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

ACTIVE = ("active", "approved")
EXTENSION_HORIZON_DAYS = 365
DEFAULT_EXTRA_PERCENT = 25
DEFAULT_EXTENSION_DAYS = 7


def _schema(conn) -> None:
    from education_system.systems.university.domains.health.infrastructure.health import (
        accommodation_schema,
    )
    accommodation_schema.apply_to_connection(conn)


def _has_table(conn, name) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                             (name,)).fetchone())


def _columns(conn, table) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


# ---------------------------------------------------------------- the rules

def adjustments(accommodation_type, description="") -> dict:
    """What an accommodation means in practice, from its type and wording:
    ``extra_percent``, ``separate_room``, ``reader_scribe``,
    ``assistive_technology``, ``extension_days``, ``register_type`` (the
    ``student_accommodations`` category) and a plain ``summary``."""
    kind = str(accommodation_type or "").lower()
    text = f"{kind} {str(description or '').lower()}"
    out = {"extra_percent": 0, "separate_room": False, "reader_scribe": False,
           "assistive_technology": None, "extension_days": 0, "register_type": "other"}
    if any(w in text for w in ("extended time", "extra time", "additional time")):
        found = re.search(r"(\d{1,3})\s*%", text)
        out["extra_percent"] = int(found.group(1)) if found else DEFAULT_EXTRA_PERCENT
        out["register_type"] = "extended_time"
    if any(w in text for w in ("separate room", "quiet room", "smaller room", "rest break")):
        out["separate_room"] = True
    if any(w in text for w in ("reader", "scribe", "amanuensis")) and "screen reader" not in text:
        out["reader_scribe"] = True
    if "screen reader" in text:
        out["assistive_technology"] = "Screen reader"
        out["register_type"] = (out["register_type"] if out["extra_percent"]
                                else "screen_reader")
    elif any(w in text for w in ("assistive technology", "laptop", "speech-to-text",
                                 "dictation", "software")):
        out["assistive_technology"] = str(accommodation_type or "Assistive technology")
    if out["register_type"] == "other":
        if "large" in text and ("print" in text or "text" in text):
            out["register_type"] = "large_text"
        elif any(w in text for w in ("alternate format", "alternative format", "braille")):
            out["register_type"] = "alt_format"
    # An extension: deadline wording, or extended time that the type itself
    # says covers assignments ("Additional time for assignments or exams").
    if (any(w in text for w in ("extension", "deadline", "extra days"))
            or (out["extra_percent"] and "assignment" in text)
            or kind in ("extended time", "extended deadline", "extended deadlines")):
        found = re.search(r"(\d{1,2})\s*(?:working\s+)?days?", text)
        out["extension_days"] = int(found.group(1)) if found else DEFAULT_EXTENSION_DAYS
    parts = []
    if out["extra_percent"]:
        parts.append(f"{out['extra_percent']}% extra time in timed assessments")
    if out["separate_room"]:
        parts.append("a separate or quiet room")
    if out["reader_scribe"]:
        parts.append("a reader/scribe")
    if out["assistive_technology"]:
        parts.append(f"assistive technology ({out['assistive_technology']})")
    if out["extension_days"]:
        parts.append(f"{out['extension_days']}-day extension on coursework deadlines")
    if out["register_type"] in ("alt_format", "large_text"):
        parts.append("materials in an alternative format" if out["register_type"] == "alt_format"
                     else "large-print materials")
    out["summary"] = "; ".join(parts) or str(accommodation_type or "Adjustment")
    return out


def _end(row) -> str | None:
    return (row.get("end_date") or row.get("expiration_date") or None)


def _is_active(row, today) -> bool:
    if str(row.get("status") or "").lower() not in ACTIVE:
        return False
    start, end = row.get("start_date"), _end(row)
    if start and str(start)[:10] > today:
        return False
    return not (end and str(end)[:10] < today)


# ---------------------------------------------------------------- reconcile

def reconcile(conn=None, *, send=True) -> dict:
    """Bring the derived tables and staff notices in line with
    ``accommodations``. Commits its own connection (or the caller's, when
    ``conn`` is given and not in a transaction the caller still owns —
    pass ``send=False`` and send the returned ``emails`` yourself then)."""
    own = conn is None
    conn = conn or get_connection(row_factory=False)
    try:
        if not _has_table(conn, "accommodations"):
            return {"active": 0, "emails": []}
        _schema(conn)
        today = date.today().isoformat()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cols = _columns(conn, "accommodations")
        end_expr = ("COALESCE(NULLIF(end_date, ''), NULLIF(expiration_date, ''))"
                    if "expiration_date" in cols else "NULLIF(end_date, '')")
        expired = conn.execute(
            f"UPDATE accommodations SET status = 'expired', updated_at = ? "  # nosec B608
            f"WHERE LOWER(COALESCE(status, '')) IN ('active', 'approved') "
            f"AND {end_expr} IS NOT NULL AND substr({end_expr}, 1, 10) < ?",
            (now, today)).rowcount
        names = [c for c in ("id", "student_id", "accommodation_type", "description",
                             "start_date", "end_date", "expiration_date", "status",
                             "request_id")
                 if c in cols]
        rows = [dict(zip(names, r)) for r in conn.execute(
            f"SELECT {', '.join(names)} FROM accommodations")]  # nosec B608
        active = {r["id"]: r for r in rows if _is_active(r, today)}
        counts = {"expired": expired, "active": len(active), "exam": 0, "register": 0,
                  "extensions": 0, "withdrawn": 0}
        for acc_id, row in active.items():
            adj = adjustments(row.get("accommodation_type"), row.get("description"))
            counts["exam"] += _exam_row(conn, acc_id, row, adj, now)
            counts["register"] += _register_row(conn, acc_id, row, adj, now)
            counts["extensions"] += _extensions(conn, acc_id, row, adj, today, now)
        counts["withdrawn"] = _withdraw_others(conn, set(active), today, now)
        counts["requests"] = _sync_requests(conn, rows, active)
        emails = _notices(conn, active, rows, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if own:
            conn.close()
    counts["emails"] = emails
    if send:
        _send(emails)
    return counts


def _exam_row(conn, acc_id, row, adj, now) -> int:
    if not _has_table(conn, "exam_accommodations"):
        return 0
    if not (adj["extra_percent"] or adj["separate_room"] or adj["reader_scribe"]
            or adj["assistive_technology"]):
        conn.execute("UPDATE exam_accommodations SET status = 'withdrawn' "
                     "WHERE source_accommodation_id = ? AND status = 'active'", (acc_id,))
        return 0
    minutes = round(adj["extra_percent"] * 60 / 100) if adj["extra_percent"] else None
    note = (f"From medical accommodation #{acc_id}: {adj['summary']}"
            + (" (extended_time = minutes per hour)" if minutes else ""))
    values = (str(row["student_id"]), minutes, int(adj["separate_room"]),
              adj["assistive_technology"], int(adj["reader_scribe"]), note)
    found = conn.execute("SELECT accommodation_id FROM exam_accommodations "
                         "WHERE source_accommodation_id = ?", (acc_id,)).fetchone()
    if found:
        conn.execute("UPDATE exam_accommodations SET student_id = ?, extended_time = ?, "
                     "separate_room = ?, assistive_technology = ?, reader_scribe = ?, "
                     "notes = ?, status = 'active' WHERE accommodation_id = ?",
                     values + (found[0],))
        return 0
    conn.execute("INSERT INTO exam_accommodations (student_id, exam_id, extended_time, "
                 "separate_room, assistive_technology, reader_scribe, notes, status, "
                 "created_at, source_accommodation_id) VALUES (?, NULL, ?, ?, ?, ?, ?, "
                 "'active', ?, ?)", values + (now, acc_id))
    return 1


def _register_row(conn, acc_id, row, adj, now) -> int:
    if not _has_table(conn, "student_accommodations"):
        return 0
    multiplier = 1 + adj["extra_percent"] / 100 if adj["extra_percent"] else 1.0
    cols = _columns(conn, "student_accommodations")
    expiry = _end(row)
    found = conn.execute("SELECT id FROM student_accommodations "
                         "WHERE source_accommodation_id = ?", (acc_id,)).fetchone()
    details = f"Medical accommodation #{acc_id}: {adj['summary']}"
    if found:
        sets = ["student_id = ?", "accommodation_type = ?", "details = ?",
                "time_multiplier = ?", "is_active = 1", "expires_at = ?"]
        args = [str(row["student_id"]), adj["register_type"], details, multiplier, expiry]
        if "updated_at" in cols:
            sets.append("updated_at = ?")
            args.append(now)
        conn.execute(f"UPDATE student_accommodations SET {', '.join(sets)} "  # nosec B608
                     "WHERE id = ?", (*args, found[0]))
        return 0
    conn.execute("INSERT INTO student_accommodations (student_id, accommodation_type, details, "
                 "time_multiplier, is_active, approved_by, created_at, expires_at, "
                 "source_accommodation_id) VALUES (?, ?, ?, ?, 1, 'health portal', ?, ?, ?)",
                 (str(row["student_id"]), adj["register_type"], details, multiplier, now,
                  expiry, acc_id))
    return 1


def _extensions(conn, acc_id, row, adj, today, now) -> int:
    if not adj["extension_days"] or not (_has_table(conn, "extension_requests")
                                         and _has_table(conn, "assignments")
                                         and _has_table(conn, "student_modules")):
        return 0
    start = max(str(row.get("start_date") or today)[:10], today)
    until = str(_end(row) or (date.today() + timedelta(days=EXTENSION_HORIZON_DAYS))
                .isoformat())[:10]
    made = 0
    for assignment_id, due in conn.execute(
            "SELECT a.id, a.due_date FROM assignments a JOIN student_modules sm "
            "ON sm.module_code = a.module_code AND sm.student_id = ? "
            "AND COALESCE(sm.status, 'Enrolled') = 'Enrolled' "
            "WHERE COALESCE(a.is_active, 1) = 1 AND COALESCE(a.archived, 0) = 0 "
            "AND substr(a.due_date, 1, 10) BETWEEN ? AND ?",
            (str(row["student_id"]), start, until)).fetchall():
        if conn.execute("SELECT 1 FROM extension_requests WHERE assignment_id = ? "
                        "AND student_id = ? AND LOWER(COALESCE(status, '')) IN "
                        "('pending', 'approved')", (assignment_id, str(row["student_id"]))
                        ).fetchone():
            continue
        try:
            due_dt = datetime.fromisoformat(str(due).replace("Z", ""))
        except ValueError:
            continue
        new_due = (due_dt + timedelta(days=adj["extension_days"])).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO extension_requests (assignment_id, student_id, requested_date, "
                     "new_due_date, reason, status, reviewed_date, approved_extension_days, "
                     "reviewer_notes, source_accommodation_id) VALUES (?, ?, ?, ?, ?, "
                     "'approved', ?, ?, ?, ?)",
                     (assignment_id, str(row["student_id"]), now, new_due,
                      f"Approved medical accommodation #{acc_id}", now,
                      adj["extension_days"], "Granted automatically from the health portal",
                      acc_id))
        made += 1
    return made


def _withdraw_others(conn, active_ids, today, now) -> int:
    """Withdraw what was derived from accommodations no longer active."""
    keep = sorted(active_ids) or [-1]
    marks = ",".join("?" * len(keep))
    total = 0
    if _has_table(conn, "exam_accommodations"):
        total += conn.execute(
            f"UPDATE exam_accommodations SET status = 'withdrawn' "  # nosec B608
            f"WHERE source_accommodation_id IS NOT NULL AND status = 'active' "
            f"AND source_accommodation_id NOT IN ({marks})", keep).rowcount
    if _has_table(conn, "student_accommodations"):
        total += conn.execute(
            f"UPDATE student_accommodations SET is_active = 0 "  # nosec B608
            f"WHERE source_accommodation_id IS NOT NULL AND is_active = 1 "
            f"AND source_accommodation_id NOT IN ({marks})", keep).rowcount
    if _has_table(conn, "extension_requests") and _has_table(conn, "assignments"):
        total += conn.execute(
            f"UPDATE extension_requests SET status = 'withdrawn', reviewer_notes = "  # nosec B608
            f"'Withdrawn: the medical accommodation no longer applies', reviewed_date = ? "
            f"WHERE source_accommodation_id IS NOT NULL AND status = 'approved' "
            f"AND source_accommodation_id NOT IN ({marks}) AND assignment_id IN "
            f"(SELECT id FROM assignments WHERE substr(due_date, 1, 10) >= ?)",
            (now, *keep, today)).rowcount
    return total


def _sync_requests(conn, rows, active) -> int:
    """A request made through accessibility services
    (``accommodation_requests``) follows the decision on its accommodation,
    whichever screen made it."""
    if not _has_table(conn, "accommodation_requests"):
        return 0
    changed = 0
    for row in rows:
        request_id = row.get("request_id")
        if not request_id:
            continue
        status = str(row.get("status") or "").lower()
        if row["id"] in active or status in ACTIVE:
            target = "Approved"
        elif status in ("rejected", "denied"):
            target = "Denied"
        else:
            continue
        changed += conn.execute(
            "UPDATE accommodation_requests SET status = ?, reviewed_date = COALESCE("
            "reviewed_date, CURRENT_TIMESTAMP) WHERE request_id = ? AND COALESCE(status, '') "
            "NOT IN (?, 'Active')", (target, request_id, target)).rowcount
    return changed


# ---------------------------------------------------------------- staff notices

def module_staff_emails(conn, student_id) -> list[str]:
    """E-mails of the staff teaching the student's enrolled modules."""
    found = set()
    if _has_table(conn, "module_staff") and _has_table(conn, "student_modules"):
        found.update(r[0] for r in conn.execute(
            "SELECT DISTINCT u.email FROM student_modules sm JOIN module_staff ms "
            "ON ms.module_code = sm.module_code JOIN users u ON u.username = ms.username "
            "WHERE sm.student_id = ? AND COALESCE(sm.status, 'Enrolled') = 'Enrolled' "
            "AND COALESCE(u.email, '') <> ''", (str(student_id),)))
    if (_has_table(conn, "modules") and _has_table(conn, "instructors")
            and "instructor_id" in _columns(conn, "modules")):
        found.update(r[0] for r in conn.execute(
            "SELECT DISTINCT i.email FROM student_modules sm JOIN modules m "
            "ON m.module_code = sm.module_code JOIN instructors i ON i.id = m.instructor_id "
            "WHERE sm.student_id = ? AND COALESCE(sm.status, 'Enrolled') = 'Enrolled' "
            "AND COALESCE(i.email, '') <> ''", (str(student_id),)))
    return sorted(found)


def _consented(conn, student_id) -> bool:
    try:
        from education_system.systems.university.domains.health.application.health import (
            consent,
        )
        return consent.has_consent(student_id, "share_with_accommodation", conn=conn)
    except Exception:
        logger.debug("Consent check failed for %s; not shared", student_id, exc_info=True)
        return False


def _student_label(conn, student_id) -> str:
    try:
        row = conn.execute("SELECT first_name, last_name FROM students WHERE student_id = ?",
                           (str(student_id),)).fetchone()
    except Exception:
        row = None
    name = " ".join(p for p in (row or ()) if p)
    return f"{name} ({student_id})" if name else f"student {student_id}"


def _notices(conn, active, rows, now) -> list[tuple]:
    emails = []
    shared = {}
    for acc_id, recipient, state in conn.execute(
            "SELECT accommodation_id, recipient, state FROM accommodation_shares"):
        shared[(acc_id, recipient)] = state
    by_id = {r["id"]: r for r in rows}

    def mark(acc_id, recipient, state):
        conn.execute("INSERT INTO accommodation_shares (accommodation_id, recipient, state, "
                     "changed_at) VALUES (?, ?, ?, ?) ON CONFLICT (accommodation_id, recipient) "
                     "DO UPDATE SET state = excluded.state, changed_at = excluded.changed_at",
                     (acc_id, recipient, state, now))

    consent_cache = {}
    for acc_id, row in active.items():
        sid = row["student_id"]
        if sid not in consent_cache:
            consent_cache[sid] = _consented(conn, sid)
        if not consent_cache[sid]:
            continue
        adj = adjustments(row.get("accommodation_type"), row.get("description"))
        who = _student_label(conn, sid)
        for recipient in module_staff_emails(conn, sid):
            if shared.get((acc_id, recipient)) == "shared":
                continue
            emails.append((recipient, f"Reasonable adjustment for {who}",
                           f"{who}, who is on a module you teach, has an approved reasonable "
                           f"adjustment from {row.get('start_date') or 'now'}"
                           f"{' to ' + str(_end(row)) if _end(row) else ''}:\n\n"
                           f"  {adj['summary']}\n\n"
                           "The student has agreed to this being shared with their module "
                           "staff. Please apply it; the details of any condition are held by "
                           "the health team only and should not be asked for. Exam and "
                           "coursework systems have been updated."))
            mark(acc_id, recipient, "shared")
    # No longer applies (withdrawn/expired/deleted) or consent withdrawn.
    for (acc_id, recipient), state in shared.items():
        if state != "shared":
            continue
        row = by_id.get(acc_id)
        if row and acc_id in active:
            sid = row["student_id"]
            if sid not in consent_cache:
                consent_cache[sid] = _consented(conn, sid)
            if consent_cache[sid]:
                continue
        who = _student_label(conn, row["student_id"]) if row else "a student"
        emails.append((recipient, f"Reasonable adjustment no longer applies — {who}",
                       f"The reasonable adjustment previously shared with you for {who} "
                       "no longer applies (or the student has withdrawn consent to share it). "
                       "Please stop applying it and remove any local copy of the notice."))
        mark(acc_id, recipient, "withdrawn")
    return emails


def _send(emails) -> None:
    if not emails:
        return
    try:
        from education_system.systems.university.infrastructure.email.email_service.core import (
            send_email,
        )
    except Exception:
        logger.debug("E-mail unavailable; %d accommodation notices not sent", len(emails),
                     exc_info=True)
        return
    for address, subject, body in emails:
        try:
            send_email(address, subject, body)
        except Exception:
            logger.debug("Accommodation notice to %s failed", address, exc_info=True)


def after_change() -> None:
    """For writers: reconcile after committing; never breaks the caller."""
    try:
        reconcile()
    except Exception:
        logger.exception("Medical accommodations could not be propagated")


# ---------------------------------------------------------------- writers

def exam_arrangement_text(*, extra_percent=0, separate_room=False, reader=False, scribe=False,
                          assistive_technology="", rest_breaks=False, other="") -> str:
    """Exam access arrangements in the wording :func:`adjustments` reads,
    so an arrangement recorded elsewhere (a DSA needs assessment, say)
    reaches exams exactly as typed."""
    parts = []
    if int(extra_percent or 0) > 0:
        parts.append(f"{int(extra_percent)}% extra time in exams")
    if separate_room:
        parts.append("separate room")
    if rest_breaks:
        parts.append("rest breaks (separate room)")
    if reader:
        parts.append("reader")
    if scribe:
        parts.append("scribe")
    if str(assistive_technology or "").strip():
        parts.append(f"assistive technology: {str(assistive_technology).strip()}")
    if str(other or "").strip():
        parts.append(str(other).strip())
    return "; ".join(parts)


def add_approved(student_id, accommodation_type, description, *, approved_by, start_date=None,
                 end_date=None, notes=None) -> int:
    """Write one approved ``accommodations`` row and reconcile, so exams,
    the register and extensions follow it. Returns its id."""
    accommodation_type = str(accommodation_type or "").strip()
    if not accommodation_type or not str(description or "").strip():
        raise ValueError("An adjustment needs a type and a description.")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start = start_date or date.today().isoformat()
    conn = get_connection(row_factory=False)
    try:
        _schema(conn)
        if not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                            (str(student_id),)).fetchone():
            raise ValueError(f"No student {student_id}.")
        acc_id = conn.execute(
            "INSERT INTO accommodations (student_id, accommodation_type, description, "
            "start_date, end_date, status, approved_by, approval_date, notes, created_at, "
            "updated_at) VALUES (?, ?, ?, ?, ?, 'approved', ?, ?, ?, ?, ?)",
            (str(student_id), accommodation_type, str(description).strip(), start,
             end_date or None, approved_by, now[:10], notes, now, now)).lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    after_change()
    return int(acc_id)


def withdraw(accommodation_id, *, reason, by) -> bool:
    """Withdraw an adjustment (status ``withdrawn`` with the reason in its
    notes); reconcile withdraws what was derived from it."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection(row_factory=False)
    try:
        changed = conn.execute(
            "UPDATE accommodations SET status = 'withdrawn', updated_at = ?, "
            "notes = TRIM(COALESCE(notes, '') || char(10) || ?) WHERE id = ? "
            "AND LOWER(COALESCE(status, '')) NOT IN ('withdrawn', 'expired')",
            (now, f"Withdrawn {now[:10]} by {by}: {reason}", int(accommodation_id))).rowcount
        conn.commit()
    finally:
        conn.close()
    if changed:
        after_change()
    return bool(changed)
