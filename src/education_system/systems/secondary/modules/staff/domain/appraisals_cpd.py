"""Appraisals & CPD, part two: CPD (the activity catalogue, training requests
and bookings, attendance, evaluation, certificates, the CPD log and budget),
statutory training with expiry, and the summary / CSV export for the screen.

The tables, records and who-may-do-what rules are in :mod:`appraisals`;
this module only adds the CPD and training operations on top of them.
"""

from __future__ import annotations

import csv
import datetime as _dt
from collections import Counter
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.modules.staff.domain.appraisals import (  # the shared rules
    _AC_SELECT,
    _RC_SELECT,
    _TR_SELECT,
    ACTIVITY_STATUSES,
    ACTIVITY_TYPES,
    DEFAULT_ACTIVITY_STATUS,
    DEFAULT_ACTIVITY_TYPE,
    DEFAULT_RECORD_STATUS,
    DONE,
    DUE_SOON_DAYS,
    GOING,
    RATINGS,
    RECORD_STATUSES,
    REQUIRED_TRAINING,
    SPENDING,
    TRAINING_TYPES,
    Activity,
    NotFound,
    PermissionDenied,
    Record,
    Training,
    ValidationError,
    _appraisees,
    _audit,
    _bool,
    _choice,
    _date,
    _deny,
    _make,
    _me_id,
    _number,
    _require_editor,
    _require_staff,
    _staff,
    _text,
    _update_row,
    _year,
    is_editor,
    list_appraisals,
)
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import current_year
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

__all__ = ["ValidationError", "PermissionDenied", "NotFound"]


# ── CPD activities (the catalogue) ───────────────────────────────────

AC_FIELDS = ("title", "provider", "activity_type", "activity_date", "end_date", "hours", "cost",
             "certificated", "accreditor", "location", "capacity", "organiser", "description",
             "outcomes", "status", "notes")


def get_activity(activity_id: int) -> Activity:
    with database.connect() as conn:
        r = conn.execute(_AC_SELECT + " WHERE c.activity_id = ?", (int(activity_id),)).fetchone()
    if r is None:
        raise NotFound(f"No CPD activity {activity_id}")
    return _make(Activity, r)


def list_activities(*, activity_type: str | None = None, status: str | None = None,
                    title: str | None = None, upcoming_only: bool = False,
                    completed_only: bool = False) -> list[Activity]:
    sql, params = _AC_SELECT + " WHERE 1=1", []
    for col, val in (("c.activity_type", activity_type), ("c.status", status)):
        if val:
            sql += f" AND {col} = ?"
            params.append(val)
    if title and title.strip():
        sql += " AND c.title LIKE ?"
        params.append(f"%{title.strip()}%")
    if completed_only:
        sql += " AND c.status = 'Completed'"
    with database.connect() as conn:
        rows = [_make(Activity, r) for r in conn.execute(
            sql + " ORDER BY c.activity_date DESC", params)]
    return [a for a in rows if a.is_upcoming] if upcoming_only else rows


def _clean_activity(data: dict[str, Any], current: Activity | None
                    ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in AC_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in AC_FIELDS})
    out: dict[str, Any] = {"title": _text(merged.get("title"), 200)}
    if not out["title"]:
        problems.append("Title is required")
    out["activity_type"] = _choice(merged.get("activity_type"), ACTIVITY_TYPES, "Type",
                                   problems, DEFAULT_ACTIVITY_TYPE)
    out["status"] = _choice(merged.get("status"), ACTIVITY_STATUSES, "Status", problems,
                            DEFAULT_ACTIVITY_STATUS)
    out["activity_date"] = _date(merged.get("activity_date"), "Date", problems)
    if not out["activity_date"] and not any(p.startswith("Date") for p in problems):
        problems.append("Date is required")
    out["end_date"] = _date(merged.get("end_date"), "End date", problems)
    if out["end_date"] and out["activity_date"] and out["end_date"] < out["activity_date"]:
        problems.append("End date can't be before the start")
    out["hours"] = _number(merged.get("hours"), "Hours", problems, 0, 1000)
    out["cost"] = _number(merged.get("cost"), "Cost", problems, 0, 100000)
    cap = _number(merged.get("capacity"), "Capacity", problems, 1, 10000)
    out["capacity"] = int(cap) if cap is not None else None
    out["certificated"] = _bool(merged.get("certificated"))
    for k in ("provider", "accreditor", "location", "organiser"):
        out[k] = _text(merged.get(k), 120)
    for k in ("description", "outcomes", "notes"):
        out[k] = _text(merged.get(k), 4000)
    return out, problems


def create_activity(data: dict[str, Any], *, actor: Principal) -> Activity:
    _require_editor(actor, "activity_create")
    c, problems = _clean_activity(data, None)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        aid = conn.execute(
            f"INSERT INTO cpd_activities ({', '.join(AC_FIELDS)}, created_by) "  # nosec B608 - fixed
            f"VALUES ({', '.join('?' * len(AC_FIELDS))}, ?)",
            (*(int(c[k]) if isinstance(c[k], bool) else c[k] for k in AC_FIELDS),
             actor.username)).lastrowid
        _audit(conn, "activity", "create", actor, aid, None)
    return get_activity(aid)


def update_activity(activity_id: int, changes: dict[str, Any], *, actor: Principal) -> Activity:
    cur = get_activity(activity_id)
    _require_editor(actor, "activity_update", cur.activity_id)
    c, problems = _clean_activity(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = {k: c[k] for k in AC_FIELDS if c[k] != getattr(cur, k)}
    _update_row("cpd_activities", "activity_id", cur.activity_id, changed)
    if changed:
        with database.connect() as conn:
            _audit(conn, "activity", "update", actor, cur.activity_id, None,
                   fields=sorted(changed))
    return get_activity(cur.activity_id)


def mark_activity_completed(activity_id: int, *, actor: Principal) -> Activity:
    return update_activity(activity_id, {"status": "Completed"}, actor=actor)


def set_activity_status(activity_id: int, status: str, *, actor: Principal) -> Activity:
    problems: list[str] = []
    st = _choice(status, ACTIVITY_STATUSES, "Status", problems, None)
    if problems or st is None:
        raise ValidationError(problems or ["Choose a status"])
    return update_activity(activity_id, {"status": st}, actor=actor)


def delete_activity(activity_id: int, *, actor: Principal) -> bool:
    cur = get_activity(activity_id)
    _require_editor(actor, "activity_delete", cur.activity_id)
    with database.connect() as conn:
        conn.execute("DELETE FROM cpd_activities WHERE activity_id = ?", (cur.activity_id,))
        _audit(conn, "activity", "delete", actor, cur.activity_id, None, records=cur.records)
    return True


# ── CPD records: requests, bookings, attendance, evaluation ──────────

R_FIELDS = ("activity_id", "title", "provider", "start_date", "end_date", "cost",
            "cover_needed", "cover_days", "reason", "status", "booked_on", "attended_on",
            "hours_completed", "evaluation_rating", "evaluation_notes", "impact_on_practice",
            "certificate_received", "certificate_filed", "certificate_ref", "cost_to_staff",
            "notes")
#: What the person who asked can change while a request waits.
REQUEST_FIELDS = frozenset({"title", "provider", "start_date", "end_date", "cost",
                            "cover_needed", "cover_days", "reason", "notes", "activity_id"})


def get_record(record_id: int, *, actor: Principal | None = None) -> Record:
    with database.connect() as conn:
        r = conn.execute(_RC_SELECT + " WHERE r.record_id = ?", (int(record_id),)).fetchone()
    if r is None:
        raise NotFound(f"No CPD record {record_id}")
    rec = _make(Record, r)
    if actor is not None and not _can_see_record(actor, rec):
        _deny(actor, "record_view", rec.record_id, "That CPD record isn't yours to see.")
    return rec


def _can_see_record(actor: Principal, r: Record) -> bool:
    me = _me_id(actor)
    return is_editor(actor) or (me is not None and (me == r.staff_id
                                                    or r.staff_id in _appraisees(actor)))


def list_records(*, actor: Principal, staff_id: int | None = None, status: str | None = None,
                 activity_id: int | None = None, awaiting_cert: bool = False,
                 completed_only: bool = False, academic_year: str | None = None
                 ) -> list[Record]:
    _require_staff(actor, "records")
    sql, params = _RC_SELECT + " WHERE 1=1", []
    for col, val in (("r.staff_id", staff_id), ("r.activity_id", activity_id)):
        if val is not None:
            sql += f" AND {col} = ?"
            params.append(int(val))
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    if completed_only:
        sql += " AND r.status IN ('Attended', 'Completed')"
    with database.connect() as conn:
        rows = [_make(Record, r) for r in conn.execute(
            sql + " ORDER BY coalesce(r.start_date, r.created_at) DESC", params)]
    if awaiting_cert:
        rows = [r for r in rows if r.awaiting_certificate]
    if academic_year:
        rows = [r for r in rows if r.academic_year == academic_year]
    return [r for r in rows if _can_see_record(actor, r)]


def records_for_staff(staff_id: int, *, actor: Principal) -> list[Record]:
    return list_records(actor=actor, staff_id=staff_id)


def _clean_record(data: dict[str, Any], current: Record | None
                  ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in R_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in R_FIELDS})
    out: dict[str, Any] = {}
    act = merged.get("activity_id")
    out["activity_id"] = None
    if act not in (None, ""):
        try:
            a = get_activity(int(str(act).split(" ")[0].lstrip("#")))
            out["activity_id"] = a.activity_id
            for k, v in (("title", a.title), ("provider", a.provider),
                         ("start_date", a.activity_date), ("end_date", a.end_date),
                         ("cost", a.cost)):
                if merged.get(k) in (None, ""):
                    merged[k] = v
        except (ValueError, NotFound):
            problems.append(f"No CPD activity {act}")
    out["title"] = _text(merged.get("title"), 200)
    if not out["title"]:
        problems.append("Title is required")
    out["provider"] = _text(merged.get("provider"), 120)
    for k, label in (("start_date", "Start date"), ("end_date", "End date"),
                     ("booked_on", "Booked on"), ("attended_on", "Attended on")):
        out[k] = _date(merged.get(k), label, problems)
    if out["start_date"] and out["end_date"] and out["end_date"] < out["start_date"]:
        problems.append("End date can't be before the start")
    out["cost"] = _number(merged.get("cost"), "Cost", problems, 0, 100000)
    out["cost_to_staff"] = _number(merged.get("cost_to_staff"), "Cost to staff", problems, 0,
                                   100000)
    out["cover_needed"] = _bool(merged.get("cover_needed"))
    out["cover_days"] = _number(merged.get("cover_days"), "Cover days", problems, 0, 60)
    if out["cover_days"] and not out["cover_needed"]:
        out["cover_needed"] = True
    out["hours_completed"] = _number(merged.get("hours_completed"), "Hours", problems, 0, 1000)
    rating = merged.get("evaluation_rating")
    out["evaluation_rating"] = None
    if rating not in (None, ""):
        try:
            out["evaluation_rating"] = int(str(rating).strip()[:1])
            if out["evaluation_rating"] not in RATINGS:
                raise ValueError
        except ValueError:
            problems.append("Rating must be 1-5")
            out["evaluation_rating"] = None
    out["status"] = _choice(merged.get("status"), RECORD_STATUSES, "Status", problems,
                            DEFAULT_RECORD_STATUS)
    for k in ("certificate_received", "certificate_filed"):
        out[k] = _bool(merged.get(k))
    out["certificate_ref"] = _text(merged.get("certificate_ref"), 60)
    for k in ("reason", "evaluation_notes", "impact_on_practice", "notes"):
        out[k] = _text(merged.get(k), 4000)
    return out, problems


def _insert_record(staff_id: int, c: dict[str, Any], actor: Principal, action: str) -> Record:
    with database.connect() as conn:
        rid = conn.execute(
            f"INSERT INTO cpd_records (staff_id, {', '.join(R_FIELDS)}, requested_by) "  # nosec B608 - fixed
            f"VALUES (?, {', '.join('?' * len(R_FIELDS))}, ?)",
            (staff_id, *(int(c[k]) if isinstance(c[k], bool) else c[k] for k in R_FIELDS),
             actor.username)).lastrowid
        _audit(conn, "cpd", action, actor, rid, staff_id, status=c["status"])
    activity_log.record(f"appraisals.cpd_{action}", target=rid, principal=actor)
    return get_record(rid)


def request_cpd(data: dict[str, Any], *, actor: Principal) -> Record:
    """A training request for yourself (editors may ask for anyone)."""
    _require_staff(actor, "cpd_request")
    problems: list[str] = []
    who = data.get("staff_id") or data.get("staff")
    m = _staff(who, "Staff", problems) if who not in (None, "") else SD.me(actor)
    if m is None:
        raise ValidationError(problems or ["You have no staff record - ask HR to add one"])
    if m.staff_id != _me_id(actor) and not is_editor(actor):
        _deny(actor, "cpd_request", m.staff_code, "You can ask for training only for yourself.")
    c, more = _clean_record({**data, "status": "Requested"}, None)
    problems += more
    if problems:
        raise ValidationError(problems)
    return _insert_record(m.staff_id, c, actor, "request")


def create_record(data: dict[str, Any], *, actor: Principal) -> Record:
    """The old New record: the CPD lead books someone on (status Booked)."""
    _require_editor(actor, "cpd_create")
    problems: list[str] = []
    m = _staff(data.get("staff_id") or data.get("staff"), "Staff", problems,
               current_only=False)
    if m is None and not problems:
        problems.append("Staff is required")
    c, more = _clean_record(data, None)
    problems += more
    if problems or m is None:
        raise ValidationError(problems)
    c["booked_on"] = c["booked_on"] or _today().isoformat()
    return _insert_record(m.staff_id, c, actor, "create")


def update_record(record_id: int, changes: dict[str, Any], *, actor: Principal) -> Record:
    cur = get_record(record_id, actor=actor)
    keys = {k for k in changes if k in R_FIELDS}
    own_request = cur.status == "Requested" and _me_id(actor) == cur.staff_id \
        and keys <= REQUEST_FIELDS
    if not (is_editor(actor) or own_request):
        _deny(actor, "cpd_update", cur.record_id, "Only the CPD lead can change that.")
    c, problems = _clean_record(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = {k: c[k] for k in R_FIELDS if c[k] != getattr(cur, k)}
    _update_row("cpd_records", "record_id", cur.record_id, changed)
    if changed:
        with database.connect() as conn:
            _audit(conn, "cpd", "update", actor, cur.record_id, cur.staff_id,
                   fields=sorted(changed))
    return get_record(cur.record_id)


def decide(record_id: int, approve: bool, *, actor: Principal, note: str | None = None,
           allow_over_budget: bool = False) -> Record:
    """Approve or decline a request. Approving past the year's budget is refused
    unless *allow_over_budget*."""
    cur = get_record(record_id)
    _require_editor(actor, "cpd_decide", cur.record_id)
    if cur.status != "Requested":
        raise ValidationError([f"Only a request can be decided (this is {cur.status})"])
    warn = budget_warning(cur) if approve else None
    if warn and not allow_over_budget:
        raise ValidationError([warn])
    if not approve and not (note and note.strip()):
        raise ValidationError(["Say why the request is declined"])
    st = "Approved" if approve else "Declined"
    _update_row("cpd_records", "record_id", cur.record_id, {
        "status": st, "decided_by": actor.username,
        "decided_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "decision_note": _text(note, 1000)})
    with database.connect() as conn:
        _audit(conn, "cpd", "approve" if approve else "decline", actor, cur.record_id,
               cur.staff_id, over_budget=bool(warn))
    activity_log.record("appraisals.cpd_decide", target=cur.record_id, principal=actor,
                        decision=st)
    return get_record(cur.record_id)


def withdraw_request(record_id: int, *, actor: Principal) -> Record:
    cur = get_record(record_id, actor=actor)
    if not (is_editor(actor) or _me_id(actor) == cur.staff_id):
        _deny(actor, "cpd_withdraw", cur.record_id, "Only the person who asked can withdraw it.")
    if cur.status not in ("Requested", "Approved", "Booked", "Confirmed"):
        raise ValidationError([f"It is {cur.status} - too late to withdraw"])
    _update_row("cpd_records", "record_id", cur.record_id, {"status": "Cancelled"})
    with database.connect() as conn:
        _audit(conn, "cpd", "withdraw", actor, cur.record_id, cur.staff_id)
    return get_record(cur.record_id)


def _self_or_editor(actor: Principal, r: Record, action: str) -> None:
    if not (is_editor(actor) or _me_id(actor) == r.staff_id):
        _deny(actor, action, r.record_id, "Only the member of staff or the CPD lead can do that.")


def mark_attended(record_id: int, *, actor: Principal, attended_on: str | None = None,
                  hours_completed: Any = None) -> Record:
    cur = get_record(record_id, actor=actor)
    _self_or_editor(actor, cur, "cpd_attended")
    if cur.status not in GOING:
        raise ValidationError([f"Only approved or booked training can be attended "
                               f"(this is {cur.status})"])
    problems: list[str] = []
    day = _date(attended_on, "Attended on", problems) or _today().isoformat()
    if day > _today().isoformat():
        problems.append("Attended on can't be in the future")
    hours = _number(hours_completed, "Hours", problems, 0, 1000)
    if problems:
        raise ValidationError(problems)
    _update_row("cpd_records", "record_id", cur.record_id, {
        "status": "Attended", "attended_on": day,
        "hours_completed": hours if hours is not None else cur.hours_completed})
    with database.connect() as conn:
        _audit(conn, "cpd", "attended", actor, cur.record_id, cur.staff_id)
    return get_record(cur.record_id)


def record_evaluation(record_id: int, *, actor: Principal, rating: Any,
                      notes: str | None = None, impact: str | None = None) -> Record:
    """After attending: rating 1-5, notes, impact on practice. Completes it."""
    cur = get_record(record_id, actor=actor)
    _self_or_editor(actor, cur, "cpd_evaluate")
    if cur.status not in DONE:
        raise ValidationError(["Evaluate training once it has been attended"])
    c, problems = _clean_record({"evaluation_rating": rating, "evaluation_notes": notes,
                                 "impact_on_practice": impact}, cur)
    if c["evaluation_rating"] is None and not problems:
        problems.append("Give a rating 1-5")
    if problems:
        raise ValidationError(problems)
    _update_row("cpd_records", "record_id", cur.record_id, {
        "evaluation_rating": c["evaluation_rating"], "evaluation_notes": c["evaluation_notes"],
        "impact_on_practice": c["impact_on_practice"], "status": "Completed"})
    with database.connect() as conn:
        _audit(conn, "cpd", "evaluate", actor, cur.record_id, cur.staff_id,
               rating=c["evaluation_rating"])
    return get_record(cur.record_id)


def file_certificate(record_id: int, *, actor: Principal, ref: str | None = None) -> Record:
    cur = get_record(record_id, actor=actor)
    _self_or_editor(actor, cur, "cpd_certificate")
    _update_row("cpd_records", "record_id", cur.record_id, {
        "certificate_received": True, "certificate_filed": True,
        "certificate_ref": _text(ref, 60) or cur.certificate_ref})
    with database.connect() as conn:
        _audit(conn, "cpd", "certificate", actor, cur.record_id, cur.staff_id)
    return get_record(cur.record_id)


def set_record_status(record_id: int, status: str, *, actor: Principal) -> Record:
    return update_record(record_id, {"status": status}, actor=actor)


def delete_record(record_id: int, *, actor: Principal) -> bool:
    cur = get_record(record_id)
    _require_editor(actor, "cpd_delete", cur.record_id)
    with database.connect() as conn:
        conn.execute("DELETE FROM cpd_records WHERE record_id = ?", (cur.record_id,))
        _audit(conn, "cpd", "delete", actor, cur.record_id, cur.staff_id)
    return True


def cpd_log(staff_id: int, *, actor: Principal) -> dict[str, Any]:
    """A person's CPD: everything attended, hours and cost by year."""
    m = SD.get(staff_id)
    rows = [r for r in list_records(actor=actor, staff_id=m.staff_id) if r.status in DONE]
    if not rows and not is_editor(actor) and _me_id(actor) != m.staff_id and \
            m.staff_id not in _appraisees(actor):
        _deny(actor, "cpd_log", m.staff_code, "That CPD log isn't yours to see.")
    by_year: dict[str, dict[str, float]] = {}
    for r in rows:
        y = by_year.setdefault(r.academic_year, {"courses": 0, "hours": 0.0, "cost": 0.0})
        y["courses"] += 1
        y["hours"] += r.hours_completed or 0
        y["cost"] += r.cost or 0
    return {"member": m, "records": rows, "by_year": by_year,
            "hours": sum(r.hours_completed or 0 for r in rows)}


# ── CPD budget ───────────────────────────────────────────────────────

def set_budget(academic_year: str | None, amount: Any, *, actor: Principal) -> dict[str, Any]:
    _require_editor(actor, "budget")
    problems: list[str] = []
    year = _year(academic_year, problems)
    amt = _number(amount, "Budget", problems, 0, 10_000_000)
    if amt is None and not problems:
        problems.append("Budget is required")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("INSERT INTO cpd_budgets (academic_year, amount, set_by) VALUES (?, ?, ?) "
                     "ON CONFLICT (academic_year) DO UPDATE SET amount = excluded.amount, "
                     "set_by = excluded.set_by, set_at = datetime('now')",
                     (year, amt, actor.username))
        _audit(conn, "budget", "set", actor, None, None, year=year, amount=amt)
    return budget(year)


def budget(academic_year: str | None = None) -> dict[str, Any]:
    """{"year", "available" (None if not set), "used", "requested", "remaining"}."""
    year = academic_year or current_year()
    with database.connect() as conn:
        r = conn.execute("SELECT amount FROM cpd_budgets WHERE academic_year = ?",
                         (year,)).fetchone()
        rows = [_make(Record, x) for x in conn.execute(_RC_SELECT)]
    rows = [x for x in rows if x.academic_year == year]
    used = round(sum(x.cost or 0 for x in rows if x.status in SPENDING), 2)
    requested = round(sum(x.cost or 0 for x in rows if x.status == "Requested"), 2)
    available = float(r[0]) if r else None
    return {"year": year, "available": available, "used": used, "requested": requested,
            "remaining": None if available is None else round(available - used, 2)}


def budget_warning(r: Record) -> str | None:
    if not r.cost:
        return None
    b = budget(r.academic_year)
    if b["available"] is None:
        return None
    if b["used"] + r.cost > b["available"]:
        return (f"Approving £{r.cost:,.2f} takes the {b['year']} CPD budget over: "
                f"£{b['used']:,.2f} of £{b['available']:,.2f} already used")
    return None


# ── Statutory training ───────────────────────────────────────────────

def expiry_for(training_type: str, completed_on: str) -> str | None:
    months = TRAINING_TYPES.get(training_type)
    if not months:
        return None
    d = _dt.date.fromisoformat(completed_on)
    y, mth = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, mth + 1
    for day in (d.day, 30, 29, 28):
        try:
            return _dt.date(year, month, day).isoformat()
        except ValueError:
            continue
    return None  # pragma: no cover


def get_training(training_id: int) -> Training:
    with database.connect() as conn:
        r = conn.execute(_TR_SELECT + " WHERE t.training_id = ?", (int(training_id),)).fetchone()
    if r is None:
        raise NotFound(f"No training record {training_id}")
    return _make(Training, r)


def list_training(*, actor: Principal, staff_id: int | None = None,
                  training_type: str | None = None) -> list[Training]:
    """Editors see everyone's; others their own."""
    _require_staff(actor, "training")
    sql, params = _TR_SELECT + " WHERE 1=1", []
    if not is_editor(actor):
        me = _me_id(actor)
        if me is None:
            return []
        staff_id = me
    if staff_id is not None:
        sql += " AND t.staff_id = ?"
        params.append(int(staff_id))
    if training_type:
        sql += " AND t.training_type = ?"
        params.append(training_type)
    with database.connect() as conn:
        return [_make(Training, r) for r in conn.execute(
            sql + " ORDER BY s.last_name COLLATE NOCASE, t.training_type, t.completed_on DESC",
            params)]


T_FIELDS = ("training_type", "completed_on", "expires_on", "provider", "certificate_ref",
            "notes")


def _clean_training(data: dict[str, Any], current: Training | None
                    ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in T_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in T_FIELDS})
    out: dict[str, Any] = {
        "training_type": _choice(merged.get("training_type"), tuple(TRAINING_TYPES), "Training",
                                 problems, None),
        "completed_on": _date(merged.get("completed_on"), "Completed on", problems),
        "provider": _text(merged.get("provider"), 120),
        "certificate_ref": _text(merged.get("certificate_ref"), 60),
        "notes": _text(merged.get("notes"), 2000)}
    if not out["training_type"] and not problems:
        problems.append("Choose the training")
    if not out["completed_on"] and not any(p.startswith("Completed") for p in problems):
        problems.append("Completed on is required")
    if out["completed_on"] and out["completed_on"] > _today().isoformat():
        problems.append("Completed on can't be in the future")
    exp = _date(merged.get("expires_on"), "Expires on", problems)
    if "completed_on" in data and "expires_on" not in data and current is not None:
        exp = None  # a new completion date works the expiry out again
    if exp is None and out["completed_on"] and out["training_type"]:
        exp = expiry_for(out["training_type"], out["completed_on"])
    if exp and out["completed_on"] and exp <= out["completed_on"]:
        problems.append("Expires on must be after it was completed")
    out["expires_on"] = exp
    return out, problems


def add_training(data: dict[str, Any], *, actor: Principal) -> Training:
    _require_editor(actor, "training_add")
    problems: list[str] = []
    m = _staff(data.get("staff_id") or data.get("staff"), "Staff", problems)
    if m is None and not problems:
        problems.append("Staff is required")
    c, more = _clean_training(data, None)
    problems += more
    if problems or m is None:
        raise ValidationError(problems)
    with database.connect() as conn:
        tid = conn.execute(
            f"INSERT INTO statutory_training (staff_id, {', '.join(T_FIELDS)}, recorded_by) "  # nosec B608 - fixed
            f"VALUES (?, {', '.join('?' * len(T_FIELDS))}, ?)",
            (m.staff_id, *(c[k] for k in T_FIELDS), actor.username)).lastrowid
        _audit(conn, "training", "create", actor, tid, m.staff_id, type=c["training_type"])
    activity_log.record("appraisals.training", target=tid, principal=actor)
    return get_training(tid)


def update_training(training_id: int, changes: dict[str, Any], *, actor: Principal) -> Training:
    cur = get_training(training_id)
    _require_editor(actor, "training_update", cur.training_id)
    c, problems = _clean_training(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = {k: c[k] for k in T_FIELDS if c[k] != getattr(cur, k)}
    _update_row("statutory_training", "training_id", cur.training_id, changed, stamp=None)
    if changed:
        with database.connect() as conn:
            _audit(conn, "training", "update", actor, cur.training_id, cur.staff_id,
                   fields=sorted(changed))
    return get_training(cur.training_id)


def delete_training(training_id: int, *, actor: Principal) -> bool:
    cur = get_training(training_id)
    _require_editor(actor, "training_delete", cur.training_id)
    with database.connect() as conn:
        conn.execute("DELETE FROM statutory_training WHERE training_id = ?", (cur.training_id,))
        _audit(conn, "training", "delete", actor, cur.training_id, cur.staff_id)
    return True


def training_due(*, actor: Principal, within_days: int = DUE_SOON_DAYS) -> list[dict[str, Any]]:
    """What is missing (required training never done), overdue (latest record
    expired) or due soon, for current staff - everyone for editors, else
    yourself. Most urgent first."""
    _require_staff(actor, "training_due")
    if is_editor(actor):
        people = SD.list_staff()
    else:
        me = SD.me(actor)
        people = [me] if me and not me.is_leaver else []
    latest: dict[tuple[int, str], Training] = {}
    for t in list_training(actor=actor):
        key = (t.staff_id, t.training_type)
        if key not in latest or t.completed_on > latest[key].completed_on:
            latest[key] = t
    today = _today()
    soon = (today + _dt.timedelta(days=within_days)).isoformat()
    out = []
    for m in people:
        types = set(REQUIRED_TRAINING) | {k for (sid, k) in latest if sid == m.staff_id}
        for kind in sorted(types):
            t = latest.get((m.staff_id, kind))
            if t is None:
                state, due = "Missing", None
            elif t.expires_on and t.expires_on < today.isoformat():
                state, due = "Overdue", t.expires_on
            elif t.expires_on and t.expires_on <= soon:
                state, due = "Due soon", t.expires_on
            else:
                continue
            out.append({"staff_id": m.staff_id, "staff": m.full_name,
                        "staff_code": m.staff_code, "training_type": kind, "state": state,
                        "last_completed": t.completed_on if t else None, "expires_on": due})
    order = {"Overdue": 0, "Missing": 1, "Due soon": 2}
    return sorted(out, key=lambda d: (order[d["state"]], d["expires_on"] or "", d["staff"]))


# ── Summary and export ───────────────────────────────────────────────

def summary(*, actor: Principal, academic_year: str | None = None) -> dict[str, Any]:
    """The old Appraisals and CPD summaries, for what *actor* can see."""
    year = academic_year or current_year()
    aps = list_appraisals(actor=actor, academic_year=year)
    recs = list_records(actor=actor, academic_year=year)
    acts = list_activities()
    return {
        "year": year, "appraisals": len(aps), "open": sum(1 for a in aps if a.is_open),
        "mid_year_overdue": sum(1 for a in aps if a.mid_year_overdue),
        "completed": sum(1 for a in aps if a.status in ("Completed", "Closed")),
        "by_status": dict(Counter(a.status for a in aps).most_common()),
        "by_grade": dict(Counter(a.grade_label for a in aps if a.overall_grade).most_common()),
        "pay": dict(Counter(a.pay_progression for a in aps).most_common()),
        "no_appraiser": sum(1 for a in aps if a.appraiser_id is None),
        "activities": len(acts), "upcoming": sum(1 for a in acts if a.is_upcoming),
        "records": len(recs), "requests": sum(1 for r in recs if r.status == "Requested"),
        "attended": sum(1 for r in recs if r.status in DONE),
        "hours": round(sum(r.hours_completed or 0 for r in recs if r.status in DONE), 1),
        "awaiting_cert": sum(1 for r in recs if r.awaiting_certificate),
        "average_rating": round(sum(r.evaluation_rating for r in recs if r.evaluation_rating)
                                / max(1, sum(1 for r in recs if r.evaluation_rating)), 2),
        "budget": budget(year),
        "training_overdue": sum(1 for d in training_due(actor=actor)
                                if d["state"] in ("Overdue", "Missing"))}


def export_csv(path: str | Path, what: str = "appraisals", *, actor: Principal,
               **filters: Any) -> int:
    """*what*: appraisals, cpd or training - only what *actor* may see."""
    _require_staff(actor, "export")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if what == "cpd":
            rows: list[Any] = list_records(actor=actor, **filters)
            w.writerow(["id", "staff_code", "staff", "title", "provider", "start", "end", "cost",
                        "cover_needed", "status", "attended", "hours", "rating",
                        "certificate_filed"])
            for r in rows:
                w.writerow([r.record_id, r.staff_code, _safe(r.staff_name), _safe(r.title),
                            _safe(r.provider), r.start_date or "", r.end_date or "",
                            r.cost if r.cost is not None else "", "yes" if r.cover_needed
                            else "no", r.status, r.attended_on or "",
                            r.hours_completed if r.hours_completed is not None else "",
                            r.evaluation_rating or "", "yes" if r.certificate_filed else "no"])
        elif what == "training":
            rows = list_training(actor=actor, **filters)
            w.writerow(["id", "staff", "training", "completed", "expires", "provider",
                        "certificate"])
            for t in rows:
                w.writerow([t.training_id, _safe(t.staff_name), t.training_type, t.completed_on,
                            t.expires_on or "", _safe(t.provider), _safe(t.certificate_ref)])
        else:
            rows = list_appraisals(actor=actor, **filters)
            w.writerow(["id", "staff_code", "staff", "year", "appraiser", "status",
                        "objectives_set", "mid_year", "end_year", "grade", "outcome", "pay",
                        "objectives"])
            for a in rows:
                w.writerow([a.appraisal_id, a.staff_code, _safe(a.staff_name), a.academic_year,
                            _safe(a.appraiser_name), a.status, a.objectives_set_on or "",
                            a.mid_year_review_on or "", a.end_year_review_on or "",
                            a.overall_grade or "", a.outcome or "", a.pay_progression,
                            a.objectives])
    activity_log.record("appraisals.export", principal=actor, rows=len(rows), what=what)
    return len(rows)
