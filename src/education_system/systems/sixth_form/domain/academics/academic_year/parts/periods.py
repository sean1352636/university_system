"""Day periods (the bell schedule) and a day's shape.

Split out of ``academic_year.py``, which re-exports every name here and keeps
the database/RBAC/audit state (DB_PATH, CURRENT_ACTOR, ...). Import from
``academic_year``, not from here.
"""

from __future__ import annotations

from typing import Any
import datetime as _dt

from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    _audit,
    _check_write,
    _connect,
    init_db,
    _row_period,
    WEEKDAY_NAMES,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.models import (
    Period,
    _period_to_dict,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.validation import (
    _require,
    _validate_date,
    _validate_time,
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.years import (
    get_year,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.notes import (
    list_notes,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.events import (
    events_on,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.teaching_days import (
    _break_ranges,
    _day_weight,
    find_term_on,
    is_break,
    _non_teaching_term_ranges,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.weeks import (
    cycle_week_label,
    cycle_week_on,
)


# ── Periods (the shape of a teaching day) ─────────────────────────

def _validate_period_payload(payload: dict[str, Any]
                              ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    yid_raw = payload.get("year_id")
    if yid_raw in (None, ""):
        raise ValidationError("Year is required")
    try:
        yid = int(yid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Year id must be a number") from None
    year = get_year(yid)
    if year is None:
        raise ValidationError(f"No academic year #{yid}")
    out["year_id"] = yid

    name = _require(payload.get("name"), "Period name").strip()
    if len(name) > 32:
        raise ValidationError("Period name must be 32 chars or fewer")
    out["name"] = name

    wd = payload.get("weekday")
    if wd in (None, ""):
        raise ValidationError("Weekday is required (0=Mon … 6=Sun)")
    if isinstance(wd, str) and not wd.strip().lstrip("-").isdigit():
        match = [i for i, n in enumerate(WEEKDAY_NAMES)
                  if n.lower() == wd.strip().lower()]
        if not match:
            raise ValidationError(
                f"Weekday must be 0-6 or one of: "
                f"{', '.join(WEEKDAY_NAMES)}")
        wd = match[0]
    try:
        wd = int(wd)
    except (TypeError, ValueError):
        raise ValidationError("Weekday must be a number 0-6") from None
    if not (0 <= wd <= 6):
        raise ValidationError("Weekday must be 0 (Mon) … 6 (Sun)")
    out["weekday"] = wd

    out["start_time"] = _validate_time(payload.get("start_time"),
                                          "Start time")
    out["end_time"] = _validate_time(payload.get("end_time"),
                                        "End time")
    if out["end_time"] <= out["start_time"]:
        raise ValidationError("End time must be after start time")

    cw = payload.get("cycle_week")
    if cw in (None, ""):
        out["cycle_week"] = None
    else:
        try:
            cw = int(cw)
        except (TypeError, ValueError):
            raise ValidationError("Cycle week must be a number") from None
        if not (1 <= cw <= year.cycle_weeks):
            raise ValidationError(
                f"Cycle week must be 1..{year.cycle_weeks} for this year")
        out["cycle_week"] = cw

    out["is_teaching"] = bool(payload.get("is_teaching", True))
    try:
        out["sort_order"] = int(payload.get("sort_order") or 0)
    except (TypeError, ValueError):
        raise ValidationError("Sort order must be a number") from None
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


def _assert_no_period_clash(p: dict[str, Any], *,
                             exclude_period_id: int | None = None
                             ) -> None:
    """Two periods on the same weekday and cycle week must not share
    wall-clock time."""
    for other in list_periods(year_id=p["year_id"],
                                weekday=p["weekday"]):
        if exclude_period_id is not None \
                and other.period_id == exclude_period_id:
            continue
        # NULL cycle_week means "every week", so it clashes with all.
        if (other.cycle_week is not None
                and p["cycle_week"] is not None
                and other.cycle_week != p["cycle_week"]):
            continue
        if (other.start_time < p["end_time"]
                and p["start_time"] < other.end_time):
            raise ValidationError(
                f"Clashes with {other.name!r} "
                f"({other.start_time}-{other.end_time}) on "
                f"{WEEKDAY_NAMES[p['weekday']]}")


def create_period(payload: dict[str, Any]) -> Period:
    init_db()
    _check_write()
    p = _validate_period_payload(payload)
    _assert_no_period_clash(p)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO academic_periods
                   (year_id, name, weekday, start_time, end_time,
                    cycle_week, is_teaching, sort_order, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["year_id"], p["name"], p["weekday"], p["start_time"],
             p["end_time"], p["cycle_week"],
             1 if p["is_teaching"] else 0, p["sort_order"], p["notes"]))
        new_id = cur.lastrowid
        _audit(conn, entity="period", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_period(new_id)
    assert out is not None
    return out


def get_period(period_id: int, *,
                include_deleted: bool = False) -> Period | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_periods "
            f"WHERE period_id = ?{extra}", (period_id,)).fetchone()
        return _row_period(r) if r else None


def list_periods(*, year_id: int | None = None,
                  weekday: int | None = None,
                  cycle_week: int | None = None,
                  teaching_only: bool = False,
                  include_deleted: bool = False) -> list[Period]:
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if weekday is not None:
        clauses.append("weekday = ?")
        args.append(int(weekday))
    if cycle_week is not None:
        # NULL means "every week", so it matches any requested week.
        clauses.append("(cycle_week IS NULL OR cycle_week = ?)")
        args.append(int(cycle_week))
    if teaching_only:
        clauses.append("is_teaching = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_periods {where} "
           "ORDER BY weekday ASC, sort_order ASC, start_time ASC")
    with _connect() as conn:
        return [_row_period(r) for r in conn.execute(sql, args).fetchall()]


def update_period(period_id: int, payload: dict[str, Any]) -> Period:
    init_db()
    _check_write()
    existing = get_period(period_id)
    if existing is None:
        raise ValidationError(f"No period #{period_id}")
    current = _period_to_dict(existing)
    merged = {k: payload.get(k, current[k]) for k in current}
    merged["year_id"] = existing.year_id
    p = _validate_period_payload(merged)
    _assert_no_period_clash(p, exclude_period_id=period_id)
    with _connect() as conn:
        conn.execute(
            """UPDATE academic_periods SET
                   name = ?, weekday = ?, start_time = ?, end_time = ?,
                   cycle_week = ?, is_teaching = ?, sort_order = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE period_id = ?""",
            (p["name"], p["weekday"], p["start_time"], p["end_time"],
             p["cycle_week"], 1 if p["is_teaching"] else 0,
             p["sort_order"], p["notes"], period_id))
        _audit(conn, entity="period", entity_id=period_id,
                 action="update", old=current, new=p)
        conn.commit()
    out = get_period(period_id)
    assert out is not None
    return out


def delete_period(period_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_period(period_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_periods WHERE period_id = ?",
                (period_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_periods SET "
                "deleted_at = datetime('now'), "
                "updated_at = datetime('now') WHERE period_id = ?",
                (period_id,))
        if cur.rowcount:
            _audit(conn, entity="period", entity_id=period_id,
                     action="hard-delete" if hard else "delete",
                     old=_period_to_dict(existing))
            conn.commit()
            return True
        return False


def restore_period(period_id: int) -> Period:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_periods SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE period_id = ?",
            (period_id,))
        _audit(conn, entity="period", entity_id=period_id,
                 action="restore")
        conn.commit()
    out = get_period(period_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No period #{period_id}")
    return out


def periods_on(year_id: int, date_iso: str, *,
                teaching_only: bool = False) -> list[Period]:
    """The day's shape: periods for that weekday and cycle week.

    Returns [] on a weekend with no periods defined, or on a day the
    college is closed (a full-day break).
    """
    s = _validate_date(date_iso, "Date")
    d = _dt.date.fromisoformat(s)
    cw = cycle_week_on(year_id, s)
    return list_periods(year_id=year_id, weekday=d.weekday(),
                          cycle_week=cw, teaching_only=teaching_only)


def day_shape(year_id: int, date_iso: str, *,
               group_label: str | None = None) -> dict[str, Any]:
    """Everything about one day: term, break, cycle week, periods,
    events. The single call an attendance or timetable screen needs.
    """
    s = _validate_date(date_iso, "Date")
    brk = is_break(year_id, s, group_label=group_label)
    term = find_term_on(year_id, s, group_label=group_label)
    weight = _day_weight(
        s, _break_ranges(year_id, group_label=group_label),
        _non_teaching_term_ranges(year_id, group_label=group_label),
        half_days=True)
    periods = [] if weight == 0 else periods_on(year_id, s)
    if brk and brk.am_pm in ("AM", "PM"):
        # Half day: keep only the sessions that still run.
        periods = [p for p in periods
                    if (p.start_time >= "12:00") == (brk.am_pm == "AM")]
    return {
        "date": s,
        "term": term.name if term else None,
        "term_kind": term.kind if term else None,
        "break": brk.name if brk else None,
        "break_type": brk.type if brk else None,
        "am_pm": brk.am_pm if brk else None,
        "cycle_week": cycle_week_on(year_id, s),
        "cycle_label": cycle_week_label(year_id, s),
        "periods": periods,
        "events": events_on(year_id, s, group_label=group_label),
        "notes": list_notes(year_id=year_id, pinned_only=True),
        "day_weight": (weight
                       if _dt.date.fromisoformat(s).weekday() < 5
                       else 0.0),
        "is_teaching_day": bool(
            _dt.date.fromisoformat(s).weekday() < 5 and weight > 0),
    }
