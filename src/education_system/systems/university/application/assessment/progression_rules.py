"""Progression outcomes: the board's proposal, the registration permit, rollover.

* :func:`propose` turns the programme's progression rule
  (``programmes.record.progression``) and the student's failed modules into a
  proposed outcome for the board. The board decides; nothing is applied here.
* :func:`registration_permit` is what annual re-registration
  (``student_lifecycle.register``) asks: the student's latest *ratified*
  progression outcome decides whether they may re-register and as what. A
  student with no board outcome on record keeps today's behaviour.
* :func:`rollover` applies a ratified board's outcomes: ``progress`` and
  ``progress_trailing`` advance the year of study (FHEQ level = year + 3),
  ``withdraw`` withdraws the student through the lifecycle, ``resit`` /
  ``repeat_year`` keep the year (re-registration then records the matching
  registration type), and ``exit_award`` leaves the student for conferral.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json

from education_system.systems.university.application.assessment import (
    classification,
    classification_rules,
)
from education_system.systems.university.infrastructure.database.schemas import (
    progression_classification_schema as schema,
)

LABELS = {
    "progress": "Progress",
    "progress_trailing": "Progress with trailing credit",
    "resit": "Resit (reassessment)",
    "repeat_year": "Repeat year",
    "withdraw": "Withdraw / terminate studies",
    "exit_award": "Exit award",
}
#: Outcome -> the registration type re-registration records under it.
REGISTRATION_TYPES = {
    "progress": "re-registration",
    "progress_trailing": "re-registration (trailing credit)",
    "resit": "resit registration",
    "repeat_year": "repeat-year registration",
}
_RECORD_TO_OUTCOME = {"progress": "progress", "progress with compensation": "progress",
                      "resit required": "resit"}
_PENDING = ("provisional", "under_correction")
_FINAL = ("ratified", "rolled_over")


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


def _dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def _student_columns(conn) -> set:
    return {r[1] for r in conn.execute("PRAGMA table_info(students)")}


# ── the student's year and failed modules ───────────────────────────────


def current_year(conn, student_id, level_hint: str | None = None) -> int:
    """Year of study from the student record, else the agenda's level, else 1."""
    cols = _student_columns(conn)
    picks = [c for c in ("year_of_study", "year") if c in cols]
    if picks:
        # db-audit: ignore[DBW001] - column names come from PRAGMA
        row = conn.execute(f"SELECT {', '.join(picks)} FROM students WHERE student_id = ?",
                           (str(student_id),)).fetchone()
        for value in tuple(row or ()):
            try:
                if 1 <= int(value) <= 8:
                    return int(value)
            except (TypeError, ValueError):
                continue
    digits = "".join(ch for ch in str(level_hint or "") if ch.isdigit())
    if digits and 4 <= int(digits) <= 8:
        return int(digits) - 3
    return 1


def failed_modules(conn, student_id, pass_mark: float | None = None) -> list[dict]:
    """Modules with a result below the pass mark, or awaiting a resit."""
    floor = classification.PASS_MARK if pass_mark is None else pass_mark
    return _dicts(conn.execute(
        "SELECT mg.module_code, mg.final_score AS mark, COALESCE(m.credits, 0) AS credits, "
        "COALESCE(mg.status, 'provisional') AS status FROM module_grades mg "
        "LEFT JOIN modules m ON m.module_code = mg.module_code WHERE mg.student_id = ? "
        "AND ((mg.final_score IS NOT NULL AND mg.final_score < ?) "
        "     OR COALESCE(mg.status, '') = 'awaiting_resit') ORDER BY mg.module_code",
        (str(student_id), floor)))


def module_credits(conn, codes) -> float:
    codes = [c for c in codes or [] if c]
    if not codes:
        return 0.0
    marks = ", ".join("?" for _ in codes)
    # db-audit: ignore[DBW001] - placeholders only
    row = conn.execute(f"SELECT COALESCE(SUM(COALESCE(credits, 0)), 0) FROM modules "
                       f"WHERE module_code IN ({marks})", codes).fetchone()
    return float(row[0] or 0)


# ── proposal ────────────────────────────────────────────────────────────


def _course_code(conn, student_id) -> str | None:
    row = conn.execute("SELECT course FROM students WHERE student_id = ?",
                       (str(student_id),)).fetchone()
    return row[0] if row and row[0] else None


def _programme_rule(conn, student_id, year) -> dict | None:
    """``programmes.record.progression`` when the course has a progression rule."""
    code = _course_code(conn, student_id)
    if not code:
        return None
    from education_system.systems.university.application.programmes import record
    try:
        return record.progression(conn, student_id, code, year)
    except ValueError:
        return None


def propose(conn, student_id, level_hint: str | None = None) -> dict:
    """The outcome the rules point to: ``{outcome, reason, from_year, to_year,
    trailing_modules, resit_modules, exit_award}`` (``outcome`` None when marks
    are outstanding)."""
    year = current_year(conn, student_id, level_hint)
    failed = failed_modules(conn, student_id)
    failed_codes = [f["module_code"] for f in failed]
    rule = _programme_rule(conn, student_id, year)
    base = {"from_year": year, "to_year": None, "trailing_modules": [], "resit_modules": [],
            "exit_award": None}
    if rule is not None and rule["outcome"] in ("incomplete", "no results for this year"):
        return dict(base, outcome=None, reason=f"Programme rule: {rule['outcome']}")
    outcome = _RECORD_TO_OUTCOME.get(rule["outcome"]) if rule else None
    reason = f"Programme rule: {rule['outcome']} ({rule['passed_credits']:g} of " \
             f"{rule['required']:g} credits)" if rule else "No programme progression rule; " \
             "proposed from failed modules"
    if outcome is None:
        outcome = "progress" if not failed else "resit"
    if outcome == "resit":
        cap = classification_rules.max_trailing_credits(conn, student_id)
        credit = sum(float(f["credits"] or 0) for f in failed)
        if failed and 0 < credit <= cap:
            return dict(base, outcome="progress_trailing", to_year=year + 1,
                        trailing_modules=failed_codes,
                        reason=f"{reason}; {credit:g} failed credits within the "
                               f"{cap:g}-credit trailing limit")
        return dict(base, outcome="resit", to_year=year, resit_modules=failed_codes,
                    reason=reason)
    return dict(base, outcome="progress", to_year=year + 1, reason=reason)


def target_year(outcome: str, from_year: int) -> int | None:
    if outcome in ("progress", "progress_trailing"):
        return from_year + 1
    if outcome in ("resit", "repeat_year"):
        return from_year
    return None


# ── registration permit ─────────────────────────────────────────────────


def _latest(conn, student_id, statuses) -> dict | None:
    marks = ", ".join("?" for _ in statuses)
    # db-audit: ignore[DBW001] - placeholders only
    rows = _dicts(conn.execute(
        f"SELECT * FROM board_progression_outcomes WHERE student_id = ? AND status IN ({marks}) "
        "ORDER BY outcome_id DESC LIMIT 1", (str(student_id), *statuses)))
    return rows[0] if rows else None


def registration_permit(conn, student_id) -> dict:
    """May the student re-register, and as what?

    ``{allowed, registration_type, outcome, outcome_id, repeat_year, reason}``.
    Withdrawn / terminated students and students given an exit award may not;
    a decision still awaiting ratification (or under correction) holds
    re-registration until the board ratifies it.
    """
    none = {"allowed": True, "registration_type": None, "outcome": None, "outcome_id": None,
            "repeat_year": None, "reason": "No progression outcome on record"}
    if not _has_table(conn, "board_progression_outcomes"):
        return none
    final = _latest(conn, student_id, _FINAL)
    pending = _latest(conn, student_id, _PENDING)
    if pending and (final is None or pending["outcome_id"] > final["outcome_id"]):
        return dict(none, allowed=False, outcome=pending["outcome"],
                    outcome_id=pending["outcome_id"],
                    reason=f"Progression decision at board #{pending['board_id']} is awaiting "
                           "ratification")
    if final is None:
        return none
    outcome = final["outcome"]
    result = dict(none, outcome=outcome, outcome_id=final["outcome_id"],
                  reason=f"Ratified outcome: {LABELS[outcome]} (board #{final['board_id']})")
    if outcome not in REGISTRATION_TYPES:
        return dict(result, allowed=False)
    return dict(result, registration_type=REGISTRATION_TYPES[outcome],
                repeat_year=final["from_year"] if outcome == "repeat_year" else None)


# ── rollover ────────────────────────────────────────────────────────────


def _set_year(conn, student_id, year) -> None:
    cols = _student_columns(conn)
    sets = [c for c in ("year_of_study", "year") if c in cols]
    if sets:
        # db-audit: ignore[DBW001] - column names come from PRAGMA
        conn.execute(f"UPDATE students SET {', '.join(f'{c} = ?' for c in sets)} "
                     "WHERE student_id = ?", (*([int(year)] * len(sets)), str(student_id)))


def _withdraw(conn, student_id, actor, board_id) -> tuple[str, int | None]:
    from education_system.systems.university.domains.learners.domain import student_lifecycle
    from education_system.systems.university.services.boundary_errors import (
        EnrolmentBoundaryError,
    )
    try:
        history_id, _ = student_lifecycle.apply_status_change(
            conn, str(student_id), "withdraw", actor_id=actor,
            reason=f"Progression outcome at assessment board #{board_id}")
    except EnrolmentBoundaryError as exc:
        return f"not withdrawn: {exc}", None
    return "withdrawn", int(history_id)


def _apply_one(conn, row, actor) -> tuple[str, int | None]:
    outcome, sid = row["outcome"], row["student_id"]
    if outcome in ("progress", "progress_trailing"):
        _set_year(conn, sid, row["to_year"])
        note = f"advanced to year {row['to_year']} (Level {int(row['to_year']) + 3})"
        if outcome == "progress_trailing":
            note += "; trailing " + ", ".join(json.loads(row["trailing_modules"] or "[]"))
        return note, None
    if outcome in ("resit", "repeat_year"):
        return f"stays in year {row['from_year']}; may re-register as " \
               f"{REGISTRATION_TYPES[outcome]}", None
    if outcome == "withdraw":
        return _withdraw(conn, sid, actor, row["board_id"])
    return f"exit award {row['exit_award']} ratified; confer it in Graduation", None


def rollover(conn, board_id, actor) -> dict:
    """Apply every ratified, not yet rolled-over outcome of a ratified board.

    Returns ``{applied: [{student_id, outcome, note}], lifecycle: [(sid, history_id)]}``;
    publish each lifecycle change with ``student_lifecycle.publish_change`` after commit.
    """
    ensure(conn)
    board = conn.execute("SELECT status FROM assessment_boards WHERE board_id = ?",
                         (board_id,)).fetchone()
    if board is None:
        raise ValueError(f"Assessment board {board_id} does not exist")
    if board[0] != "ratified":
        raise ValueError("Only a ratified board's outcomes can be rolled over")
    rows = _dicts(conn.execute("SELECT * FROM board_progression_outcomes WHERE board_id = ? "
                               "AND status = 'ratified' ORDER BY outcome_id", (board_id,)))
    applied, lifecycle = [], []
    for row in rows:
        note, history_id = _apply_one(conn, row, actor)
        if history_id:
            lifecycle.append((row["student_id"], history_id))
        conn.execute("UPDATE board_progression_outcomes SET status = 'rolled_over', "
                     "rolled_over_at = datetime('now'), rolled_over_by = ?, rollover_note = ? "
                     "WHERE outcome_id = ?", (actor, note, row["outcome_id"]))
        applied.append({"student_id": row["student_id"], "outcome": row["outcome"],
                        "note": note})
    return {"applied": applied, "lifecycle": lifecycle}


def after_rollover(result) -> None:
    """Post-commit: publish the lifecycle changes a rollover made."""
    if not result.get("lifecycle"):
        return
    from education_system.systems.university.domains.learners.domain import student_lifecycle
    for student_id, history_id in result["lifecycle"]:
        student_lifecycle.publish_change(student_id, "withdraw", history_id)


# ── the student's own view ──────────────────────────────────────────────


def student_outcomes(conn, student_id) -> list[dict]:
    """The student's released outcomes, newest first (nothing before release)."""
    if not _has_table(conn, "board_progression_outcomes"):
        return []
    rows = _dicts(conn.execute(
        "SELECT o.outcome_id, o.board_id, b.name AS board_name, o.academic_year, o.outcome, "
        "o.from_year, o.to_year, o.trailing_modules, o.resit_modules, o.exit_award, "
        "o.exit_classification, o.rationale, o.ratified_at, o.released_at, o.status "
        "FROM board_progression_outcomes o JOIN assessment_boards b ON b.board_id = o.board_id "
        "WHERE o.student_id = ? AND o.released = 1 AND o.status IN ('ratified', 'rolled_over') "
        "ORDER BY o.outcome_id DESC", (str(student_id),)))
    for row in rows:
        row["label"] = LABELS[row["outcome"]]
        row["trailing_modules"] = json.loads(row["trailing_modules"] or "[]")
        row["resit_modules"] = json.loads(row["resit_modules"] or "[]")
    return rows


__all__ = ["LABELS", "REGISTRATION_TYPES", "current_year", "failed_modules", "module_credits",
           "propose", "registration_permit", "rollover", "after_rollover", "student_outcomes", "target_year"]
