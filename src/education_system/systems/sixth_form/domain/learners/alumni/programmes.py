"""Sixth-form alumni — Speakers register, work-experience offers, references given and volunteer hours.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    REFERENCE_TYPES,
    SECTORS,
    VOLUNTEER_ACTIVITY_TYPES,
    WORK_EXP_APP_STATUSES,
    WORK_EXP_STATUSES,
)
from .db import (
    ValidationError,
    _connect,
    _require,
    _validate_date,
    init_db,
)


# ── Speakers register ────────────────────────────────────────────

@dataclass
class SpeakerProfile:
    alumni_id: int
    topics: str | None
    year_groups: str | None
    availability_notes: str | None
    last_confirmed_at: str | None
    updated_at: str


def _row_speaker(r: db.Row) -> SpeakerProfile:
    return SpeakerProfile(
        alumni_id=r["alumni_id"], topics=r["topics"],
        year_groups=r["year_groups"],
        availability_notes=r["availability_notes"],
        last_confirmed_at=r["last_confirmed_at"],
        updated_at=r["updated_at"],
    )


def upsert_speaker(alumni_id: int, *,
                    topics: str | None = None,
                    year_groups: str | None = None,
                    availability_notes: str | None = None,
                    confirm: bool = False) -> SpeakerProfile:
    init_db()
    today = _dt.date.today().isoformat()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        existing = conn.execute(
            "SELECT * FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        if existing:
            new_topics = ((topics or "").strip()
                            if topics is not None else existing["topics"])
            new_years  = ((year_groups or "").strip()
                            if year_groups is not None
                            else existing["year_groups"])
            new_avail  = ((availability_notes or "").strip()
                            if availability_notes is not None
                            else existing["availability_notes"])
            new_conf   = (today if confirm
                            else existing["last_confirmed_at"])
            conn.execute(
                """UPDATE alumni_speakers SET
                       topics = ?, year_groups = ?,
                       availability_notes = ?, last_confirmed_at = ?,
                       updated_at = datetime('now')
                   WHERE alumni_id = ?""",
                (new_topics or None, new_years or None,
                 new_avail or None, new_conf, alumni_id))
        else:
            conn.execute(
                """INSERT INTO alumni_speakers
                       (alumni_id, topics, year_groups,
                        availability_notes, last_confirmed_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (alumni_id,
                 (topics or "").strip() or None,
                 (year_groups or "").strip() or None,
                 (availability_notes or "").strip() or None,
                 today if confirm else None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
    return _row_speaker(r)


def get_speaker(alumni_id: int) -> SpeakerProfile | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
    return _row_speaker(r) if r else None


def list_speakers(*, topic_like: str | None = None,
                    year_group: str | None = None
                    ) -> list[SpeakerProfile]:
    init_db()
    clauses, args = [], []
    if topic_like:
        clauses.append("topics LIKE ?")
        args.append(f"%{topic_like.strip()}%")
    if year_group:
        clauses.append("year_groups LIKE ?")
        args.append(f"%{year_group.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_speakers {where} "
            "ORDER BY COALESCE(last_confirmed_at, '') DESC, alumni_id")
    with _connect() as conn:
        return [_row_speaker(r)
                  for r in conn.execute(sql, args).fetchall()]


def remove_speaker(alumni_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Work-experience offers ───────────────────────────────────────

@dataclass
class WorkExpOffer:
    offer_id: int
    alumni_id: int
    title: str
    employer: str | None
    sector: str | None
    location: str | None
    duration_weeks: int | None
    start_window: str | None
    vacancy_count: int
    requirements: str | None
    deadline: str | None
    status: str
    notes: str | None
    created_at: str


@dataclass
class WorkExpApplication:
    application_id: int
    offer_id: int
    student_id: str
    applied_on: str
    status: str
    outcome_notes: str | None


def _row_wxo(r: db.Row) -> WorkExpOffer:
    return WorkExpOffer(
        offer_id=r["offer_id"], alumni_id=r["alumni_id"],
        title=r["title"], employer=r["employer"],
        sector=r["sector"], location=r["location"],
        duration_weeks=r["duration_weeks"],
        start_window=r["start_window"],
        vacancy_count=int(r["vacancy_count"] or 1),
        requirements=r["requirements"], deadline=r["deadline"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _row_wxa(r: db.Row) -> WorkExpApplication:
    return WorkExpApplication(
        application_id=r["application_id"], offer_id=r["offer_id"],
        student_id=r["student_id"], applied_on=r["applied_on"],
        status=r["status"], outcome_notes=r["outcome_notes"],
    )


def add_work_exp_offer(alumni_id: int,
                          payload: dict[str, Any]) -> WorkExpOffer:
    init_db()
    title = _require(payload.get("title"), "Title").strip()
    sector = (payload.get("sector") or "").strip()
    if sector and sector not in SECTORS:
        raise ValidationError(
            f"Sector must be one of: {', '.join(SECTORS)}")
    status = (payload.get("status") or "Open").strip()
    if status not in WORK_EXP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(WORK_EXP_STATUSES)}")
    weeks = payload.get("duration_weeks")
    weeks = max(0, int(weeks)) if weeks not in (None, "") else None
    vacancies = int(payload.get("vacancy_count") or 1) or 1
    deadline = _validate_date(payload.get("deadline"), "Deadline")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_work_exp_offers
                   (alumni_id, title, employer, sector, location,
                    duration_weeks, start_window, vacancy_count,
                    requirements, deadline, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, title,
             (payload.get("employer") or "").strip() or None,
             sector or None,
             (payload.get("location") or "").strip() or None,
             weeks,
             (payload.get("start_window") or "").strip() or None,
             vacancies,
             (payload.get("requirements") or "").strip() or None,
             deadline, status,
             (payload.get("notes") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_work_exp_offers WHERE offer_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_wxo(r)


def list_work_exp_offers(*, alumni_id: int | None = None,
                            status: str | None = None,
                            open_only: bool = False
                            ) -> list[WorkExpOffer]:
    init_db()
    clauses, args = [], []
    if alumni_id is not None:
        clauses.append("alumni_id = ?")
        args.append(int(alumni_id))
    if status:
        if status not in WORK_EXP_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(WORK_EXP_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        clauses.append("status = 'Open'")
        clauses.append("(deadline IS NULL OR deadline >= ?)")
        args.append(_dt.date.today().isoformat())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_work_exp_offers {where} "
            "ORDER BY COALESCE(deadline, '9999') ASC, offer_id DESC")
    with _connect() as conn:
        return [_row_wxo(r)
                  for r in conn.execute(sql, args).fetchall()]


def update_work_exp_status(offer_id: int, status: str) -> WorkExpOffer:
    if status not in WORK_EXP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(WORK_EXP_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_work_exp_offers SET status = ? "
            "WHERE offer_id = ?", (status, offer_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(f"No offer #{offer_id}")
        r = conn.execute(
            "SELECT * FROM alumni_work_exp_offers WHERE offer_id = ?",
            (offer_id,)).fetchone()
    return _row_wxo(r)


def delete_work_exp_offer(offer_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_work_exp_offers WHERE offer_id = ?",
            (offer_id,))
        conn.commit()
        return cur.rowcount > 0


def apply_to_work_exp(offer_id: int, student_id: str, *,
                        applied_on: str | None = None,
                        outcome_notes: str | None = None
                        ) -> WorkExpApplication:
    init_db()
    day = _validate_date(applied_on or _dt.date.today().isoformat(),
                          "Applied on", required=True)
    sid = _require(student_id, "Student id").strip()
    with _connect() as conn:
        r0 = conn.execute(
            "SELECT 1 FROM alumni_work_exp_offers WHERE offer_id = ?",
            (offer_id,)).fetchone()
        if r0 is None:
            raise ValidationError(f"No offer #{offer_id}")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_work_exp_applications
                       (offer_id, student_id, applied_on,
                        status, outcome_notes)
                   VALUES (?, ?, ?, 'Submitted', ?)""",
                (offer_id, sid, day,
                 (outcome_notes or "").strip() or None))
            conn.commit()
            new_id = cur.lastrowid
        except db.IntegrityError:
            raise ValidationError(
                f"{sid} has already applied to offer #{offer_id}") \
                from None
        r = conn.execute(
            "SELECT * FROM alumni_work_exp_applications "
            "WHERE application_id = ?", (new_id,)).fetchone()
    return _row_wxa(r)


def set_work_exp_application_status(application_id: int,
                                       status: str,
                                       *,
                                       notes: str | None = None
                                       ) -> WorkExpApplication:
    if status not in WORK_EXP_APP_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(WORK_EXP_APP_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_work_exp_applications "
            "SET status = ?, outcome_notes = COALESCE(?, outcome_notes) "
            "WHERE application_id = ?",
            (status, notes, application_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No application #{application_id}")
        r = conn.execute(
            "SELECT * FROM alumni_work_exp_applications "
            "WHERE application_id = ?",
            (application_id,)).fetchone()
    return _row_wxa(r)


def list_work_exp_applications(offer_id: int
                                  ) -> list[WorkExpApplication]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_work_exp_applications "
            "WHERE offer_id = ? "
            "ORDER BY applied_on DESC, application_id DESC",
            (offer_id,)).fetchall()
    return [_row_wxa(r) for r in rows]


def delete_work_exp_application(application_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_work_exp_applications "
            "WHERE application_id = ?", (application_id,))
        conn.commit()
        return cur.rowcount > 0


# ── References given ─────────────────────────────────────────────

@dataclass
class Reference:
    reference_id: int
    alumni_id: int
    staff_id: str | None
    ref_type: str
    requested_on: str | None
    sent_on: str | None
    target_name: str | None
    target_url: str | None
    notes: str | None
    created_at: str


def _row_reference(r: db.Row) -> Reference:
    return Reference(
        reference_id=r["reference_id"], alumni_id=r["alumni_id"],
        staff_id=r["staff_id"], ref_type=r["ref_type"],
        requested_on=r["requested_on"], sent_on=r["sent_on"],
        target_name=r["target_name"], target_url=r["target_url"],
        notes=r["notes"], created_at=r["created_at"],
    )


def add_reference(alumni_id: int,
                    payload: dict[str, Any]) -> Reference:
    init_db()
    rt = (payload.get("ref_type") or "Job").strip()
    if rt not in REFERENCE_TYPES:
        raise ValidationError(
            f"Reference type must be one of: "
            f"{', '.join(REFERENCE_TYPES)}")
    requested = _validate_date(payload.get("requested_on"),
                                  "Requested on")
    sent = _validate_date(payload.get("sent_on"), "Sent on")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_references
                   (alumni_id, staff_id, ref_type, requested_on, sent_on,
                    target_name, target_url, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id,
             ((payload.get("staff_id") or "").strip().upper()
                or None),
             rt, requested, sent,
             (payload.get("target_name") or "").strip() or None,
             (payload.get("target_url") or "").strip() or None,
             (payload.get("notes") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_references WHERE reference_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_reference(r)


def list_references(alumni_id: int) -> list[Reference]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_references WHERE alumni_id = ? "
            "ORDER BY COALESCE(sent_on, requested_on, created_at) "
            "DESC, reference_id DESC",
            (alumni_id,)).fetchall()
    return [_row_reference(r) for r in rows]


def mark_reference_sent(reference_id: int, *,
                          when: str | None = None) -> Reference:
    init_db()
    sent = _validate_date(when or _dt.date.today().isoformat(),
                            "Sent on", required=True)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_references SET sent_on = ? "
            "WHERE reference_id = ?", (sent, reference_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No reference #{reference_id}")
        r = conn.execute(
            "SELECT * FROM alumni_references WHERE reference_id = ?",
            (reference_id,)).fetchone()
    return _row_reference(r)


def delete_reference(reference_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_references WHERE reference_id = ?",
            (reference_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Volunteer hours ──────────────────────────────────────────────

@dataclass
class VolunteerEntry:
    volunteer_id: int
    alumni_id: int
    activity_date: str
    hours: float
    activity_type: str
    event_id: int | None
    notes: str | None
    created_at: str


def _row_volunteer(r: db.Row) -> VolunteerEntry:
    return VolunteerEntry(
        volunteer_id=r["volunteer_id"], alumni_id=r["alumni_id"],
        activity_date=r["activity_date"],
        hours=float(r["hours"]),
        activity_type=r["activity_type"], event_id=r["event_id"],
        notes=r["notes"], created_at=r["created_at"],
    )


def log_volunteer_hours(alumni_id: int, hours: float, *,
                          activity_type: str = "Other",
                          activity_date: str | None = None,
                          event_id: int | None = None,
                          notes: str | None = None
                          ) -> VolunteerEntry:
    init_db()
    if activity_type not in VOLUNTEER_ACTIVITY_TYPES:
        raise ValidationError(
            f"Activity type must be one of: "
            f"{', '.join(VOLUNTEER_ACTIVITY_TYPES)}")
    try:
        h = float(hours)
    except (TypeError, ValueError):
        raise ValidationError("Hours must be a number") from None
    if h <= 0:
        raise ValidationError("Hours must be greater than zero")
    day = _validate_date(activity_date or _dt.date.today().isoformat(),
                           "Activity date", required=True)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if event_id is not None:
            r0 = conn.execute(
                "SELECT 1 FROM alumni_events WHERE event_id = ?",
                (event_id,)).fetchone()
            if r0 is None:
                raise ValidationError(f"No event #{event_id}")
        cur = conn.execute(
            """INSERT INTO alumni_volunteer_hours
                   (alumni_id, activity_date, hours, activity_type,
                    event_id, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (alumni_id, day, h, activity_type, event_id,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_volunteer_hours "
            "WHERE volunteer_id = ?", (cur.lastrowid,)).fetchone()
    return _row_volunteer(r)


def list_volunteer_hours(alumni_id: int) -> list[VolunteerEntry]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_volunteer_hours WHERE alumni_id = ? "
            "ORDER BY activity_date DESC, volunteer_id DESC",
            (alumni_id,)).fetchall()
    return [_row_volunteer(r) for r in rows]


def total_volunteer_hours(alumni_id: int) -> float:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(hours), 0) AS h "
            "FROM alumni_volunteer_hours WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
    return float(r["h"])


def delete_volunteer_entry(volunteer_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_volunteer_hours WHERE volunteer_id = ?",
            (volunteer_id,))
        conn.commit()
        return cur.rowcount > 0


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .profile import (  # noqa: E402,F401
    _require_alumnus,
)
