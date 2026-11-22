"""Attendance: AM/PM session marks for pupils on roll.

Marks follow the school register meaning (the DfE code is shown alongside):
present and late count as attending, as does approved off-site education
(B); "attending another school" (D, dual registration) and "not required"
(X) don't count as a possible session at all.

Rules: no marks for future dates or for pupils who aren't on roll (or were
not on roll then), one mark per pupil per session, and an authorised absence needs a
reason. Below 90% is **persistent absence**.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.alternative_provision.infrastructure import database as db
from education_system.systems.alternative_provision.modules import learners

MARKS = ("Present (/ \\)", "Late (L)", "Off-site education (B)", "Authorised absence (C)",
         "Illness (I)", "Medical appointment (M)", "Suspended / excluded (E)",
         "Unauthorised absence (O)", "Attending other school (D)", "Not required (X)")
ATTENDING = frozenset(MARKS[:3])
NOT_POSSIBLE = frozenset({"Attending other school (D)", "Not required (X)"})
ABSENT = frozenset(MARKS) - ATTENDING - NOT_POSSIBLE
SESSIONS = ("AM", "PM")
PERSISTENT_ABSENCE = 90.0


def _today() -> str:
    return date.today().isoformat()


def _check_mark(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    on = r.to_date(merged.get("session_date"))
    if on and on > date.today():
        raise ValidationError("Attendance can't be marked for a future session.")
    pupil = r.get(learners.LEARNERS, int(merged["learner_id"]))
    if pupil is None:
        raise ValidationError("Choose the pupil.")
    start, left = r.to_date(pupil.get("start_date")), r.to_date(pupil.get("leave_date"))
    on_roll = pupil["status"] == "On roll" or (left and on and on <= left)
    if not on_roll or (start and on and on < start):
        raise ValidationError(f"{learners.pupil_label(pupil)} wasn't on roll on that day.")
    if merged.get("mark") in ABSENT - {"Suspended / excluded (E)"} and \
            merged.get("mark") != "Unauthorised absence (O)" and not merged.get("reason"):
        raise ValidationError("Give the reason for an authorised absence.")
    with db.connect() as conn:
        dup = conn.execute("SELECT 1 FROM attendance WHERE learner_id = ? AND session_date = ? "
                           "AND session = ? AND id IS NOT ?",
                           (merged["learner_id"], on.isoformat() if on else None,
                            merged.get("session"), (old or {}).get("id"))).fetchone()
    if dup:
        raise ValidationError("That pupil already has a mark for this session.")


ATTENDANCE = RecordType(
    key="attendance", title="Attendance Marks", singular="attendance mark",
    order_by="session_date DESC, session DESC, id DESC", check=_check_mark,
    filters=("mark", "session"),
    describe=lambda row: f"{row.get('session_date')} {row.get('session')} {row.get('mark')}",
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("session_date", "Date", "date", required=True, default=_today),
        Field("session", "Session", "choice", SESSIONS, required=True, default="AM"),
        Field("mark", "Mark", "choice", MARKS, required=True, default=MARKS[0]),
        Field("reason", "Reason / note"),
        Field("contact_made", "First-day contact made", "bool", listed=False,
              help="For an absence: parent / carer contacted"),
    ),
)


def register(on: date, session: str) -> list[dict]:
    """Pupils on roll on *on*, with any mark already made for *session*."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT l.id AS learner_id, l.first_name || ' ' || l.last_name AS name, "
            "l.pupil_ref, a.mark, a.reason, a.id AS mark_id FROM learners l "
            "LEFT JOIN attendance a ON a.learner_id = l.id AND a.session_date = ? "
            "AND a.session = ? WHERE (l.status = 'On roll' OR (l.leave_date >= ? AND "
            "l.status IN ('Reintegrated', 'Left'))) AND (l.start_date IS NULL OR "
            "l.start_date <= ?) ORDER BY l.last_name, l.first_name",
            (on.isoformat(), session, on.isoformat(), on.isoformat()))
        return [dict(x) for x in rows]


def save_register(on: date, session: str, marks: dict[int, tuple[str, str]], *,
                  actor: str) -> int:
    """Save a register: learner_id -> (mark, reason). Returns marks written."""
    existing = {x["learner_id"]: x["mark_id"] for x in register(on, session)}
    n = 0
    for learner_id, (mark, reason) in marks.items():
        if not mark:
            continue
        r.save(ATTENDANCE, {"learner_id": learner_id, "session_date": on.isoformat(),
                            "session": session, "mark": mark, "reason": reason or None},
               record_id=existing.get(learner_id), actor=actor)
        n += 1
    return n


def rate(learner_id: int | None = None, *, days: int | None = None) -> float | None:
    """Attendance % (attending / possible sessions), for one pupil or everyone,
    over the last *days* days (all time if None)."""
    sql = "SELECT mark FROM attendance WHERE 1 = 1"
    args: list = []
    if learner_id is not None:
        sql += " AND learner_id = ?"
        args.append(learner_id)
    if days is not None:
        sql += " AND session_date >= ?"
        args.append((date.today() - timedelta(days=days)).isoformat())
    with db.connect() as conn:
        marks = [m[0] for m in conn.execute(sql, args)]
    possible = [m for m in marks if m not in NOT_POSSIBLE]
    if not possible:
        return None
    return round(100 * sum(m in ATTENDING for m in possible) / len(possible), 1)


def short(mark: str) -> str:
    """The register letter for a mark, e.g. 'Late (L)' -> 'L'."""
    return mark[mark.rfind("(") + 1:-1] if "(" in mark else mark
