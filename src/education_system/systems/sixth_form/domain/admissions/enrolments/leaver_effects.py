"""The leaver steps owned by other areas.

:func:`leaving.learner_left` closes a leaver's enrolments and then calls
:func:`on_left`, which runs — through each area's own API — the steps
that stop a learner who has gone still looking enrolled:

* **class groups** — the learner leaves every class group (the
  membership trail in ``class_group_membership_log`` keeps the history);
* **exam entries** — entries not yet sat are withdrawn (the exams office
  amendment history records it, with any late-withdrawal fee); an entry
  whose paper date has already passed is *flagged*, never changed, since
  the learner may have sat it;
* **bursary** — every scheduled award stops on the leaving date (later
  pending instalments are cancelled by the bursary module); instalments
  for periods before the leaving date, and applications still being
  assessed, are reported for the finance team to decide;
* **free meals** — active entitlements end on the leaving date.

One step failing never stops the others, and nothing here raises: every
outcome — done or not — comes back as a line for the screen.

Each change is also kept in ``enrolment_leaver_effects`` so that
:func:`on_returned` (called when a withdrawal is reinstated) can tell
staff exactly what to re-do. It never re-adds anything itself: a
returning learner may need a different set, entry or award.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import logging
from typing import Any, Iterator

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as _enrolments,
)

logger = logging.getLogger(__name__)

#: Areas recorded in ``enrolment_leaver_effects``.
AREAS: tuple[str, ...] = ("class_group", "exam_entry", "bursary",
                          "free_meals")

#: Rough last day of each exam series, for an entry with no timetabled
#: paper date: (month, day) in the entry's year.
_SERIES_END: dict[str, tuple[int, int]] = {
    "January": (1, 31), "Summer": (6, 30), "November": (11, 30),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolment_leaver_effects (
    effect_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    left_on      TEXT NOT NULL,
    area         TEXT NOT NULL,
    ref          TEXT,
    label        TEXT,
    action       TEXT NOT NULL,
    recorded_by  TEXT,
    recorded_at  TEXT NOT NULL DEFAULT (datetime('now')),
    returned_at  TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_leaver_effects_student
    ON enrolment_leaver_effects(student_id);
"""

_READY_PATHS: set[str] = set()


@contextlib.contextmanager
def _db() -> Iterator[Any]:
    _init()
    conn = _enrolments._connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init() -> None:
    key = str(_enrolments.DB_PATH)
    if key in _READY_PATHS:
        return
    _enrolments.init_db()
    conn = _enrolments._connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    _READY_PATHS.add(key)


def _actor() -> str:
    from education_system.systems.sixth_form.domain.admissions import _guard
    return _guard.actor() or "system:leaver"


def _remember(student_id: str, day: str, area: str, ref: Any, label: str,
              action: str) -> None:
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO enrolment_leaver_effects (student_id, left_on, "
                "area, ref, label, action, recorded_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (student_id, day, area, str(ref), label, action, _actor()))
    except Exception:  # noqa: BLE001 — the step itself already happened
        logger.exception("Could not record leaver effect %s %s for %s",
                         area, ref, student_id)


# ── Class groups ────────────────────────────────────────────────────

def _class_groups(student_id: str, day: str) -> list[str]:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_group_membership as _members,
        class_groups as _cg,
    )
    lines: list[str] = []
    groups = _cg.groups_for_student(student_id)
    if not groups:
        return ["Class groups: not in any class group"]
    for g in groups:
        try:
            r = _members.remove_members_bulk(
                g.group_id, [student_id], actor=_actor(),
                reason=f"Learner left on {day}", action="leave")
            if r.succeeded:
                lines.append(f"Class group {g.group_name}: removed "
                             "(history kept)")
                _remember(student_id, day, "class_group", g.group_id,
                          g.group_name, "removed")
            else:
                lines.append(f"Class group {g.group_name}: was not a member")
        except Exception as exc:  # noqa: BLE001 — reported per group
            logger.exception("Leaver %s: class group #%d", student_id,
                             g.group_id)
            lines.append(f"Class group {g.group_name}: could not remove "
                         f"— {exc}")
    return lines


# ── Exam entries ────────────────────────────────────────────────────

def _paper_dates(season: str, year: int) -> dict[tuple[str, str], str]:
    """(board, component code) -> exam date for a series (empty when
    the exams timetable is not set up)."""
    try:
        from education_system.systems.sixth_form.domain.assessment.exams_office import (
            timetable as _tt,
        )
        return {(p.exam_board, p.component_code): p.exam_date
                for p in _tt.list_papers(season=season, year=year)}
    except Exception:  # noqa: BLE001 — no timetable: fall back to series end
        logger.debug("exams timetable not read", exc_info=True)
        return {}


def _sat_by(entry: Any, dates: dict[tuple[str, str], str]) -> str:
    """The day the entry's paper is (or was) sat: the timetabled date,
    else the end of its series."""
    when = dates.get((entry.exam_board, entry.paper_code))
    if when:
        return when
    month, d = _SERIES_END.get(entry.season, (6, 30))
    return _dt.date(int(entry.year), month, d).isoformat()


def _exam_entries(student_id: str, day: str) -> list[str]:
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _ee,
    )
    lines: list[str] = []
    entries = [e for e in _ee.list_entries(student_id=student_id)
               if e.status == "Entered"]
    if not entries:
        return ["Exam entries: none open"]
    cache: dict[tuple[str, int], dict[tuple[str, str], str]] = {}
    for e in entries:
        label = (f"{e.subject} {e.paper_code} ({e.exam_board}, {e.season} "
                 f"{e.year})")
        try:
            key = (e.season, int(e.year))
            if key not in cache:
                cache[key] = _paper_dates(*key)
            sat_by = _sat_by(e, cache[key])
            if sat_by <= day:
                lines.append(f"Exam entry {label}: paper date {sat_by} is on "
                             "or before the leaving date — check whether it "
                             "was sat; not changed")
                continue
            note = f"Withdrawn: learner left on {day}"
            notes = f"{e.notes} | {note}" if e.notes else note
            _ee.update_entry(e.entry_id, {"status": "Withdrawn",
                                          "notes": notes[:1000]},
                             reason=f"Learner left on {day}")
            lines.append(f"Exam entry {label}: withdrawn (any late "
                         "withdrawal fee is in the amendment history)")
            _remember(student_id, day, "exam_entry", e.entry_id, label,
                      "withdrawn")
        except Exception as exc:  # noqa: BLE001 — reported per entry
            logger.exception("Leaver %s: exam entry #%d", student_id,
                             e.entry_id)
            lines.append(f"Exam entry {label}: could not withdraw — {exc}")
    return lines


# ── Bursary ─────────────────────────────────────────────────────────

def _bursary(student_id: str, day: str) -> list[str]:
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _br,
        bursary_payments as _bp,
    )
    lines: list[str] = []
    awards = _bp.list_scheduled_awards(student_id=student_id,
                                       active_only=True)
    for a in awards:
        label = f"{a.bursary_type} #{a.application_id}"
        try:
            before = {i.instalment_id for i in _bp.list_instalments(
                application_id=a.application_id, state=_bp.INSTALMENT_PENDING)}
            _bp.end_scheduled_award(a.application_id, on=day)
            after = {i.instalment_id for i in _bp.list_instalments(
                application_id=a.application_id, state=_bp.INSTALMENT_PENDING)}
            lines.append(f"Bursary {label}: payments stopped from {day} "
                         f"({len(before - after)} later instalment(s) "
                         "cancelled)")
            _remember(student_id, day, "bursary", a.application_id, label,
                      "award ended")
            if after:
                lines.append(f"Bursary {label}: {len(after)} instalment(s) "
                             "for periods before leaving are still pending "
                             "— decide them in Bursaries")
        except Exception as exc:  # noqa: BLE001 — reported per award
            logger.exception("Leaver %s: bursary #%d", student_id,
                             a.application_id)
            lines.append(f"Bursary {label}: could not stop payments — {exc}")
    held = [i for i in _bp.list_instalments(student_id=student_id,
                                            state=_bp.INSTALMENT_HELD)]
    if held:
        lines.append(f"Bursary: {len(held)} held instalment(s) — release or "
                     "forfeit them in Bursaries")
    scheduled = {a.application_id for a in awards}
    for app in _br.list_applications(student_id=student_id):
        if app.application_id in scheduled or app.is_approved:
            continue
        if app.is_active:
            lines.append(f"Bursary application #{app.application_id} "
                         f"({app.bursary_type}) is still {app.status} — "
                         "review it in Bursaries")
    if not lines:
        lines.append("Bursary: no scheduled payments")
    return lines


# ── Free meals ──────────────────────────────────────────────────────

def _free_meals(student_id: str, day: str) -> list[str]:
    from education_system.systems.sixth_form.domains.finance.domain.free_meals import (
        free_meals as _fm,
    )
    lines: list[str] = []
    for e in _fm.list_entitlements(student_id=student_id, status="Active"):
        label = f"Free meals entitlement #{e.entitlement_id}"
        if e.end_date and e.end_date <= day:
            continue
        try:
            if e.start_date > day:
                note = f"Ended: learner left on {day} before it started"
                _fm.update_entitlement(e.entitlement_id, {
                    "status": "Ended",
                    "notes": f"{e.notes} | {note}" if e.notes else note})
            else:
                _fm.end_entitlement(e.entitlement_id, on=day,
                                    reason="Learner left")
            lines.append(f"{label}: ended on {day}")
            _remember(student_id, day, "free_meals", e.entitlement_id,
                      label, "ended")
        except Exception as exc:  # noqa: BLE001 — reported per entitlement
            logger.exception("Leaver %s: free meals #%d", student_id,
                             e.entitlement_id)
            lines.append(f"{label}: could not end — {exc}")
    return lines or ["Free meals: no active entitlement"]


def _onboarding(student_id: str, day: str) -> list[str]:
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding as _ob,
    )
    return _ob.close_for_leaver(student_id, day)


_STEPS = (("Class groups", _class_groups), ("Exam entries", _exam_entries),
          ("Bursary", _bursary), ("Free meals", _free_meals),
          ("Onboarding", _onboarding))


def on_left(student_id: str, day: str) -> list[str]:
    """Run every leaver step for *student_id* leaving on *day*
    (YYYY-MM-DD). Never raises; returns one line per outcome."""
    lines: list[str] = []
    for name, step in _STEPS:
        try:
            lines += step(student_id, day)
        except Exception as exc:  # noqa: BLE001 — one area never blocks the rest
            logger.exception("Leaver step %s for %s", name, student_id)
            lines.append(f"{name}: not done — {exc}")
    return lines


# ── Coming back ─────────────────────────────────────────────────────

_REDO: dict[str, str] = {
    "class_group": "re-add them to a class group for this subject if they "
                   "are returning to it",
    "exam_entry": "re-enter them if they are still sitting it (late entry "
                  "fees may apply)",
    "bursary": "set up the award again in Bursaries if they still qualify",
    "free_meals": "open a new free meals entitlement if they still qualify",
}


def on_returned(student_id: str) -> list[str]:
    """What staff must re-do for a learner whose leaving was undone.

    Reads the effects recorded on the most recent leaving and marks them
    as reported. Nothing is re-added automatically. Never raises.
    """
    try:
        with _db() as conn:
            last = conn.execute(
                "SELECT MAX(left_on) FROM enrolment_leaver_effects "
                "WHERE student_id = ? AND returned_at IS NULL",
                (student_id,)).fetchone()[0]
            if not last:
                return ["No leaver changes are waiting to be re-done"]
            rows = conn.execute(
                "SELECT * FROM enrolment_leaver_effects WHERE student_id = ? "
                "AND left_on = ? AND returned_at IS NULL ORDER BY effect_id",
                (student_id, last)).fetchall()
            conn.execute(
                "UPDATE enrolment_leaver_effects SET returned_at = "
                "datetime('now') WHERE student_id = ? AND returned_at IS NULL",
                (student_id,))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Leaver effects not read for %s", student_id)
        return [f"Could not read what changed when they left: {exc}"]
    return [f"{r['label']} was {r['action']} when they left on "
            f"{r['left_on']} — {_REDO.get(r['area'], 're-check it')}"
            for r in rows]


def effects_for(student_id: str) -> list[dict[str, Any]]:
    """Every recorded leaver effect for the learner, newest first."""
    with _db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM enrolment_leaver_effects WHERE student_id = ? "
            "ORDER BY effect_id DESC", (student_id,)).fetchall()]
