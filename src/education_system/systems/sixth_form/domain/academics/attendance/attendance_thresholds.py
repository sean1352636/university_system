"""Configurable attendance thresholds for the Sixth Form System.

Sibling to :mod:`attendance`. Every module in this package has an
opinion about what counts as a problem — 90% is persistent absence, a
letter goes at 92%, a bursary is held below 85% — and until now each of
them held that number itself. Which means a college that runs to
different figures has to find them all, and a college that changes its
mind has to find them all again.

So the numbers live here, once, and everything else asks.

Two things make this more than a settings table:

* **Scope.** A threshold can be set college-wide, per year group, or
  per cohort tag ("resit", "bursary", "EHCP"). :func:`resolve` walks
  from the most specific scope to the least, so a Year 13 rule beats
  the college default without anybody having to restate the default.
* **Direction.** Some thresholds trip when a figure falls *below* them
  (attendance percentages) and some when it rises *above* (late
  minutes, unauthorised sessions). Storing which way round it goes is
  what lets :func:`breaches` answer "is this learner over the line" for
  any threshold without the caller knowing which kind it is.

The shipped defaults are the sector's usual figures, so a college that
never opens this screen behaves exactly as the hard-coded numbers did.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# Which way a threshold is crossed.
BELOW: str = "below"        # trips when the value falls under it
ABOVE: str = "above"        # trips when the value rises over it
DIRECTIONS: tuple[str, ...] = (BELOW, ABOVE)

# How specific a setting is. Resolution walks this list left to right.
SCOPE_COHORT: str = "cohort"
SCOPE_YEAR: str = "year"
SCOPE_COLLEGE: str = "college"
SCOPES: tuple[str, ...] = (SCOPE_COHORT, SCOPE_YEAR, SCOPE_COLLEGE)

# The keys the rest of the package asks for. Kept as constants so a
# typo is an AttributeError here rather than a silently missing rule.
PERSISTENT_ABSENCE: str = "persistent_absence"
SEVERE_ABSENCE: str = "severe_absence"
TARGET_ATTENDANCE: str = "target_attendance"
LETTER_1: str = "letter_1"
LETTER_2: str = "letter_2"
LETTER_3: str = "letter_3"
BURSARY_HOLD: str = "bursary_hold"
REWARD_ATTENDANCE: str = "reward_attendance"
REWARD_IMPROVEMENT: str = "reward_improvement"
LATE_MINUTES_TRIGGER: str = "late_minutes_trigger"
LATE_COUNT_TRIGGER: str = "late_count_trigger"
UNEXPLAINED_DAYS_ALERT: str = "unexplained_days_alert"
CME_REFERRAL_DAYS: str = "cme_referral_days"
EVIDENCE_DAYS: str = "evidence_days"
SELF_CERT_CAP: str = "self_certification_cap"

# (key, direction, default, unit, description). The sector's usual
# figures — a college that never touches this screen gets exactly what
# the hard-coded numbers used to give it.
SHIPPED: tuple[tuple[str, str, float, str, str], ...] = (
    (PERSISTENT_ABSENCE, BELOW, 90.0, "%",
     "Attendance at or below this is persistent absence."),
    (SEVERE_ABSENCE, BELOW, 50.0, "%",
     "Attendance at or below this is severe absence — a safeguarding "
     "matter, not an attendance one."),
    (TARGET_ATTENDANCE, BELOW, 95.0, "%",
     "The figure the college asks learners to hold."),
    (LETTER_1, BELOW, 92.0, "%", "First attendance letter home."),
    (LETTER_2, BELOW, 88.0, "%", "Second letter, and a tutor meeting."),
    (LETTER_3, BELOW, 85.0, "%", "Third letter, and a formal review."),
    (BURSARY_HOLD, BELOW, 85.0, "%",
     "Bursary payments are held below this figure."),
    (REWARD_ATTENDANCE, BELOW, 100.0, "%",
     "Attendance at or above this earns a certificate."),
    (REWARD_IMPROVEMENT, ABOVE, 5.0, "pp",
     "Percentage-point gain on the previous period that earns a "
     "most-improved award."),
    (LATE_MINUTES_TRIGGER, ABOVE, 60.0, "min",
     "Cumulative late minutes in a term that trigger an intervention."),
    (LATE_COUNT_TRIGGER, ABOVE, 5.0, "lates",
     "Late marks in a rolling window that trigger a detention."),
    (UNEXPLAINED_DAYS_ALERT, ABOVE, 3.0, "days",
     "Consecutive unexplained absence days that raise a DSL alert."),
    (CME_REFERRAL_DAYS, ABOVE, 10.0, "days",
     "Consecutive unexplained absence days that prompt a children-"
     "missing-education referral."),
    (EVIDENCE_DAYS, ABOVE, 5.0, "days",
     "Days allowed for promised evidence to arrive before the mark "
     "reverts to unauthorised."),
    (SELF_CERT_CAP, ABOVE, 3.0, "days",
     "Days per term a learner may self-certify before a conversation "
     "is required."),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_thresholds (
    threshold_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key          TEXT NOT NULL,
    scope        TEXT NOT NULL DEFAULT 'college',
    scope_value  TEXT,
    value        REAL NOT NULL,
    direction    TEXT NOT NULL DEFAULT 'below',
    unit         TEXT,
    description  TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    updated_at   TEXT DEFAULT (datetime('now')),
    updated_by   TEXT,
    UNIQUE(key, scope, scope_value)
);

CREATE INDEX IF NOT EXISTS idx_att_thresh_key
    ON attendance_thresholds(key);
CREATE INDEX IF NOT EXISTS idx_att_thresh_scope
    ON attendance_thresholds(scope, scope_value);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Threshold:
    """One configured number."""

    threshold_id: int
    key: str
    scope: str
    scope_value: str | None
    value: float
    direction: str
    unit: str | None
    description: str | None
    active: bool
    updated_at: str | None
    updated_by: str | None

    @property
    def label(self) -> str:
        where = ("college-wide" if self.scope == SCOPE_COLLEGE
                 else f"{self.scope} {self.scope_value}")
        return (f"{self.key}: {self.direction} {self.value:g}"
                f"{self.unit or ''} ({where})")

    def breached_by(self, value: float | None) -> bool:
        """Whether a measured figure has crossed this line.

        Inclusive on both sides: attendance *at* 90% is persistent
        absence, and 5 lates *is* the fifth late. Sector practice reads
        these as "90% or below", not "below 90%", and getting that wrong
        moves a learner in or out of a cohort by one session.
        """
        if value is None:
            return False
        return value <= self.value if self.direction == BELOW \
            else value >= self.value


@dataclass
class Breach:
    """A threshold a measured value has crossed."""

    threshold: Threshold
    value: float

    @property
    def key(self) -> str:
        return self.threshold.key

    @property
    def label(self) -> str:
        return (f"{self.threshold.key}: {self.value:g}"
                f"{self.threshold.unit or ''} vs "
                f"{self.threshold.value:g}{self.threshold.unit or ''}")


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _dedupe_college_rows(conn)
        # UNIQUE(key, scope, scope_value) never matches a NULL
        # scope_value, so college-wide rows need their own index —
        # without it every start re-seeded the shipped figures and the
        # upsert in set_threshold added a row instead of updating one.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_att_thresh_college "
            "ON attendance_thresholds(key, scope) WHERE scope_value IS NULL")
        conn.commit()
    _DB_READY = True
    seed_defaults()
    logger.debug("Attendance threshold schema ready at %s", DB_PATH)


def _dedupe_college_rows(conn: sqlite3.Connection) -> int:
    """Collapse duplicate college-wide rows left by the NULL-key bug.

    Keeps the newest row that differs from the shipped figure (the
    college's edit), else the oldest; the rest are deleted.
    """
    shipped = {key: value for key, _d, value, _u, _desc in SHIPPED}
    dupes = conn.execute(
        "SELECT key, scope FROM attendance_thresholds "
        "WHERE scope_value IS NULL GROUP BY key, scope "
        "HAVING COUNT(*) > 1").fetchall()
    removed = 0
    for d in dupes:
        rows = conn.execute(
            "SELECT threshold_id, value FROM attendance_thresholds "
            "WHERE key = ? AND scope = ? AND scope_value IS NULL "
            "ORDER BY threshold_id", (d["key"], d["scope"])).fetchall()
        edited = [r for r in rows if r["value"] != shipped.get(d["key"])]
        keep = (edited[-1] if edited else rows[0])["threshold_id"]
        removed += conn.execute(
            "DELETE FROM attendance_thresholds WHERE key = ? AND scope = ? "
            "AND scope_value IS NULL AND threshold_id <> ?",
            (d["key"], d["scope"], keep)).rowcount
    if removed:
        logger.warning("Removed %d duplicate college-wide threshold row(s)",
                       removed)
    return removed


def seed_defaults() -> int:
    """Insert the shipped figures, leaving any the college has edited.

    Idempotent, and keyed on ``(key, scope, scope_value)`` — an edited
    college-wide value is never reset by a later call.
    """
    with _connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_thresholds").fetchone()["n"]
        conn.executemany(
            """INSERT OR IGNORE INTO attendance_thresholds
                   (key, scope, scope_value, value, direction, unit,
                    description)
               VALUES (?, 'college', NULL, ?, ?, ?, ?)""",
            [(key, value, direction, unit, description)
             for key, direction, value, unit, description in SHIPPED])
        conn.commit()
        after = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_thresholds").fetchone()["n"]
    added = after - before
    if added:
        logger.info("Seeded %d attendance threshold(s)", added)
    return added


def _row(r: sqlite3.Row) -> Threshold:
    return Threshold(
        threshold_id=r["threshold_id"],
        key=r["key"],
        scope=r["scope"],
        scope_value=r["scope_value"],
        value=r["value"],
        direction=r["direction"],
        unit=r["unit"],
        description=r["description"],
        active=bool(r["active"]),
        updated_at=r["updated_at"],
        updated_by=r["updated_by"],
    )


# ── Validation ──────────────────────────────────────────────────────

def validate_direction(value: Any) -> str:
    s = (value or "").strip().lower() if isinstance(value, str) else ""
    if not s:
        return BELOW
    if s not in DIRECTIONS:
        raise ValidationError(
            f"Direction must be one of: {', '.join(DIRECTIONS)}")
    return s


def validate_scope(value: Any) -> str:
    s = (value or "").strip().lower() if isinstance(value, str) else ""
    if not s:
        return SCOPE_COLLEGE
    if s not in SCOPES:
        raise ValidationError(f"Scope must be one of: {', '.join(SCOPES)}")
    return s


def _validate_key(value: Any) -> str:
    s = (value or "").strip().lower().replace(" ", "_") \
        if isinstance(value, str) else ""
    if not s:
        raise ValidationError("Threshold key is required")
    if len(s) > 60:
        raise ValidationError("Threshold key must be 60 characters or fewer")
    return s


def _validate_value(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Threshold value must be a number") from None
    if out < 0 or out > 100000:
        raise ValidationError("Threshold value is out of range")
    return out


# ── Reading ─────────────────────────────────────────────────────────

def resolve(
    key: str,
    *,
    year_group: int | str | None = None,
    cohort: str | None = None,
) -> Threshold | None:
    """The threshold that applies, most specific scope first.

    Cohort beats year group beats college. A college that has set only
    the default gets the default for everybody, which is what makes
    scoping safe to add to an existing installation.
    """
    init_db()
    key = _validate_key(key)
    candidates: list[tuple[str, str | None]] = []
    if cohort:
        candidates.append((SCOPE_COHORT, str(cohort).strip()))
    if year_group not in (None, ""):
        candidates.append((SCOPE_YEAR, str(year_group).strip()))
    candidates.append((SCOPE_COLLEGE, None))

    with _connect() as conn:
        for scope, scope_value in candidates:
            r = conn.execute(
                "SELECT * FROM attendance_thresholds "
                "WHERE key = ? AND scope = ? AND active = 1 "
                "AND (scope_value IS ? OR scope_value = ?)",
                (key, scope, scope_value, scope_value)).fetchone()
            if r is not None:
                return _row(r)
    return None


def value_of(key: str, *, year_group: int | str | None = None,
             cohort: str | None = None,
             default: float | None = None) -> float | None:
    """Just the number. ``default`` covers a key nobody has configured."""
    threshold = resolve(key, year_group=year_group, cohort=cohort)
    return threshold.value if threshold else default


def get_threshold(threshold_id: int) -> Threshold | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_thresholds WHERE threshold_id = ?",
            (threshold_id,)).fetchone()
    return _row(r) if r else None


def list_thresholds(*, key: str | None = None, scope: str | None = None,
                    active_only: bool = True) -> list[Threshold]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if active_only:
        clauses.append("active = 1")
    if key:
        clauses.append("key = ?")
        args.append(_validate_key(key))
    if scope:
        clauses.append("scope = ?")
        args.append(validate_scope(scope))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_thresholds {where} "
            "ORDER BY key, scope, scope_value", args).fetchall()
    return [_row(r) for r in rows]


def as_dict(*, year_group: int | str | None = None,
            cohort: str | None = None) -> dict[str, float]:
    """Every threshold resolved for one learner, as ``key -> value``.

    Read once by anything that needs several — a report card, a letter
    run — rather than issuing a query per figure.
    """
    init_db()
    keys = {t.key for t in list_thresholds()}
    out: dict[str, float] = {}
    for key in sorted(keys):
        threshold = resolve(key, year_group=year_group, cohort=cohort)
        if threshold is not None:
            out[key] = threshold.value
    return out


# ── Writing ─────────────────────────────────────────────────────────

def set_threshold(
    key: str,
    value: float,
    *,
    scope: str = SCOPE_COLLEGE,
    scope_value: str | None = None,
    direction: str | None = None,
    unit: str | None = None,
    description: str | None = None,
    actor: str | None = None,
) -> Threshold:
    """Set or change a threshold.

    ``direction`` and ``unit`` are inherited from the college-wide
    setting when left out, so adding a Year 13 override is one number
    rather than a restatement of the whole rule.
    """
    init_db()
    key = _validate_key(key)
    value = _validate_value(value)
    scope = validate_scope(scope)
    scope_value = ((scope_value or "").strip() or None
                   if scope != SCOPE_COLLEGE else None)
    if scope != SCOPE_COLLEGE and not scope_value:
        raise ValidationError(f"A {scope}-scoped threshold needs a "
                              f"{scope} to apply to")

    inherited = resolve(key)
    direction = (validate_direction(direction) if direction
                 else (inherited.direction if inherited else BELOW))
    unit = unit if unit is not None else (inherited.unit if inherited else None)
    description = (description if description is not None
                   else (inherited.description if inherited else None))

    with _connect() as conn:
        target = ("(key, scope) WHERE scope_value IS NULL"
                  if scope_value is None else "(key, scope, scope_value)")
        conn.execute(
            """INSERT INTO attendance_thresholds
                   (key, scope, scope_value, value, direction, unit,
                    description, updated_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT{target} DO UPDATE SET
                   value = excluded.value,
                   direction = excluded.direction,
                   unit = excluded.unit,
                   description = COALESCE(excluded.description,
                                          attendance_thresholds.description),
                   active = 1,
                   updated_at = datetime('now'),
                   updated_by = excluded.updated_by""".format(target=target),
            (key, scope, scope_value, value, direction, unit, description,
             (actor or "").strip() or None))
        conn.commit()
    logger.info("Threshold %s set to %g (%s %s) by %s", key, value, scope,
                scope_value or "-", actor or "?")
    out = resolve(key, year_group=scope_value if scope == SCOPE_YEAR else None,
                  cohort=scope_value if scope == SCOPE_COHORT else None)
    assert out is not None
    return out


def clear_override(key: str, *, scope: str, scope_value: str) -> bool:
    """Drop a scoped override so the wider setting applies again."""
    init_db()
    if validate_scope(scope) == SCOPE_COLLEGE:
        raise ValidationError(
            "The college-wide setting is the fallback — it cannot be "
            "cleared, only changed")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_thresholds "
            "WHERE key = ? AND scope = ? AND scope_value = ?",
            (_validate_key(key), scope, scope_value.strip()))
        conn.commit()
    return bool(cur.rowcount)


def reset_to_shipped(*, actor: str | None = None) -> int:
    """Put every shipped figure back, leaving custom keys alone."""
    init_db()
    with _connect() as conn:
        conn.executemany(
            """UPDATE attendance_thresholds
                  SET value = ?, direction = ?, active = 1,
                      updated_at = datetime('now'), updated_by = ?
                WHERE key = ? AND scope = 'college'""",
            [(value, direction, (actor or "").strip() or None, key)
             for key, direction, value, _unit, _desc in SHIPPED])
        conn.commit()
    logger.info("Attendance thresholds reset to shipped values by %s",
                actor or "?")
    return len(SHIPPED)


# ── Testing a value ─────────────────────────────────────────────────

def is_breached(key: str, value: float | None, *,
                year_group: int | str | None = None,
                cohort: str | None = None) -> bool:
    """Whether a measured figure has crossed one named threshold."""
    threshold = resolve(key, year_group=year_group, cohort=cohort)
    return bool(threshold and threshold.breached_by(value))


def breaches(values: dict[str, float | None], *,
             year_group: int | str | None = None,
             cohort: str | None = None) -> list[Breach]:
    """Every threshold a set of measurements has crossed.

    Pass what you measured, get back what it means. The caller never has
    to know which way round a given threshold reads.
    """
    out: list[Breach] = []
    for key, value in values.items():
        if value is None:
            continue
        threshold = resolve(key, year_group=year_group, cohort=cohort)
        if threshold is not None and threshold.breached_by(value):
            out.append(Breach(threshold=threshold, value=float(value)))
    return out


def worst_letter(percentage: float | None, *,
                 year_group: int | str | None = None,
                 cohort: str | None = None) -> str | None:
    """Which attendance letter a percentage has earned, if any.

    The most serious one triggered, not the first — a learner at 80%
    gets letter 3, not three letters.
    """
    for key in (LETTER_3, LETTER_2, LETTER_1):
        if is_breached(key, percentage, year_group=year_group, cohort=cohort):
            return key
    return None


def describe(key: str) -> str:
    """One line for a settings screen."""
    threshold = resolve(key)
    if threshold is None:
        return f"{key}: not configured"
    return f"{threshold.label} — {threshold.description or ''}".strip(" —")
