"""Recurring events for the Sixth Form Calendar.

Sibling to :mod:`calendar`. Tutor time, assemblies and lesson blocks
happen every week, and today each occurrence is a hand-typed row —
which is why the calendar has terms where tutor time simply stops
appearing after the week somebody got bored.

A *series* holds the rule (every Monday and Wednesday until the end of
term) and a template of event fields. Occurrences are *materialised*
into ordinary :mod:`calendar` rows, linked back to the series, so every
existing view, filter, export and API sees them with no special cases.
Materialisation is idempotent: a date already claimed is skipped, so
the sweep can run at every launch.

Two escape hatches keep a series honest against real life:

* **Exceptions** — dates the rule skips (an INSET day, a snow day).
  Adding one archives the occurrence if it was already materialised.
* **Detaching** — one occurrence stops following the series. Its link
  row is kept so the date stays claimed; template pushes and pruning
  leave it alone from then on. This is "edit just this one".

"Edit the whole series" is :func:`update_series` followed by
:func:`sync`, which pushes the template onto future occurrences that
still follow the series and archives ones whose date no longer matches
the rule.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_CALENDAR_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

DAILY: str = "Daily"
WEEKLY: str = "Weekly"
FORTNIGHTLY: str = "Fortnightly"
MONTHLY: str = "Monthly"
FREQUENCIES: tuple[str, ...] = (DAILY, WEEKLY, FORTNIGHTLY, MONTHLY)
DEFAULT_FREQUENCY: str = WEEKLY

WEEKDAYS: tuple[str, ...] = (
    "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun",
)
_WEEKDAY_INDEX: dict[str, int] = {d: i for i, d in enumerate(WEEKDAYS)}

# A series without an end is capped rather than infinite. 366 covers
# "daily for a school year"; anything needing more is two series.
MAX_OCCURRENCES: int = 366

# How far ahead the launch-time sweep keeps every active series
# materialised. Half a term past the visible horizon is enough; a
# whole year of tutor time up front just makes the All Events tab lie.
DEFAULT_HORIZON_DAYS: int = 120

# Template fields an occurrence inherits. Dates are the rule's job and
# status is the occurrence's own business once it exists.
_TEMPLATE_FIELDS: tuple[str, ...] = (
    "title", "event_type", "description", "start_time", "end_time",
    "all_day", "location", "organiser", "audience", "capacity",
    "rsvp_required", "cost", "notes", "department", "visibility",
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_series (
    series_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    frequency   TEXT NOT NULL DEFAULT 'Weekly',
    byday       TEXT,
    bymonthday  INTEGER,
    span_days   INTEGER NOT NULL DEFAULT 1,
    start_date  TEXT NOT NULL,
    until_date  TEXT,
    max_count   INTEGER,
    template    TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    created_by  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calendar_series_exceptions (
    exception_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id    INTEGER NOT NULL,
    date         TEXT NOT NULL,
    reason       TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(series_id, date)
);

CREATE TABLE IF NOT EXISTS calendar_series_occurrences (
    link_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id       INTEGER NOT NULL,
    event_id        INTEGER NOT NULL,
    occurrence_date TEXT NOT NULL,
    detached        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(series_id, occurrence_date)
);

CREATE INDEX IF NOT EXISTS idx_cal_series_active
    ON calendar_series(active);
CREATE INDEX IF NOT EXISTS idx_cal_occ_series
    ON calendar_series_occurrences(series_id);
CREATE INDEX IF NOT EXISTS idx_cal_occ_event
    ON calendar_series_occurrences(event_id);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Series:
    series_id: int
    title: str
    frequency: str
    byday: tuple[str, ...]
    bymonthday: int | None
    span_days: int
    start_date: str
    until_date: str | None
    max_count: int | None
    template: dict[str, Any]
    active: bool
    created_by: str | None
    created_at: str
    updated_at: str

    @property
    def rule_label(self) -> str:
        if self.frequency == DAILY:
            head = "Every day"
        elif self.frequency in (WEEKLY, FORTNIGHTLY):
            days = "/".join(self.byday) or "?"
            head = (f"Every {days}" if self.frequency == WEEKLY
                    else f"Every other {days}")
        else:
            head = f"Monthly on day {self.bymonthday}"
        tail = (f" until {self.until_date}" if self.until_date
                else (f" ({self.max_count}x)" if self.max_count else ""))
        return head + tail


@dataclass
class Occurrence:
    """One date a series has claimed, and the event living there."""

    link_id: int
    series_id: int
    event_id: int
    occurrence_date: str
    detached: bool


@dataclass
class SyncResult:
    """What one materialise/sync pass did."""

    created: int = 0
    updated: int = 0
    pruned: int = 0
    skipped: int = 0
    events: list[core.Event] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.created} created, {self.updated} updated, "
                f"{self.pruned} pruned, {self.skipped} skipped")


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Calendar series schema ready at %s", DB_PATH)
    _DB_READY = True


def _row_series(r: sqlite3.Row) -> Series:
    byday = tuple(d for d in (r["byday"] or "").split(",") if d)
    try:
        template = json.loads(r["template"])
    except (TypeError, ValueError):
        template = {}
    return Series(
        series_id=r["series_id"], title=r["title"],
        frequency=r["frequency"], byday=byday,
        bymonthday=r["bymonthday"], span_days=r["span_days"],
        start_date=r["start_date"], until_date=r["until_date"],
        max_count=r["max_count"], template=template,
        active=bool(r["active"]), created_by=r["created_by"],
        created_at=r["created_at"], updated_at=r["updated_at"])


def _row_occurrence(r: sqlite3.Row) -> Occurrence:
    return Occurrence(
        link_id=r["link_id"], series_id=r["series_id"],
        event_id=r["event_id"], occurrence_date=r["occurrence_date"],
        detached=bool(r["detached"]))


# ── Validation ──────────────────────────────────────────────────────

def _validate_byday(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
    else:
        parts = [str(p).strip() for p in value]
    out: list[str] = []
    for p in parts:
        name = p[:3].capitalize()
        if name not in _WEEKDAY_INDEX:
            raise ValidationError(
                f"Weekday must be one of: {', '.join(WEEKDAYS)}")
        if name not in out:
            out.append(name)
    out.sort(key=_WEEKDAY_INDEX.__getitem__)
    return tuple(out)


def _validate_rule(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = core._require(payload.get("title"), "Title").strip()

    freq = (payload.get("frequency") or DEFAULT_FREQUENCY).strip()
    if freq not in FREQUENCIES:
        raise ValidationError(
            f"Frequency must be one of: {', '.join(FREQUENCIES)}")
    out["frequency"] = freq

    out["start_date"] = core._validate_date(
        payload.get("start_date"), "Start date")
    out["until_date"] = core._validate_date(
        payload.get("until_date"), "Until date", required=False)
    if out["until_date"] and out["until_date"] < out["start_date"]:
        raise ValidationError("Until date cannot be before start date")

    count = payload.get("max_count")
    if count in (None, ""):
        out["max_count"] = None
    else:
        try:
            n = int(count)
        except (TypeError, ValueError):
            raise ValidationError(
                "Occurrence count must be a whole number") from None
        if n < 1:
            raise ValidationError("Occurrence count must be at least 1")
        out["max_count"] = min(n, MAX_OCCURRENCES)

    anchor = _dt.date.fromisoformat(out["start_date"])
    byday = _validate_byday(payload.get("byday"))
    if freq in (WEEKLY, FORTNIGHTLY):
        # Default to the weekday the series starts on — "every Monday
        # from the 8th" should not need Monday spelling out twice.
        out["byday"] = byday or (WEEKDAYS[anchor.weekday()],)
    else:
        out["byday"] = ()

    if freq == MONTHLY:
        day = payload.get("bymonthday")
        if day in (None, ""):
            out["bymonthday"] = anchor.day
        else:
            try:
                d = int(day)
            except (TypeError, ValueError):
                raise ValidationError(
                    "Day of month must be a whole number") from None
            if not 1 <= d <= 31:
                raise ValidationError(
                    "Day of month must be between 1 and 31")
            out["bymonthday"] = d
    else:
        out["bymonthday"] = None

    span = payload.get("span_days", 1)
    try:
        s = int(span if span not in (None, "") else 1)
    except (TypeError, ValueError):
        raise ValidationError("Span days must be a whole number") from None
    if s < 1:
        raise ValidationError("Span days must be at least 1")
    out["span_days"] = s
    return out


def _validate_template(template: dict[str, Any],
                       rule: dict[str, Any]) -> dict[str, Any]:
    """Check the template by building the first occurrence's payload.

    Cheaper than re-implementing the core rules, and it cannot drift
    from them: if the first occurrence would be rejected, so would
    every other one.
    """
    tpl = {k: template[k] for k in _TEMPLATE_FIELDS if k in template}
    tpl.setdefault("title", rule["title"])
    probe = dict(tpl)
    probe["start_date"] = rule["start_date"]
    end = (_dt.date.fromisoformat(rule["start_date"])
           + _dt.timedelta(days=rule["span_days"] - 1))
    probe["end_date"] = end.isoformat()
    core._validate_payload(probe)
    return tpl


# ── Expansion ───────────────────────────────────────────────────────

def _matches(series: Series, day: _dt.date, anchor: _dt.date) -> bool:
    if series.frequency == DAILY:
        return True
    if series.frequency in (WEEKLY, FORTNIGHTLY):
        if WEEKDAYS[day.weekday()] not in series.byday:
            return False
        if series.frequency == WEEKLY:
            return True
        anchor_monday = anchor - _dt.timedelta(days=anchor.weekday())
        monday = day - _dt.timedelta(days=day.weekday())
        return ((monday - anchor_monday).days // 7) % 2 == 0
    # Monthly. Months without the day (the 31st in February) skip a
    # beat rather than sliding to a different date.
    return day.day == series.bymonthday


def occurrence_dates(series: Series, *,
                     date_to: str | None = None) -> list[str]:
    """Every date the rule produces, exceptions excluded.

    Expansion always walks from the series' own start date — a
    ``max_count`` counted from an arbitrary window start would give a
    different answer every time it was asked.
    """
    anchor = _dt.date.fromisoformat(series.start_date)
    hard_stop = anchor + _dt.timedelta(days=3 * 366)
    stops = [hard_stop]
    if series.until_date:
        stops.append(_dt.date.fromisoformat(series.until_date))
    if date_to:
        stops.append(_dt.date.fromisoformat(
            core._validate_date(date_to, "date_to")))
    stop = min(stops)

    skip = set(exception_dates(series.series_id))
    out: list[str] = []
    produced = 0
    day = anchor
    while day <= stop:
        if _matches(series, day, anchor):
            produced += 1
            if series.max_count and produced > series.max_count:
                break
            iso = day.isoformat()
            if iso not in skip:
                out.append(iso)
            if len(out) >= MAX_OCCURRENCES:
                break
        day += _dt.timedelta(days=1)
    return out


# ── Series CRUD ─────────────────────────────────────────────────────

def create_series(payload: dict[str, Any], *,
                  actor: str | None = None) -> Series:
    """Define a series. Nothing appears on the calendar until
    :func:`materialise` or :func:`sweep` runs."""
    init_db()
    rule = _validate_rule(payload)
    template = _validate_template(payload.get("template") or {}, rule)
    who = (actor or "").strip() or None
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO calendar_series
                   (title, frequency, byday, bymonthday, span_days,
                    start_date, until_date, max_count, template,
                    active, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (rule["title"], rule["frequency"],
             ",".join(rule["byday"]) or None, rule["bymonthday"],
             rule["span_days"], rule["start_date"], rule["until_date"],
             rule["max_count"], json.dumps(template), who))
        conn.commit()
        new_id = cur.lastrowid
    out = get_series(new_id)
    assert out is not None
    logger.info("Created series #%d %r (%s)", new_id, out.title,
                out.rule_label)
    return out


def get_series(series_id: int) -> Series | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM calendar_series WHERE series_id = ?",
            (series_id,)).fetchone()
    return _row_series(r) if r else None


def list_series(*, active_only: bool = True) -> list[Series]:
    init_db()
    where = "WHERE active = 1" if active_only else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM calendar_series {where} "
            "ORDER BY start_date, series_id").fetchall()
    return [_row_series(r) for r in rows]


def update_series(series_id: int, payload: dict[str, Any], *,
                  actor: str | None = None) -> Series:
    """Change the rule and/or template. The calendar itself does not
    move until :func:`sync` pushes the change onto occurrences."""
    init_db()
    existing = get_series(series_id)
    if existing is None:
        raise ValidationError(f"No series #{series_id}")
    merged_rule = {
        "title":      payload.get("title", existing.title),
        "frequency":  payload.get("frequency", existing.frequency),
        "byday":      payload.get("byday", ",".join(existing.byday)),
        "bymonthday": payload.get("bymonthday", existing.bymonthday),
        "span_days":  payload.get("span_days", existing.span_days),
        "start_date": payload.get("start_date", existing.start_date),
        "until_date": payload.get("until_date", existing.until_date),
        "max_count":  payload.get("max_count", existing.max_count),
    }
    rule = _validate_rule(merged_rule)
    merged_template = {**existing.template,
                       **(payload.get("template") or {})}
    template = _validate_template(merged_template, rule)
    with _connect() as conn:
        conn.execute(
            """UPDATE calendar_series SET
                   title = ?, frequency = ?, byday = ?, bymonthday = ?,
                   span_days = ?, start_date = ?, until_date = ?,
                   max_count = ?, template = ?,
                   updated_at = datetime('now')
               WHERE series_id = ?""",
            (rule["title"], rule["frequency"],
             ",".join(rule["byday"]) or None, rule["bymonthday"],
             rule["span_days"], rule["start_date"], rule["until_date"],
             rule["max_count"], json.dumps(template), series_id))
        conn.commit()
    out = get_series(series_id)
    assert out is not None
    logger.info("Updated series #%d (%s)", series_id, out.rule_label)
    return out


def deactivate_series(series_id: int, *, cancel_future: bool = True,
                      actor: str | None = None) -> int:
    """Retire a series. Past occurrences are history and stay put;
    future non-detached ones are archived when ``cancel_future``.

    Returns how many occurrences were archived.
    """
    init_db()
    if get_series(series_id) is None:
        raise ValidationError(f"No series #{series_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE calendar_series SET active = 0, "
            "updated_at = datetime('now') WHERE series_id = ?",
            (series_id,))
        conn.commit()
    archived = 0
    if cancel_future:
        today = _dt.date.today().isoformat()
        for occ in list_occurrences(series_id):
            if occ.detached or occ.occurrence_date < today:
                continue
            if core.delete_event(occ.event_id, actor=actor):
                archived += 1
    logger.info("Deactivated series #%d (%d future occurrence(s) "
                "archived)", series_id, archived)
    return archived


# ── Exceptions ──────────────────────────────────────────────────────

def exception_dates(series_id: int) -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT date FROM calendar_series_exceptions "
            "WHERE series_id = ? ORDER BY date", (series_id,)).fetchall()
    return [r["date"] for r in rows]


def add_exception(series_id: int, date: str, *,
                  reason: str | None = None,
                  actor: str | None = None) -> bool:
    """Skip one date. If the occurrence was already materialised and
    still follows the series, it is archived too."""
    init_db()
    if get_series(series_id) is None:
        raise ValidationError(f"No series #{series_id}")
    s = core._validate_date(date, "Date")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO calendar_series_exceptions "
            "(series_id, date, reason) VALUES (?, ?, ?)",
            (series_id, s, (reason or "").strip() or None))
        conn.commit()
        added = bool(cur.rowcount)
    occ = _occurrence_on(series_id, s)
    if occ and not occ.detached:
        core.delete_event(occ.event_id, actor=actor)
        _drop_link(occ.link_id)
    return added


def remove_exception(series_id: int, date: str) -> bool:
    """Un-skip a date. The occurrence reappears on the next sync."""
    init_db()
    s = core._validate_date(date, "Date")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM calendar_series_exceptions "
            "WHERE series_id = ? AND date = ?", (series_id, s))
        conn.commit()
    return bool(cur.rowcount)


# ── Occurrence links ────────────────────────────────────────────────

def list_occurrences(series_id: int) -> list[Occurrence]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM calendar_series_occurrences "
            "WHERE series_id = ? ORDER BY occurrence_date",
            (series_id,)).fetchall()
    return [_row_occurrence(r) for r in rows]


def series_for_event(event_id: int) -> Occurrence | None:
    """Which series an event belongs to, if any — how a view knows to
    offer "edit series" next to "edit this one"."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM calendar_series_occurrences "
            "WHERE event_id = ?", (event_id,)).fetchone()
    return _row_occurrence(r) if r else None


def _occurrence_on(series_id: int, date: str) -> Occurrence | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM calendar_series_occurrences "
            "WHERE series_id = ? AND occurrence_date = ?",
            (series_id, date)).fetchone()
    return _row_occurrence(r) if r else None


def _drop_link(link_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM calendar_series_occurrences WHERE link_id = ?",
            (link_id,))
        conn.commit()


def detach(event_id: int) -> Occurrence:
    """Cut one occurrence loose from its series.

    The link row survives with ``detached`` set, so the date stays
    claimed — a later sync will neither recreate nor prune it — but
    template pushes stop touching it. This is what "edit just this
    one" means underneath.
    """
    init_db()
    occ = series_for_event(event_id)
    if occ is None:
        raise ValidationError(
            f"Event #{event_id} does not belong to a series")
    with _connect() as conn:
        conn.execute(
            "UPDATE calendar_series_occurrences SET detached = 1 "
            "WHERE link_id = ?", (occ.link_id,))
        conn.commit()
    out = series_for_event(event_id)
    assert out is not None
    logger.info("Detached event #%d from series #%d", event_id,
                occ.series_id)
    return out


def update_occurrence(event_id: int, payload: dict[str, Any], *,
                      actor: str | None = None) -> core.Event:
    """Edit one occurrence only — detaches it, then applies the edit."""
    detach(event_id)
    return core.update_event(event_id, payload, actor=actor)


# ── Materialise / sync ──────────────────────────────────────────────

def _occurrence_payload(series: Series, date: str) -> dict[str, Any]:
    payload = dict(series.template)
    payload.setdefault("title", series.title)
    payload["start_date"] = date
    end = (_dt.date.fromisoformat(date)
           + _dt.timedelta(days=series.span_days - 1))
    payload["end_date"] = end.isoformat()
    return payload


def materialise(series_id: int, *, date_to: str | None = None,
                horizon_days: int = DEFAULT_HORIZON_DAYS,
                actor: str | None = None) -> SyncResult:
    """Create calendar rows for every unclaimed date up to a horizon."""
    init_db()
    series = get_series(series_id)
    if series is None:
        raise ValidationError(f"No series #{series_id}")
    if not series.active:
        return SyncResult()
    if date_to is None:
        date_to = (_dt.date.today()
                   + _dt.timedelta(days=horizon_days)).isoformat()
    result = SyncResult()
    claimed = {o.occurrence_date for o in list_occurrences(series_id)}
    for date in occurrence_dates(series, date_to=date_to):
        if date in claimed:
            result.skipped += 1
            continue
        event = core.create_event(_occurrence_payload(series, date),
                                  actor=actor or series.created_by)
        with _connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO calendar_series_occurrences "
                "(series_id, event_id, occurrence_date) "
                "VALUES (?, ?, ?)",
                (series_id, event.event_id, date))
            conn.commit()
        result.created += 1
        result.events.append(event)
    if result.created:
        logger.info("Series #%d materialised: %s", series_id,
                    result.summary)
    return result


def sync(series_id: int, *, date_to: str | None = None,
         horizon_days: int = DEFAULT_HORIZON_DAYS,
         actor: str | None = None) -> SyncResult:
    """Make the calendar agree with the series as it now stands.

    Materialises missing dates, pushes the template onto future
    occurrences still following the series, and archives future
    occurrences whose date the rule no longer produces. Past
    occurrences and detached ones are never touched — what happened,
    happened, and what was hand-edited stays hand-edited.
    """
    init_db()
    series = get_series(series_id)
    if series is None:
        raise ValidationError(f"No series #{series_id}")
    result = materialise(series_id, date_to=date_to,
                         horizon_days=horizon_days, actor=actor)
    if not series.active:
        return result

    today = _dt.date.today().isoformat()
    valid = set(occurrence_dates(series))
    for occ in list_occurrences(series_id):
        if occ.detached or occ.occurrence_date < today:
            continue
        if occ.occurrence_date not in valid:
            if core.delete_event(occ.event_id, actor=actor):
                result.pruned += 1
            _drop_link(occ.link_id)
            continue
        if any(e.event_id == occ.event_id for e in result.events):
            continue        # just created from the current template
        payload = _occurrence_payload(series, occ.occurrence_date)
        core.update_event(occ.event_id, payload, actor=actor)
        result.updated += 1
    logger.info("Series #%d synced: %s", series_id, result.summary)
    return result


def sweep(*, horizon_days: int = DEFAULT_HORIZON_DAYS,
          actor: str | None = None) -> SyncResult:
    """Materialise every active series up to the rolling horizon.

    Safe to run at every launch — claimed dates are skipped, so a
    quiet week costs a handful of SELECTs.
    """
    init_db()
    total = SyncResult()
    for series in list_series(active_only=True):
        got = materialise(series.series_id, horizon_days=horizon_days,
                          actor=actor)
        total.created += got.created
        total.skipped += got.skipped
        total.events.extend(got.events)
    if total.created:
        logger.info("Series sweep: %s", total.summary)
    return total
