"""Sixth-form alumni — Alumni CRUD, audit trail, deduplication, merge, archiving a student, summary.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any

from .models import (
    Alumnus,
    DEFAULT_DESTINATION,
    DEFAULT_LEAVING_REASON,
    DEFAULT_STATUS,
    DESTINATION_TYPES,
    SECTORS,
    SOFT_DELETE_UNDO_DAYS,
    STATUSES,
    Summary,
    _log_action,
    logger,
)
from .db import (
    ValidationError,
    _connect,
    _row,
    _validate_payload,
    _validate_year,
    init_db,
)


# ── CRUD ──────────────────────────────────────────────────────────

def _original_create_alumnus(payload: dict[str, Any]) -> Alumnus:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni
                   (original_student_id, first_name, last_name,
                    preferred_name, pronouns, gender,
                    dob, leaving_year, leaving_date,
                    leaving_reason, destination_type,
                    destination_detail, current_role, current_employer,
                    current_sector, current_location, country, region,
                    email, phone, address,
                    linkedin, other_social, photo_path, bio,
                    opt_in_contact, status,
                    last_contacted, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["original_student_id"], p["first_name"], p["last_name"],
             p["preferred_name"], p["pronouns"], p["gender"],
             p["dob"], p["leaving_year"],
             p["leaving_date"], p["leaving_reason"],
             p["destination_type"], p["destination_detail"],
             p["current_role"], p["current_employer"],
             p["current_sector"], p["current_location"],
             p["country"], p["region"],
             p["email"], p["phone"],
             p["address"], p["linkedin"], p["other_social"],
             p["photo_path"], p["bio"],
             1 if p["opt_in_contact"] else 0, p["status"],
             p["last_contacted"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_alumnus(new_id)
    assert out is not None
    _log_action("alumnus.create", alumni_id=new_id,
                  name=f"{p['first_name']} {p['last_name']}",
                  leaving_year=p["leaving_year"],
                  destination=p["destination_type"])
    return out


def get_alumnus(alumni_id: int) -> Alumnus | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        return _row(r) if r else None


def get_alumnus_by_original_id(student_id: str) -> Alumnus | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni "
            "WHERE original_student_id = ? "
            "ORDER BY alumni_id DESC LIMIT 1",
            (student_id.strip(),)).fetchone()
        return _row(r) if r else None


def list_alumni(
    *,
    leaving_year: str | None = None,
    destination_type: str | None = None,
    status: str | None = None,
    contactable_only: bool = False,
    search: str | None = None,
    employer: str | None = None,
    university: str | None = None,
    sector: str | None = None,
    country: str | None = None,
    tag: str | None = None,
    has_email: bool | None = None,
    include_deleted: bool = False,
) -> list[Alumnus]:
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if leaving_year:
        clauses.append("leaving_year = ?")
        args.append(_validate_year(leaving_year))
    if destination_type:
        if destination_type not in DESTINATION_TYPES:
            raise ValidationError(
                f"Destination type must be one of: "
                f"{', '.join(DESTINATION_TYPES)}")
        clauses.append("destination_type = ?")
        args.append(destination_type)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if contactable_only:
        clauses.append(
            "opt_in_contact = 1 AND status = 'Active' "
            "AND (email IS NOT NULL OR phone IS NOT NULL)")
    if employer:
        clauses.append(
            "(current_employer LIKE ? OR "
            " alumni_id IN (SELECT alumni_id FROM alumni_career "
            "                WHERE employer LIKE ?))")
        like = f"%{employer.strip()}%"
        args.extend([like, like])
    if university:
        # Either current destination detail or any historical
        # education record points at this institution.
        like = f"%{university.strip()}%"
        clauses.append(
            "((destination_type = 'University' "
            "  AND destination_detail LIKE ?) OR "
            " alumni_id IN (SELECT alumni_id FROM alumni_education "
            "                WHERE institution LIKE ?))")
        args.extend([like, like])
    if sector:
        if sector not in SECTORS:
            raise ValidationError(
                f"Sector must be one of: {', '.join(SECTORS)}")
        clauses.append(
            "(current_sector = ? OR "
            " alumni_id IN (SELECT alumni_id FROM alumni_career "
            "                WHERE sector = ? AND is_current = 1))")
        args.extend([sector, sector])
    if country:
        clauses.append("country = ?")
        args.append(country.strip())
    if tag:
        clauses.append(
            "alumni_id IN (SELECT l.alumni_id FROM alumni_tag_links l "
            "  JOIN alumni_tags t ON t.tag_id = l.tag_id "
            "  WHERE t.name = ? COLLATE NOCASE)")
        args.append(tag.strip())
    if has_email is True:
        clauses.append("email IS NOT NULL AND email != ''")
    elif has_email is False:
        clauses.append("(email IS NULL OR email = '')")
    if search:
        s = f"%{search.strip()}%"
        clauses.append(
            "(first_name LIKE ? OR last_name LIKE ? OR "
            "preferred_name LIKE ? OR email LIKE ? OR "
            "original_student_id LIKE ? OR current_employer LIKE ? "
            "OR destination_detail LIKE ?)")
        args.extend([s, s, s, s, s, s, s])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni {where} "
           "ORDER BY leaving_year DESC NULLS LAST, "
           "last_name ASC, first_name ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_alumnus(alumni_id: int,
                    payload: dict[str, Any], *,
                    actor: str | None = None) -> Alumnus:
    """Update an alumnus and record any field-level changes in
    ``alumni_audit_log``. Pass ``actor`` (a staff id / username) to
    attribute the edit; if omitted the audit row records 'system'."""
    init_db()
    existing = get_alumnus(alumni_id)
    if existing is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    merged = {
        "original_student_id": payload.get("original_student_id",
                                            existing.original_student_id),
        "first_name":          payload.get("first_name",
                                            existing.first_name),
        "last_name":           payload.get("last_name",
                                            existing.last_name),
        "preferred_name":      payload.get("preferred_name",
                                            existing.preferred_name),
        "pronouns":            payload.get("pronouns",
                                            existing.pronouns),
        "gender":              payload.get("gender", existing.gender),
        "dob":                 payload.get("dob", existing.dob),
        "leaving_year":        payload.get("leaving_year",
                                            existing.leaving_year),
        "leaving_date":        payload.get("leaving_date",
                                            existing.leaving_date),
        "leaving_reason":      payload.get("leaving_reason",
                                            existing.leaving_reason),
        "destination_type":    payload.get("destination_type",
                                            existing.destination_type),
        "destination_detail":  payload.get("destination_detail",
                                            existing.destination_detail),
        "current_role":        payload.get("current_role",
                                            existing.current_role),
        "current_employer":    payload.get("current_employer",
                                            existing.current_employer),
        "current_sector":      payload.get("current_sector",
                                            existing.current_sector),
        "current_location":    payload.get("current_location",
                                            existing.current_location),
        "country":             payload.get("country", existing.country),
        "region":              payload.get("region", existing.region),
        "email":               payload.get("email", existing.email),
        "phone":               payload.get("phone", existing.phone),
        "address":             payload.get("address", existing.address),
        "linkedin":            payload.get("linkedin",
                                            existing.linkedin),
        "other_social":        payload.get("other_social",
                                            existing.other_social),
        "photo_path":          payload.get("photo_path",
                                            existing.photo_path),
        "bio":                 payload.get("bio", existing.bio),
        "opt_in_contact":      payload.get("opt_in_contact",
                                            existing.opt_in_contact),
        "status":              payload.get("status", existing.status),
        "last_contacted":      payload.get("last_contacted",
                                            existing.last_contacted),
        "notes":               payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni SET
                   original_student_id = ?, first_name = ?, last_name = ?,
                   preferred_name = ?, pronouns = ?, gender = ?,
                   dob = ?, leaving_year = ?,
                   leaving_date = ?, leaving_reason = ?,
                   destination_type = ?, destination_detail = ?,
                   current_role = ?, current_employer = ?,
                   current_sector = ?, current_location = ?,
                   country = ?, region = ?,
                   email = ?, phone = ?,
                   address = ?, linkedin = ?, other_social = ?,
                   photo_path = ?, bio = ?,
                   opt_in_contact = ?, status = ?, last_contacted = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE alumni_id = ?""",
            (p["original_student_id"], p["first_name"], p["last_name"],
             p["preferred_name"], p["pronouns"], p["gender"],
             p["dob"], p["leaving_year"],
             p["leaving_date"], p["leaving_reason"],
             p["destination_type"], p["destination_detail"],
             p["current_role"], p["current_employer"],
             p["current_sector"], p["current_location"],
             p["country"], p["region"],
             p["email"], p["phone"],
             p["address"], p["linkedin"], p["other_social"],
             p["photo_path"], p["bio"],
             1 if p["opt_in_contact"] else 0, p["status"],
             p["last_contacted"], p["notes"], alumni_id),
        )
        conn.commit()
    out = get_alumnus(alumni_id)
    assert out is not None
    _audit_diff(existing, out, actor=actor)
    _log_action("alumnus.update", actor=actor, alumni_id=alumni_id,
                  status=out.status, fields=len(payload))
    return out


# Fields the audit log tracks. We deliberately skip purely
# derived/internal ones (created_at / updated_at / bounce_count).
_AUDITABLE_FIELDS: tuple[str, ...] = (
    "first_name", "last_name", "preferred_name", "pronouns",
    "gender", "dob", "leaving_year", "leaving_date",
    "leaving_reason", "destination_type", "destination_detail",
    "current_role", "current_employer", "current_sector",
    "current_location", "country", "region",
    "email", "phone", "address", "linkedin", "other_social",
    "photo_path", "bio", "opt_in_contact", "status",
    "last_contacted", "notes", "original_student_id",
)


def _audit_diff(before: Alumnus, after: Alumnus, *,
                  actor: str | None) -> None:
    actor_label = (actor or "system").strip() or "system"
    changes: list[tuple[str, str | None, str | None]] = []
    for f in _AUDITABLE_FIELDS:
        old = getattr(before, f, None)
        new = getattr(after, f, None)
        if isinstance(old, bool):
            old = "1" if old else "0"
        if isinstance(new, bool):
            new = "1" if new else "0"
        if (old or None) != (new or None):
            changes.append((f,
                             None if old in (None, "") else str(old),
                             None if new in (None, "") else str(new)))
    if not changes:
        return
    with _connect() as conn:
        conn.executemany(
            """INSERT INTO alumni_audit_log
                   (alumni_id, field, old_value, new_value, changed_by)
               VALUES (?, ?, ?, ?, ?)""",
            [(after.alumni_id, f, o, n, actor_label)
             for f, o, n in changes])
        conn.commit()


def list_audit_log(alumni_id: int, *,
                    limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT audit_id, field, old_value, new_value, "
            "       changed_by, changed_at "
            "FROM alumni_audit_log WHERE alumni_id = ? "
            "ORDER BY changed_at DESC, audit_id DESC LIMIT ?",
            (alumni_id, int(limit))).fetchall()
    return [dict(r) for r in rows]


def set_status(alumni_id: int, status: str) -> Alumnus:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_alumnus(alumni_id, {"status": status})


def record_contact(alumni_id: int, *,
                   when: str | None = None,
                   channel: str = "Other",
                   staff_id: str | None = None,
                   subject: str | None = None,
                   summary: str | None = None,
                   log: bool = True) -> Alumnus:
    """Bump ``last_contacted`` and (by default) write a row to the
    shared messages log. Pass ``log=False`` to update the field only."""
    day = when or _dt.date.today().isoformat()
    out = update_alumnus(alumni_id, {"last_contacted": day})
    if log:
        add_communication(alumni_id, {
            "date":     day,
            "channel":  channel,
            "staff_id": staff_id,
            "subject":  subject or f"Contact recorded ({channel})",
            "summary":  summary,
            "status":   "Sent",
        })
    return out


def delete_alumnus(alumni_id: int, *,
                    actor: str | None = None) -> bool:
    """Soft delete — flips ``deleted_at`` to now. The row stays in
    the table for the undo window (see ``SOFT_DELETE_UNDO_DAYS``)
    and can be brought back with :func:`restore_alumnus`. Use
    :func:`purge_alumnus` to remove it physically."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni SET deleted_at = datetime('now'), "
            "updated_at = datetime('now') "
            "WHERE alumni_id = ? AND deleted_at IS NULL",
            (alumni_id,))
        conn.commit()
        if cur.rowcount:
            with _connect() as c2:
                c2.execute(
                    """INSERT INTO alumni_audit_log
                           (alumni_id, field, old_value, new_value,
                            changed_by)
                       VALUES (?, 'deleted_at', NULL,
                                 datetime('now'), ?)""",
                    (alumni_id,
                     (actor or "system").strip() or "system"))
                c2.commit()
            _log_action("alumnus.soft_delete", actor=actor,
                          alumni_id=alumni_id)
            return True
    return False


def restore_alumnus(alumni_id: int, *,
                     actor: str | None = None) -> Alumnus:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni SET deleted_at = NULL, "
            "updated_at = datetime('now') "
            "WHERE alumni_id = ? AND deleted_at IS NOT NULL",
            (alumni_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No soft-deleted alumnus #{alumni_id}")
        conn.execute(
            """INSERT INTO alumni_audit_log
                   (alumni_id, field, old_value, new_value,
                    changed_by)
               VALUES (?, 'deleted_at', 'soft-deleted', NULL, ?)""",
            (alumni_id,
             (actor or "system").strip() or "system"))
        conn.commit()
    a = get_alumnus(alumni_id)
    assert a is not None
    _log_action("alumnus.restore", actor=actor, alumni_id=alumni_id)
    return a


def list_soft_deleted() -> list[Alumnus]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni WHERE deleted_at IS NOT NULL "
            "ORDER BY deleted_at DESC").fetchall()
    return [_row(r) for r in rows]


def purge_alumnus(alumni_id: int) -> bool:
    """Physical delete. Audit / child rows cascade per their FK
    ``ON DELETE CASCADE`` definitions."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni WHERE alumni_id = ?", (alumni_id,))
        conn.commit()
        if cur.rowcount:
            _log_action("alumnus.purge", alumni_id=alumni_id,
                          level=logging.WARNING)
            return True
    return False


def purge_expired_soft_deletes(*,
                                 undo_days: int = SOFT_DELETE_UNDO_DAYS
                                 ) -> int:
    """Hard-delete every soft-deleted alumnus whose deletion is older
    than ``undo_days``. Returns the count purged."""
    init_db()
    cutoff = (_dt.datetime.now()
                - _dt.timedelta(days=undo_days)
                ).strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni WHERE deleted_at IS NOT NULL "
            "AND deleted_at < ?", (cutoff,))
        conn.commit()
        purged = cur.rowcount
    if purged:
        _log_action("alumnus.purge_expired", purged=purged,
                      undo_days=undo_days, level=logging.WARNING)
    return purged


# ── Deduplication ────────────────────────────────────────────────

@dataclass
class DuplicateCandidate:
    score: float
    primary: Alumnus
    other: Alumnus


def find_duplicates(*, threshold: float = 0.85,
                       include_deleted: bool = False
                       ) -> list[DuplicateCandidate]:
    """Pairwise compare alumni and return candidate duplicates.
    Names are compared via :class:`difflib.SequenceMatcher` after
    case-folding; if DOBs are present on both rows they must match
    exactly. The lower-numbered alumni_id is treated as the primary
    so merges default to keeping the older record."""
    from difflib import SequenceMatcher
    rows = list_alumni(include_deleted=include_deleted)
    out: list[DuplicateCandidate] = []
    for i, a in enumerate(rows):
        a_name = f"{a.first_name} {a.last_name}".lower().strip()
        for b in rows[i + 1:]:
            if a.dob and b.dob and a.dob != b.dob:
                continue
            b_name = f"{b.first_name} {b.last_name}".lower().strip()
            score = SequenceMatcher(None, a_name, b_name).ratio()
            if score < threshold:
                continue
            primary, other = (
                (a, b) if a.alumni_id < b.alumni_id else (b, a))
            out.append(DuplicateCandidate(
                score=score, primary=primary, other=other))
    out.sort(key=lambda c: -c.score)
    return out


# ── Merge ────────────────────────────────────────────────────────

# Child tables whose ``alumni_id`` foreign key must be repointed at
# the keeper when merging two alumni.
_CHILD_TABLES_FOR_MERGE: tuple[str, ...] = (
    "alumni_education", "alumni_career",
    "alumni_emails", "alumni_phones",
    "alumni_achievements",
    "alumni_tag_links",
    "alumni_event_rsvps",
    "alumni_work_exp_offers",
    "alumni_references",
    "alumni_volunteer_hours",
    "alumni_donations", "alumni_pledges",
    "alumni_consent",
    "alumni_portal_tokens",
    "alumni_audit_log",
    "alumni_survey_invitations",
)


def merge_alumni(keep_id: int, merge_id: int, *,
                  actor: str | None = None) -> Alumnus:
    """Merge two alumni records. All child rows referencing
    ``merge_id`` are repointed at ``keep_id``; non-null fields from
    the merged record fill in gaps in the keeper; the merged row is
    then physically deleted. The keeper's ``original_student_id``
    is preserved unless it was empty (in which case the merged
    record's id is used).

    Raises ``ValidationError`` if either id is unknown or they are
    equal. The whole operation is wrapped in a single transaction —
    on failure nothing is changed."""
    init_db()
    if keep_id == merge_id:
        raise ValidationError(
            "keep_id and merge_id must be different")
    keep  = get_alumnus(keep_id)
    other = get_alumnus(merge_id)
    if keep is None or other is None:
        raise ValidationError(
            "Both alumni must exist (no soft-delete filter)")

    # Ensure the messages-side migration has run before we open our
    # own connection — adding a column on a *different* connection
    # after we've begun a transaction here would otherwise leave us
    # with a stale schema view.
    _messages_module().init_db()

    # Fields where we let ``other`` fill in if the keeper is blank.
    fill_fields = list(_AUDITABLE_FIELDS) + ["photo_path", "bio"]
    filled: dict[str, Any] = {}
    for f in fill_fields:
        if (getattr(keep, f, None) in (None, "")
                and getattr(other, f, None) not in (None, "")):
            filled[f] = getattr(other, f)

    # Prefer the older / non-null original_student_id.
    if not keep.original_student_id and other.original_student_id:
        filled["original_student_id"] = other.original_student_id

    with _connect() as conn:
        try:
            # Repoint plain child tables.
            for tbl in _CHILD_TABLES_FOR_MERGE:
                conn.execute(
                    f"UPDATE OR IGNORE {tbl} "
                    f"SET alumni_id = ? WHERE alumni_id = ?",
                    (keep_id, merge_id))
                # If the OR-IGNORE skipped rows because of a UNIQUE
                # collision (e.g. tag links, RSVPs), drop the
                # losing rows so the cascade-delete of merge_id
                # doesn't kill them.
                conn.execute(
                    f"DELETE FROM {tbl} WHERE alumni_id = ?",
                    (merge_id,))
            # Mentor side of mentorships uses a different column.
            conn.execute(
                "UPDATE alumni_mentorships "
                "SET mentor_alumni_id = ? "
                "WHERE mentor_alumni_id = ?",
                (keep_id, merge_id))
            # Channel prefs: keep the keeper's row; drop the loser's.
            conn.execute(
                "DELETE FROM alumni_channel_prefs WHERE alumni_id = ?",
                (merge_id,))
            # Speakers: keep keeper's row; drop loser's.
            conn.execute(
                "DELETE FROM alumni_speakers WHERE alumni_id = ?",
                (merge_id,))
            # messages.alumni_id is a soft link; repoint it.
            conn.execute(
                "UPDATE messages SET alumni_id = ? WHERE alumni_id = ?",
                (keep_id, merge_id))
            # Finally remove the merged shell row.
            conn.execute(
                "DELETE FROM alumni WHERE alumni_id = ?",
                (merge_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    if filled:
        update_alumnus(keep_id, filled, actor=actor)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_audit_log
                   (alumni_id, field, old_value, new_value,
                    changed_by)
               VALUES (?, 'merge', ?, NULL, ?)""",
            (keep_id, f"merged #{merge_id} into here",
             (actor or "system").strip() or "system"))
        conn.commit()

    final = get_alumnus(keep_id)
    assert final is not None
    _log_action("alumnus.merge", actor=actor,
                  kept=keep_id, merged=merge_id,
                  level=logging.WARNING)
    return final


# ── Archive an existing student ───────────────────────────────────

def archive_student(
    student_id: str,
    *,
    leaving_year: str | None = None,
    leaving_date: str | None = None,
    leaving_reason: str | None = None,
    destination_type: str = DEFAULT_DESTINATION,
    destination_detail: str | None = None,
    notes: str | None = None,
    delete_student: bool = False,
) -> Alumnus:
    """Create an alumnus row from an existing student. By default the
    underlying ``students`` row is kept (so attendance / behaviour
    history stays linked); pass ``delete_student=True`` to remove
    it. Idempotent if an alumnus row already exists for this id —
    that existing row is updated with any newly supplied destination
    fields and returned."""
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(student_id.strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")

    existing = get_alumnus_by_original_id(student.student_id)
    if existing is not None:
        return update_alumnus(existing.alumni_id, {
            "leaving_year":       leaving_year or existing.leaving_year,
            "leaving_date":       leaving_date or existing.leaving_date,
            "leaving_reason":     leaving_reason or existing.leaving_reason,
            "destination_type":   destination_type
                                  if destination_type != DEFAULT_DESTINATION
                                  else existing.destination_type,
            "destination_detail": destination_detail
                                  or existing.destination_detail,
            "notes":              notes or existing.notes,
        })

    today = _dt.date.today()
    fallback_year = str(today.year if today.month >= 9 else today.year - 1)
    a = create_alumnus({
        "original_student_id": student.student_id,
        "first_name":          student.first_name,
        "last_name":           student.last_name,
        "leaving_year":        leaving_year or fallback_year,
        "leaving_date":        leaving_date or today.isoformat(),
        "leaving_reason":      leaving_reason or DEFAULT_LEAVING_REASON,
        "destination_type":    destination_type,
        "destination_detail":  destination_detail,
        "email":               student.email,
        "phone":               student.phone,
        "status":              DEFAULT_STATUS,
        "notes":               notes,
    })
    if delete_student:
        try:
            _students.delete_student(student.student_id)
        except Exception:
            logger.exception(
                "Archived alumnus #%d but could not delete student %s",
                a.alumni_id, student.student_id)
    _log_action("alumnus.archive_student", alumni_id=a.alumni_id,
                  student_id=student.student_id,
                  destination=destination_type,
                  delete_student=delete_student)
    return a


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    rows = list_alumni()
    by_status = {s: 0 for s in STATUSES}
    by_dest   = {d: 0 for d in DESTINATION_TYPES}
    by_year:    dict[str, int] = {}
    contactable = 0
    no_contact = 0
    most_recent_year: str | None = None
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_dest[a.destination_type] = by_dest.get(
            a.destination_type, 0) + 1
        if a.leaving_year:
            by_year[a.leaving_year] = by_year.get(
                a.leaving_year, 0) + 1
            if most_recent_year is None or a.leaving_year > most_recent_year:
                most_recent_year = a.leaving_year
        if (a.status == "Active" and a.opt_in_contact
                and (a.email or a.phone)):
            contactable += 1
        if a.status == "Active" and not (a.email or a.phone):
            no_contact += 1
    return Summary(
        total=len(rows),
        by_status=by_status,
        by_destination=by_dest,
        by_leaving_year=dict(sorted(by_year.items(),
                                      key=lambda kv: kv[0],
                                      reverse=True)),
        contactable=contactable,
        no_contact_method=no_contact,
        most_recent_year=most_recent_year,
    )


def create_alumnus(payload: dict[str, Any]) -> Alumnus:
    """Create an alumnus and publish the ``alumnus.created`` webhook.

    The insert itself is :func:`_original_create_alumnus`; this public
    entry point (used by internal callers such as the CSV import too)
    adds the webhook emit that used to be bolted on by re-binding the
    module global at the end of the old single-file module."""
    a = _original_create_alumnus(payload)
    _emit_webhook("alumnus.created", {
        "alumni_id": a.alumni_id, "full_name": a.full_name,
        "leaving_year": a.leaving_year,
        "destination_type": a.destination_type})
    return a


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .comms import (  # noqa: E402,F401
    _messages_module,
    add_communication,
)
from .integrations import (  # noqa: E402,F401
    _emit_webhook,
)
