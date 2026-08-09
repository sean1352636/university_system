"""Marking-anomaly detection for the Sixth Form System.

Sibling to :mod:`attendance`. Everything else in this package assumes
the register is broadly honest. Mostly it is. But attendance data drives
funding, safeguarding and a learner's place on their course, and a
register that is quietly wrong is worse than one that is obviously
missing — the missing one gets chased.

The patterns worth looking for are all *shapes*, not accusations:

* **Never a single absence.** A slot with a hundred marks and no absence
  at all is possible, and is much more often a register taken by
  pressing "all present" while walking to the next lesson.
* **Copy-forward dependence.** :func:`copy_forward_use` counts marks
  that arrived by prefill rather than by looking at the room. The
  feature is useful; a register that has been copied nine weeks running
  is not a register.
* **Marked at the wrong time.** A lesson at 09:00 marked at 16:40 was
  reconstructed from memory. :func:`late_marking` finds those.
* **Identical registers.** The same fingerprint week after week
  (:func:`identical_registers`) is either a very stable class or nobody
  looking.
* **Bulk saves.** A whole term marked in one minute is an import
  somebody did by hand, and it should be looked at even when it is
  entirely innocent.

**Nothing here concludes anything.** Every finding is a shape with a
confidence and an explanation, for a human to look into. Presenting
these as evidence of misconduct would be both wrong and, in most cases,
inaccurate — the usual explanation is a teacher under time pressure,
which is a workload problem rather than an integrity one.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
    attendance_register as reg,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

ALL_PRESENT: str = "Never records an absence"
COPY_FORWARD: str = "Heavy copy-forward use"
LATE_MARKING: str = "Marked long after the lesson"
IDENTICAL: str = "Identical registers week to week"
BULK_SAVE: str = "Many registers saved at once"
NO_LATES: str = "Never records lateness"
ROUND_NUMBERS: str = "Suspiciously round late minutes"
PATTERNS: tuple[str, ...] = (ALL_PRESENT, COPY_FORWARD, LATE_MARKING,
                             IDENTICAL, BULK_SAVE, NO_LATES, ROUND_NUMBERS)

HIGH: str = "High"
MEDIUM: str = "Medium"
LOW: str = "Low"
CONFIDENCE: tuple[str, ...] = (HIGH, MEDIUM, LOW)
_CONFIDENCE_RANK: dict[str, int] = {c: i for i, c in enumerate(CONFIDENCE)}

# A slot needs at least this many marked registers before its shape says
# anything. Below it, everything looks anomalous.
MIN_REGISTERS: int = 8

# Hours after a lesson ends past which marking looks reconstructed.
LATE_MARKING_HOURS: int = 6

# Registers saved within this many seconds of each other count as one
# bulk action.
BULK_WINDOW_SECONDS: int = 120
BULK_MIN_REGISTERS: int = 5


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Finding:
    """One shape worth a look. Not an accusation."""

    pattern: str
    scope: str                  # "slot #12", "T Patel", "group 3"
    confidence: str
    detail: str
    slot_id: int | None = None
    group_id: int | None = None
    owner: str | None = None
    sample: int = 0
    dates: list[str] = field(default_factory=list)

    @property
    def rank(self) -> int:
        return _CONFIDENCE_RANK.get(self.confidence, len(CONFIDENCE))

    @property
    def label(self) -> str:
        return f"[{self.confidence}] {self.scope}: {self.pattern} — {self.detail}"


@dataclass
class SlotProfile:
    """What one slot's marking looks like."""

    slot_id: int
    group_id: int | None
    registers: int = 0
    marks: int = 0
    absences: int = 0
    lates: int = 0
    copy_forward: int = 0
    distinct_digests: int = 0
    owner: str | None = None

    @property
    def absence_rate(self) -> float | None:
        if self.marks == 0:
            return None
        return round(100.0 * self.absences / self.marks, 1)

    @property
    def late_rate(self) -> float | None:
        if self.marks == 0:
            return None
        return round(100.0 * self.lates / self.marks, 1)

    @property
    def copy_forward_rate(self) -> float | None:
        if self.registers == 0:
            return None
        return round(100.0 * self.copy_forward / self.registers, 1)

    @property
    def repetition_rate(self) -> float | None:
        """How much of the term is the same register repeated."""
        if self.registers == 0:
            return None
        return round(100.0 * (1 - self.distinct_digests / self.registers), 1)


@dataclass
class Report:
    """A whole sweep."""

    date_from: str
    date_to: str
    findings: list[Finding] = field(default_factory=list)
    slots_examined: int = 0

    def of_pattern(self, pattern: str) -> list[Finding]:
        return [f for f in self.findings if f.pattern == pattern]

    @property
    def high_confidence(self) -> list[Finding]:
        return [f for f in self.findings if f.confidence == HIGH]

    @property
    def summary(self) -> str:
        by_pattern: dict[str, int] = {}
        for finding in self.findings:
            by_pattern[finding.pattern] = by_pattern.get(finding.pattern,
                                                         0) + 1
        if not by_pattern:
            return f"{self.slots_examined} slot(s) examined, nothing unusual"
        return (f"{self.slots_examined} slot(s) examined: "
                + "; ".join(f"{n} × {pattern.lower()}"
                            for pattern, n in sorted(by_pattern.items())))


# ── Gathering ───────────────────────────────────────────────────────

def _connect():
    import sqlite3
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _owner_of(slot_id: int, date: str) -> str | None:
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_cover as _cover,
        )
        return _cover.who_should_mark(slot_id, date)
    except Exception:                       # pragma: no cover - defensive
        return None


def profile_slot(slot_id: int, *, date_from: str,
                 date_to: str) -> SlotProfile:
    """What one slot's marking looks like over a window."""
    reg.init_db()
    slot = tt.get_slot(slot_id)
    profile = SlotProfile(slot_id=slot_id,
                          group_id=slot.group_id if slot else None)

    by_date: dict[str, list[Any]] = {}
    for record in core.list_records(slot_id=slot_id, date_from=date_from,
                                    date_to=date_to):
        by_date.setdefault(record.date, []).append(record)

    digests: set[str] = set()
    for date, records in by_date.items():
        profile.registers += 1
        profile.marks += len(records)
        for record in records:
            if codes.is_absence(record.code):
                profile.absences += 1
            if record.minutes_late or record.code in ("L", "U"):
                profile.lates += 1
        try:
            digests.add(reg.register_digest(slot_id, date))
        except Exception:                   # pragma: no cover - defensive
            pass
    profile.distinct_digests = len(digests)

    with _connect() as conn:
        r = conn.execute(
            """SELECT COUNT(*) AS n FROM attendance_records
                WHERE slot_id = ? AND date >= ? AND date <= ?
                  AND data_source = 'derived'""",
            (slot_id, date_from, date_to)).fetchone()
        profile.copy_forward = int(r["n"])

    if by_date:
        profile.owner = _owner_of(slot_id, sorted(by_date)[-1])
    return profile


# ── Detectors ───────────────────────────────────────────────────────

def all_present_slots(*, date_from: str, date_to: str,
                      min_registers: int = MIN_REGISTERS) -> list[Finding]:
    """Slots that have never recorded an absence.

    Possible. Also what "mark all present" looks like from the outside,
    and the two are indistinguishable in the data — which is why this is
    a prompt to ask, not a conclusion.
    """
    out: list[Finding] = []
    for slot in tt.list_slots():
        profile = profile_slot(slot.slot_id, date_from=date_from,
                               date_to=date_to)
        if profile.registers < max(1, min_registers):
            continue
        if profile.absences > 0:
            continue
        confidence = HIGH if profile.registers >= min_registers * 2 else MEDIUM
        out.append(Finding(
            pattern=ALL_PRESENT, scope=f"slot #{slot.slot_id}",
            confidence=confidence, slot_id=slot.slot_id,
            group_id=slot.group_id, owner=profile.owner,
            sample=profile.registers,
            detail=(f"{profile.marks} mark(s) across {profile.registers} "
                    f"register(s), not one absence")))
    return out


def no_lateness_slots(*, date_from: str, date_to: str,
                      min_registers: int = MIN_REGISTERS) -> list[Finding]:
    """Slots that record absence but never lateness.

    Softer than the all-present signal and often entirely innocent —
    plenty of teachers do not mark lateness at all, which is itself
    worth knowing, because their learners' punctuality data is fiction.
    """
    out: list[Finding] = []
    for slot in tt.list_slots():
        profile = profile_slot(slot.slot_id, date_from=date_from,
                               date_to=date_to)
        if profile.registers < max(1, min_registers) or profile.marks == 0:
            continue
        if profile.lates > 0 or profile.absences == 0:
            continue
        out.append(Finding(
            pattern=NO_LATES, scope=f"slot #{slot.slot_id}",
            confidence=LOW, slot_id=slot.slot_id, group_id=slot.group_id,
            owner=profile.owner, sample=profile.registers,
            detail=(f"{profile.absences} absence(s) recorded but no lateness "
                    f"in {profile.registers} register(s)")))
    return out


def copy_forward_use(*, date_from: str, date_to: str,
                     threshold_pct: float = 50.0,
                     min_registers: int = MIN_REGISTERS) -> list[Finding]:
    """Slots leaning heavily on copy-forward.

    The feature exists because an ongoing absence is still an absence
    tomorrow. Used for most of a term, it means nobody has looked at the
    room since half term.
    """
    out: list[Finding] = []
    for slot in tt.list_slots():
        profile = profile_slot(slot.slot_id, date_from=date_from,
                               date_to=date_to)
        rate = profile.copy_forward_rate
        if profile.registers < max(1, min_registers) or rate is None:
            continue
        if rate < threshold_pct:
            continue
        out.append(Finding(
            pattern=COPY_FORWARD, scope=f"slot #{slot.slot_id}",
            confidence=HIGH if rate >= 80 else MEDIUM,
            slot_id=slot.slot_id, group_id=slot.group_id,
            owner=profile.owner, sample=profile.registers,
            detail=f"{rate:.0f}% of marks arrived by prefill"))
    return out


def identical_registers(*, date_from: str, date_to: str,
                        min_registers: int = MIN_REGISTERS,
                        threshold_pct: float = 70.0) -> list[Finding]:
    """Slots whose register is the same fingerprint week after week."""
    out: list[Finding] = []
    for slot in tt.list_slots():
        profile = profile_slot(slot.slot_id, date_from=date_from,
                               date_to=date_to)
        repetition = profile.repetition_rate
        if profile.registers < max(1, min_registers) or repetition is None:
            continue
        if repetition < threshold_pct:
            continue
        out.append(Finding(
            pattern=IDENTICAL, scope=f"slot #{slot.slot_id}",
            confidence=HIGH if repetition >= 90 else MEDIUM,
            slot_id=slot.slot_id, group_id=slot.group_id,
            owner=profile.owner, sample=profile.registers,
            detail=(f"only {profile.distinct_digests} distinct register(s) "
                    f"in {profile.registers}")))
    return out


def late_marking(*, date_from: str, date_to: str,
                 hours: int = LATE_MARKING_HOURS,
                 limit: int = 200) -> list[Finding]:
    """Registers marked long after the lesson finished.

    A mark written the same evening is a reconstruction; one written the
    following week is a guess. Neither is dishonest and both are
    unreliable, which is the point.
    """
    reg.init_db()
    out: list[Finding] = []
    slots = {s.slot_id: s for s in tt.list_slots()}

    with _connect() as conn:
        rows = conn.execute(
            """SELECT slot_id, date, MIN(recorded_at) AS first_mark,
                      COUNT(*) AS n
                 FROM attendance_records
                WHERE date >= ? AND date <= ? AND voided = 0
             GROUP BY slot_id, date""",
            (core._validate_date(date_from),
             core._validate_date(date_to))).fetchall()

    for r in rows:
        slot = slots.get(r["slot_id"])
        if slot is None or not r["first_mark"]:
            continue
        try:
            marked_at = _dt.datetime.fromisoformat(r["first_mark"])
        except ValueError:                  # pragma: no cover - defensive
            continue
        _start, end = reg.slot_window(r["slot_id"])
        lesson_end = _dt.datetime.combine(
            _dt.date.fromisoformat(r["date"]),
            _dt.time(int(end.split(":")[0]), int(end.split(":")[1])))
        delay = (marked_at - lesson_end).total_seconds() / 3600.0
        if delay < hours:
            continue
        out.append(Finding(
            pattern=LATE_MARKING, scope=f"slot #{r['slot_id']} on {r['date']}",
            confidence=HIGH if delay >= 24 else MEDIUM,
            slot_id=r["slot_id"], group_id=slot.group_id,
            owner=_owner_of(r["slot_id"], r["date"]), sample=r["n"],
            dates=[r["date"]],
            detail=f"first mark written {delay:.0f}h after the lesson ended"))
        if len(out) >= limit:
            break
    out.sort(key=lambda f: -f.sample)
    return out


def bulk_saves(*, date_from: str, date_to: str,
               window_seconds: int = BULK_WINDOW_SECONDS,
               minimum: int = BULK_MIN_REGISTERS) -> list[Finding]:
    """Many registers written in one burst.

    Usually a catch-up session on a Friday afternoon, which is worth
    knowing about: those registers are memory, not observation.
    """
    reg.init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT slot_id, date, MIN(recorded_at) AS at
                 FROM attendance_records
                WHERE date >= ? AND date <= ? AND voided = 0
             GROUP BY slot_id, date
             ORDER BY at""",
            (core._validate_date(date_from),
             core._validate_date(date_to))).fetchall()

    out: list[Finding] = []
    burst: list[Any] = []
    previous: _dt.datetime | None = None
    for r in rows:
        if not r["at"]:
            continue
        try:
            stamp = _dt.datetime.fromisoformat(r["at"])
        except ValueError:                  # pragma: no cover - defensive
            continue
        if previous is not None and \
                (stamp - previous).total_seconds() <= window_seconds:
            burst.append(r)
        else:
            if len(burst) >= minimum:
                out.append(_burst_finding(burst))
            burst = [r]
        previous = stamp
    if len(burst) >= minimum:
        out.append(_burst_finding(burst))
    return out


def _burst_finding(burst: list[Any]) -> Finding:
    dates = sorted({r["date"] for r in burst})
    return Finding(
        pattern=BULK_SAVE,
        scope=f"{len(burst)} registers at {burst[0]['at'][:16]}",
        confidence=HIGH if len(burst) >= BULK_MIN_REGISTERS * 3 else MEDIUM,
        sample=len(burst), dates=dates,
        detail=(f"{len(burst)} register(s) covering {len(dates)} date(s) "
                f"saved within a couple of minutes"))


def round_late_minutes(*, date_from: str, date_to: str,
                       threshold_pct: float = 90.0,
                       minimum: int = 10) -> list[Finding]:
    """Late minutes that are always multiples of five.

    Nobody arrives at exactly five past. Where every late mark is round,
    the minutes are estimates, and any punctuality report built on them
    is an estimate too.
    """
    reg.init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT slot_id, minutes_late FROM attendance_records
                WHERE date >= ? AND date <= ? AND voided = 0
                  AND minutes_late IS NOT NULL AND minutes_late > 0""",
            (core._validate_date(date_from),
             core._validate_date(date_to))).fetchall()

    tally: dict[int, list[int]] = {}
    for r in rows:
        tally.setdefault(r["slot_id"], []).append(int(r["minutes_late"]))

    out: list[Finding] = []
    for slot_id, values in tally.items():
        if len(values) < minimum:
            continue
        round_share = 100.0 * sum(1 for v in values if v % 5 == 0) / len(values)
        if round_share < threshold_pct:
            continue
        slot = tt.get_slot(slot_id)
        out.append(Finding(
            pattern=ROUND_NUMBERS, scope=f"slot #{slot_id}",
            confidence=LOW, slot_id=slot_id,
            group_id=slot.group_id if slot else None, sample=len(values),
            detail=(f"{round_share:.0f}% of {len(values)} late mark(s) are a "
                    "multiple of five minutes")))
    return out


# ── The sweep ───────────────────────────────────────────────────────

def sweep(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = 90,
    min_registers: int = MIN_REGISTERS,
) -> Report:
    """Run every detector over a window.

    Findings are ordered by confidence, and the report is a starting
    point for a conversation about workload as often as about marking.
    """
    date_to = core._validate_date(date_to or _dt.date.today().isoformat())
    date_from = core._validate_date(
        date_from or (_dt.date.fromisoformat(date_to)
                      - _dt.timedelta(days=window_days)).isoformat())
    report = Report(date_from=date_from, date_to=date_to,
                    slots_examined=len(tt.list_slots()))

    for detector in (
        lambda: all_present_slots(date_from=date_from, date_to=date_to,
                                  min_registers=min_registers),
        lambda: copy_forward_use(date_from=date_from, date_to=date_to,
                                 min_registers=min_registers),
        lambda: identical_registers(date_from=date_from, date_to=date_to,
                                    min_registers=min_registers),
        lambda: late_marking(date_from=date_from, date_to=date_to),
        lambda: bulk_saves(date_from=date_from, date_to=date_to),
        lambda: no_lateness_slots(date_from=date_from, date_to=date_to,
                                  min_registers=min_registers),
        lambda: round_late_minutes(date_from=date_from, date_to=date_to),
    ):
        try:
            report.findings.extend(detector())
        except Exception as e:              # pragma: no cover - defensive
            logger.warning("Anomaly detector failed: %s", e)

    report.findings.sort(key=lambda f: (f.rank, -f.sample))
    logger.info("Anomaly sweep: %s", report.summary)
    return report


def by_owner(report: Report) -> dict[str, list[Finding]]:
    """Findings grouped by whoever takes the register.

    Grouped, not ranked. A list of staff sorted by suspicion is a
    management instrument this module should not be providing; a
    grouping is what somebody needs to have a sensible conversation.
    """
    out: dict[str, list[Finding]] = {}
    for finding in report.findings:
        if not finding.owner:
            continue
        out.setdefault(finding.owner, []).append(finding)
    return out


def slot_health(slot_id: int, *, window_days: int = 90) -> dict[str, Any]:
    """Everything known about one slot's marking, for a single look."""
    date_to = _dt.date.today().isoformat()
    date_from = (_dt.date.today()
                 - _dt.timedelta(days=window_days)).isoformat()
    profile = profile_slot(slot_id, date_from=date_from, date_to=date_to)
    findings = [f for f in sweep(date_from=date_from,
                                 date_to=date_to).findings
                if f.slot_id == slot_id]
    return {
        "slot_id": slot_id,
        "profile": profile,
        "findings": findings,
        "looks_healthy": not findings and profile.registers >= MIN_REGISTERS,
    }
