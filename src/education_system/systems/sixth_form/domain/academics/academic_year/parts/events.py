"""Calendar events and their repeat occurrences.

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
    DEFAULT_EVENT_KIND,
    EVENT_KINDS,
    init_db,
    logger,
    MAX_OCCURRENCES,
    REPEAT_RULES,
    _row_event,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.models import (
    CalendarEvent,
    _event_to_dict,
    EventOccurrence,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.validation import (
    _require,
    _validate_date,
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.years import (
    get_year,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.year_groups import (
    _validate_group_label,
)


# ── Events ────────────────────────────────────────────────────────

def _validate_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
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

    out["name"] = _require(payload.get("name"), "Name").strip()
    kind = (payload.get("kind") or DEFAULT_EVENT_KIND).strip()
    if kind not in EVENT_KINDS:
        raise ValidationError(
            f"Event kind must be one of: {', '.join(EVENT_KINDS)}")
    out["kind"] = kind

    s = _validate_date(payload.get("date"), "Date")
    e = _validate_date(payload.get("end_date"), "End date",
                          required=False)
    if e is not None and e < s:
        raise ValidationError("End date cannot be before start date")
    if s < year.start_date or s > year.end_date:
        raise ValidationError(
            f"Event must fall inside the year "
            f"({year.start_date} → {year.end_date})")
    if e is not None and e > year.end_date:
        raise ValidationError(
            f"Event must end inside the year (by {year.end_date})")
    out["date"], out["end_date"] = s, e

    out["group_label"] = _validate_group_label(
        yid, payload.get("group_label"))

    for field_name, label, limit in (
        ("owner", "Owner", 64),
        ("department", "Department", 64),
        ("location", "Location", 96),
    ):
        raw = payload.get(field_name)
        val = str(raw).strip() if raw not in (None, "") else None
        if val is not None and len(val) > limit:
            raise ValidationError(f"{label} must be {limit} chars or fewer")
        out[field_name] = val or None

    cap = payload.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            cap = int(cap)
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a number") from None
        if cap < 0:
            raise ValidationError("Capacity cannot be negative")
        out["capacity"] = cap

    # ── Recurrence ────────────────────────────────────────────────
    rule = payload.get("repeat_rule")
    rule = str(rule).strip().upper() if rule not in (None, "") else None
    if rule is not None and rule not in REPEAT_RULES:
        raise ValidationError(
            f"Repeat rule must be one of: {', '.join(REPEAT_RULES)}")
    out["repeat_rule"] = rule

    interval = payload.get("repeat_interval", 1)
    if interval in (None, ""):
        interval = 1
    try:
        interval = int(interval)
    except (TypeError, ValueError):
        raise ValidationError("Repeat interval must be a number") from None
    if interval < 1:
        raise ValidationError("Repeat interval must be at least 1")
    out["repeat_interval"] = interval

    until = _validate_date(payload.get("repeat_until"), "Repeat until",
                              required=False)
    if rule is None:
        if until is not None:
            raise ValidationError(
                "Repeat until needs a repeat rule")
        out["repeat_until"] = None
    else:
        # An open-ended series stops at the end of the year.
        if until is None:
            until = year.end_date
        if until < s:
            raise ValidationError(
                "Repeat until cannot be before the first date")
        if until > year.end_date:
            raise ValidationError(
                f"Repeat until must fall inside the year "
                f"(by {year.end_date})")
        out["repeat_until"] = until

    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


_EVENT_COLUMNS = (
    "year_id", "name", "kind", "date", "end_date", "notes",
    "group_label", "owner", "department", "location", "capacity",
    "repeat_rule", "repeat_interval", "repeat_until",
)


def create_event(payload: dict[str, Any]) -> CalendarEvent:
    init_db()
    _check_write()
    p = _validate_event_payload(payload)
    cols = ", ".join(_EVENT_COLUMNS)
    marks = ", ".join("?" for _ in _EVENT_COLUMNS)
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO academic_events ({cols}) VALUES ({marks})",
            tuple(p[c] for c in _EVENT_COLUMNS))
        new_id = cur.lastrowid
        _audit(conn, entity="event", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_event(new_id)
    assert out is not None
    logger.info("Created event #%d %r (%s) in year #%d",
                new_id, p["name"], p["kind"], p["year_id"])
    return out


def update_event(event_id: int, payload: dict[str, Any]) -> CalendarEvent:
    init_db()
    _check_write()
    existing = get_event(event_id)
    if existing is None:
        raise ValidationError(f"No event #{event_id}")
    current = _event_to_dict(existing)
    merged = {c: payload.get(c, current.get(c)) for c in _EVENT_COLUMNS}
    merged["year_id"] = existing.year_id  # events don't move years
    merged["notes"] = payload.get("notes", existing.notes)
    p = _validate_event_payload(merged)
    sets = ", ".join(f"{c} = ?" for c in _EVENT_COLUMNS
                      if c != "year_id")
    with _connect() as conn:
        conn.execute(
            f"UPDATE academic_events SET {sets}, "
            f"updated_at = datetime('now') WHERE event_id = ?",
            tuple(p[c] for c in _EVENT_COLUMNS if c != "year_id")
            + (event_id,))
        _audit(conn, entity="event", entity_id=event_id,
                 action="update", old=current, new=p)
        conn.commit()
    out = get_event(event_id)
    assert out is not None
    logger.info("Updated event #%d %r", event_id, out.name)
    return out


def get_event(event_id: int) -> CalendarEvent | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_events "
            "WHERE event_id = ? AND deleted_at IS NULL",
            (event_id,)).fetchone()
        return _row_event(r) if r else None


def list_events(*, year_id: int | None = None,
                 kind: str | None = None,
                 group_label: str | None = None,
                 include_shared: bool = True,
                 owner: str | None = None,
                 department: str | None = None) -> list[CalendarEvent]:
    init_db()
    clauses = ["deleted_at IS NULL"]
    args: list[Any] = []
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if kind is not None:
        if kind not in EVENT_KINDS:
            raise ValidationError(
                f"Event kind must be one of: {', '.join(EVENT_KINDS)}")
        clauses.append("kind = ?")
        args.append(kind)
    if group_label is not None:
        if include_shared:
            clauses.append("(group_label IS NULL OR group_label = ?)")
        else:
            clauses.append("group_label = ?")
        args.append(group_label)
    if owner is not None:
        clauses.append("owner = ?")
        args.append(owner)
    if department is not None:
        clauses.append("department = ?")
        args.append(department)
    where = " AND ".join(clauses)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM academic_events WHERE {where} "
            "ORDER BY date ASC, event_id ASC", args).fetchall()
    return [_row_event(r) for r in rows]


def delete_event(event_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_event(event_id)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_events WHERE event_id = ?",
                (event_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_events SET "
                "deleted_at = datetime('now') WHERE event_id = ?",
                (event_id,))
        if cur.rowcount:
            _audit(conn, entity="event", entity_id=event_id,
                     action="hard-delete" if hard else "delete")
            conn.commit()
            return True
        return False


# ── Recurring events ──────────────────────────────────────────────

def _add_months(d: _dt.date, months: int) -> _dt.date:
    """Shift by whole months, clamping to the end of short months
    (31 Jan + 1 month → 28/29 Feb)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = [31,
                 29 if (year % 4 == 0 and (year % 100 != 0
                                             or year % 400 == 0)) else 28,
                 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return _dt.date(year, month, min(d.day, last_day))


def expand_event_occurrences(
    event: CalendarEvent, *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[EventOccurrence]:
    """Materialise a (possibly recurring) event into occurrences.

    A non-recurring event yields exactly itself. Recurring events
    repeat every ``repeat_interval`` days/weeks/months up to and
    including ``repeat_until``, preserving the event's duration.
    Capped at ``MAX_OCCURRENCES``.
    """
    try:
        first = _dt.date.fromisoformat(event.date)
    except ValueError:
        return []
    try:
        last = _dt.date.fromisoformat(event.end_date or event.date)
    except ValueError:
        last = first
    span = max(0, (last - first).days)

    if not event.repeat_rule:
        starts = [first]
    else:
        until_iso = event.repeat_until or event.date
        try:
            until = _dt.date.fromisoformat(until_iso)
        except ValueError:
            until = first
        rule = event.repeat_rule.upper()
        step = max(1, event.repeat_interval)
        starts, cur, guard = [], first, 0
        while cur <= until and guard < MAX_OCCURRENCES:
            starts.append(cur)
            guard += 1
            if rule == "DAILY":
                cur = cur + _dt.timedelta(days=step)
            elif rule == "WEEKLY":
                cur = cur + _dt.timedelta(weeks=step)
            elif rule == "MONTHLY":
                cur = _add_months(first, step * guard)
            else:  # unknown rule stored by an older version
                break
        if guard >= MAX_OCCURRENCES:
            logger.warning(
                "Event #%s hit the %d-occurrence cap",
                event.event_id, MAX_OCCURRENCES)

    out: list[EventOccurrence] = []
    for s in starts:
        e = s + _dt.timedelta(days=span)
        s_iso, e_iso = s.isoformat(), e.isoformat()
        if date_from and e_iso < date_from:
            continue
        if date_to and s_iso > date_to:
            continue
        out.append(EventOccurrence(event=event, date=s_iso,
                                     end_date=e_iso))
    return out


def events_on(year_id: int, date_iso: str, *,
               group_label: str | None = None) -> list[EventOccurrence]:
    """Every event occurrence covering ``date_iso``."""
    s = _validate_date(date_iso, "Date")
    out: list[EventOccurrence] = []
    for ev in list_events(year_id=year_id, group_label=group_label):
        out.extend(expand_event_occurrences(ev, date_from=s, date_to=s))
    return sorted(out, key=lambda o: (o.date, o.event.event_id))


def events_between(year_id: int, date_from: str, date_to: str, *,
                    group_label: str | None = None,
                    kind: str | None = None) -> list[EventOccurrence]:
    """Every event occurrence overlapping [from, to], expanded."""
    df = _validate_date(date_from, "From")
    dt = _validate_date(date_to, "To")
    out: list[EventOccurrence] = []
    for ev in list_events(year_id=year_id, kind=kind,
                            group_label=group_label):
        out.extend(expand_event_occurrences(ev, date_from=df,
                                              date_to=dt))
    return sorted(out, key=lambda o: (o.date, o.event.event_id))
