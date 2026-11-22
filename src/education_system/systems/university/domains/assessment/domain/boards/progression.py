"""Progression decisions at progression / award boards.

One outcome per student per board — progress, progress with trailing credit,
resit, repeat year, withdraw / terminate, or an exit award — recorded under
the same lock rules as the board's other decisions:

* only a progression/award board takes them, and only while it is open for
  decisions (agenda locked, convened or reopened) and the student is on its
  agenda;
* each outcome is also written as the board decision it implies
  (``continue`` / ``reassess`` / ``repeat`` / ``withdraw`` / ``award``) so the
  chair's "every agenda item decided" check and the minutes see it;
* recording a new outcome for the same student supersedes the old one (and
  its board decision); an outcome already rolled over cannot be changed here;
* progressing, or making an exit award, is refused while an academic
  integrity case is unsettled (as for awards);
* trailing credit is capped by the student's classification rule set
  (``max_trailing_credits``) and may only trail modules not yet passed;
* ratification ratifies the outcomes with the board (and the exit awards with
  the awards); reopening puts them under correction and withdraws release.

Release to the student is a separate, explicit step after ratification.
"""

from __future__ import annotations

import json
from typing import Any

from education_system.systems.university.application.assessment import (
    classification_rules,
    progression_rules,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.database.schemas import (
    progression_classification_schema as schema,
)

OUTCOMES = schema.OUTCOMES
LABELS = progression_rules.LABELS
#: Outcome -> the assessment_board_decisions.decision_type it implies.
DECISION_FOR = {"progress": "continue", "progress_trailing": "continue", "resit": "reassess",
                "repeat_year": "repeat", "withdraw": "withdraw", "exit_award": "award"}
_OPEN = {"agenda_locked", "convened", "reopened"}
_NEEDS_SETTLED = {"progress", "progress_trailing", "exit_award"}


def ensure(conn=None) -> None:
    if conn is not None:
        schema.apply_to_connection(conn)
        return
    with get_connection() as own:
        schema.apply_to_connection(own)


def _dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _open_board(conn, board_id, student_id):
    board = conn.execute("SELECT * FROM assessment_boards WHERE board_id = ?",
                         (board_id,)).fetchone()
    if board is None:
        raise ValueError(f"Assessment board {board_id} does not exist")
    if board["board_type"] != "progression_award":
        raise ValueError("Progression decisions are made at a progression/award board")
    if board["status"] not in _OPEN:
        raise ValueError("Board is not open for decisions")
    item = conn.execute("SELECT current_level FROM assessment_board_agenda WHERE board_id = ? "
                        "AND student_id = ?", (board_id, student_id)).fetchone()
    if item is None:
        raise ValueError("Student is not on this board's agenda")
    return board, item["current_level"]


def _unsettled(conn, student_id) -> str:
    from education_system.systems.university.application.integrity import (
        review as integrity_review,
    )
    cases = integrity_review.blocking_cases(conn, str(student_id), None)
    return ", ".join(f"case {c['id']}" for c in cases)


def _current(conn, board_id, student_id) -> dict | None:
    rows = _dicts(conn.execute(
        "SELECT * FROM board_progression_outcomes WHERE board_id = ? AND student_id = ? "
        "AND status != 'superseded' ORDER BY outcome_id DESC LIMIT 1", (board_id, student_id)))
    return rows[0] if rows else None


def _check_trailing(conn, student_id, modules) -> float:
    if not modules:
        raise ValueError("Name the module(s) carried as trailing credit")
    open_codes = {f["module_code"] for f in progression_rules.failed_modules(conn, student_id)}
    passed = [m for m in modules if m not in open_codes]
    if passed:
        raise ValueError("Only failed or referred modules can trail: " + ", ".join(passed))
    credits = progression_rules.module_credits(conn, modules)
    cap = classification_rules.max_trailing_credits(conn, student_id)
    if credits > cap:
        raise ValueError(f"{credits:g} trailing credits exceeds the {cap:g}-credit limit "
                         "in the student's regulations")
    return credits


def _exit_award(conn, student_id, named: str | None) -> tuple[str | None, str | None]:
    """``(award, classification)``: the named award, or the one the credit earns."""
    found = classification_rules.exit_award(conn, student_id)
    if named:
        if found and found["name"] == named:
            return named, found["classification"]
        return named, None
    return (found["name"], found["classification"]) if found else (None, None)


def _details(conn, student_id, outcome, *, trailing_modules, resit_modules, exit_award):
    """Validated outcome fields: trailing credit, resit modules, exit award."""
    out = {"trailing_modules": None, "trailing_credits": None, "resit_modules": None,
           "exit_award": None, "exit_classification": None}
    if outcome == "progress_trailing":
        out["trailing_credits"] = _check_trailing(conn, student_id, trailing_modules)
        out["trailing_modules"] = json.dumps(list(trailing_modules))
    elif outcome == "resit":
        modules = resit_modules or [f["module_code"]
                                    for f in progression_rules.failed_modules(conn, student_id)]
        out["resit_modules"] = json.dumps(list(modules))
    elif outcome in ("exit_award", "withdraw"):
        award, cls = _exit_award(conn, student_id, exit_award)
        if outcome == "exit_award" and not award:
            raise ValueError("The student's earned credit meets no exit award")
        out["exit_award"], out["exit_classification"] = award, cls
    return out


def _supersede(conn, board_id, student_id) -> tuple[int | None, int | None]:
    """Mark the student's current outcome superseded; ``(outcome_id, decision_id)``."""
    current = _current(conn, board_id, student_id)
    if current is None:
        return None, None
    if current["status"] == "rolled_over":
        raise ValueError("That outcome has already been rolled over; correct the student's "
                         "record in Student Records before recording a new one")
    conn.execute("UPDATE board_progression_outcomes SET status = 'superseded' "
                 "WHERE outcome_id = ?", (current["outcome_id"],))
    return current["outcome_id"], current["decision_id"]


def _board_decision(conn, board_id, student_id, outcome, details, rationale, decided_by,
                    supersedes) -> int:
    classification = (details["exit_classification"] or "Unclassified") \
        if outcome == "exit_award" else None
    cur = conn.execute(
        "INSERT INTO assessment_board_decisions (board_id, student_id, module_code, "
        "decision_type, credits_affected, classification, rationale, decided_by, "
        "supersedes_decision_id) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)",
        (board_id, student_id, DECISION_FOR[outcome], details["trailing_credits"],
         classification, f"{LABELS[outcome]}: {rationale}", decided_by, supersedes))
    conn.execute("UPDATE assessment_board_agenda SET status = 'decided' WHERE board_id = ? "
                 "AND student_id = ?", (board_id, student_id))
    conn.execute("UPDATE assessment_boards SET status = 'convened' WHERE board_id = ?",
                 (board_id,))
    return int(cur.lastrowid)


def record_outcome(board_id: int, student_id: str, outcome: str, *, decided_by: str,
                   rationale: str, trailing_modules: list[str] | None = None,
                   resit_modules: list[str] | None = None, exit_award: str | None = None,
                   to_year: int | None = None) -> int:
    """Record (or replace) the student's progression outcome at this board."""
    if outcome not in OUTCOMES:
        raise ValueError(f"Outcome must be one of {', '.join(OUTCOMES)}")
    if not (rationale or "").strip():
        raise ValueError("Give the board's rationale")
    with transaction() as conn:
        ensure(conn)
        board, level = _open_board(conn, board_id, student_id)
        if outcome in _NEEDS_SETTLED:
            held = _unsettled(conn, student_id)
            if held:
                raise ValueError(f"Academic integrity cases are not settled ({held}); defer "
                                 "the decision until they are decided")
        details = _details(conn, student_id, outcome, trailing_modules=trailing_modules,
                           resit_modules=resit_modules, exit_award=exit_award)
        proposal = progression_rules.propose(conn, student_id, level)
        from_year = proposal["from_year"]
        target = to_year if to_year is not None else progression_rules.target_year(
            outcome, from_year)
        old_outcome, old_decision = _supersede(conn, board_id, student_id)
        decision_id = _board_decision(conn, board_id, student_id, outcome, details,
                                      rationale.strip(), decided_by, old_decision)
        cur = conn.execute(
            "INSERT INTO board_progression_outcomes (board_id, student_id, academic_year, "
            "outcome, from_year, to_year, trailing_modules, trailing_credits, resit_modules, "
            "exit_award, exit_classification, proposed_outcome, rationale, decided_by, "
            "decision_id, supersedes_outcome_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (board_id, student_id, board["academic_year"], outcome, from_year, target,
             details["trailing_modules"], details["trailing_credits"], details["resit_modules"],
             details["exit_award"], details["exit_classification"], proposal["outcome"],
             rationale.strip(), decided_by, decision_id, old_outcome))
        return int(cur.lastrowid)


def propose(board_id: int, student_id: str) -> dict[str, Any]:
    """What the rules propose for the student (read-only)."""
    with get_connection() as conn:
        ensure(conn)
        item = conn.execute("SELECT current_level FROM assessment_board_agenda WHERE "
                            "board_id = ? AND student_id = ?", (board_id, student_id)).fetchone()
        if item is None:
            raise ValueError("Student is not on this board's agenda")
        result = progression_rules.propose(conn, student_id, item["current_level"])
        exit_found = classification_rules.exit_award(conn, student_id)
        result["exit_award"] = exit_found["name"] if exit_found else None
        result["label"] = LABELS.get(result["outcome"] or "", "No proposal")
        return result


def outcomes(board_id: int, include_superseded: bool = False) -> list[dict[str, Any]]:
    with get_connection() as conn:
        ensure(conn)
        sql = "SELECT * FROM board_progression_outcomes WHERE board_id = ?"
        if not include_superseded:
            sql += " AND status != 'superseded'"
        return _dicts(conn.execute(sql + " ORDER BY student_id, outcome_id", (board_id,)))


# ── hooks called by the board service inside its transaction ────────────


def exit_awards(conn, board_id) -> dict[str, tuple[str, str | None]]:
    """``{student_id: (award name, classification)}`` for the board's current
    exit-award and withdraw-with-exit-award outcomes."""
    ensure(conn)
    return {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT student_id, exit_award, exit_classification FROM board_progression_outcomes "
        "WHERE board_id = ? AND status IN ('provisional', 'under_correction') "
        "AND exit_award IS NOT NULL AND outcome IN ('exit_award', 'withdraw')", (board_id,))}


def ratify_outcomes(conn, board, ratified_by: str, now: str) -> int:
    """Ratify the board's current outcomes and publish each one."""
    ensure(conn)
    rows = _dicts(conn.execute(
        "SELECT outcome_id, student_id, outcome FROM board_progression_outcomes "
        "WHERE board_id = ? AND status IN ('provisional', 'under_correction')",
        (board["board_id"],)))
    if not rows:
        return 0
    from education_system.systems.university.infrastructure.events import (
        transactional_publisher,
    )
    for row in rows:
        conn.execute("UPDATE board_progression_outcomes SET status = 'ratified', "
                     "ratified_at = ?, ratified_by = ? WHERE outcome_id = ?",
                     (now, ratified_by, row["outcome_id"]))
        transactional_publisher.publish(
            conn, "progression.outcome.ratified",
            {"outcome_id": row["outcome_id"], "board_id": board["board_id"],
             "student_id": row["student_id"], "outcome": row["outcome"],
             "academic_year": board["academic_year"]},
            aggregate_id=str(row["student_id"]),
            idempotency_key=f"progression:{row['outcome_id']}:ratified")
    return len(rows)


def on_reopen(conn, board_id) -> None:
    """A reopened board's ratified outcomes go back under correction, unreleased."""
    ensure(conn)
    conn.execute("UPDATE board_progression_outcomes SET status = 'under_correction', "
                 "released = 0 WHERE board_id = ? AND status = 'ratified'", (board_id,))


# ── release, rollover and the student's view ────────────────────────────


def release(board_id: int, *, released_by: str) -> int:
    """Release the ratified board's outcomes to its students; returns how many."""
    emails: list = []
    with transaction() as conn:
        ensure(conn)
        status = conn.execute("SELECT status FROM assessment_boards WHERE board_id = ?",
                              (board_id,)).fetchone()
        if status is None or status[0] != "ratified":
            raise ValueError("Outcomes are released only after the board is ratified")
        rows = _dicts(conn.execute(
            "SELECT outcome_id, student_id, outcome FROM board_progression_outcomes WHERE "
            "board_id = ? AND status IN ('ratified', 'rolled_over') AND released = 0",
            (board_id,)))
        for row in rows:
            conn.execute("UPDATE board_progression_outcomes SET released = 1, "
                         "released_at = datetime('now'), released_by = ? WHERE outcome_id = ?",
                         (released_by, row["outcome_id"]))
            emails += _notify(conn, row)
    _send(emails)
    return len(rows)


def _notify(conn, row) -> list:
    from education_system.systems.university.application.research import access
    subject = "Your progression outcome"
    body = (f"The assessment board has confirmed your progression outcome: "
            f"{LABELS[row['outcome']]}. You can see the details under Assessment Boards / "
            "My Progression Outcome. If you believe there are grounds, you may submit an "
            "academic appeal.")
    return access.notify(conn, [row["student_id"]], subject, body)


def _send(emails) -> None:
    from education_system.systems.university.application.teaching.occurrences import (
        send_emails,
    )
    send_emails(emails)


def rollover(board_id: int, *, actor_id: str) -> dict[str, Any]:
    """Apply the ratified board's outcomes (see ``progression_rules.rollover``)."""
    with transaction() as conn:
        result = progression_rules.rollover(conn, board_id, actor_id)
    progression_rules.after_rollover(result)
    return result


def student_id_for(user: dict | None) -> str | None:
    """The signed-in student's student number, resolved by username (the auth.db
    id is a different id space); None for anyone who is not a student."""
    user = user or {}
    if str(user.get("role") or "").lower() != "student":
        return None
    if user.get("student_id"):
        return str(user["student_id"])
    username = str(user.get("username") or "")
    with get_connection() as conn:
        row = conn.execute("SELECT student_id FROM users WHERE username = ? "
                           "AND student_id IS NOT NULL", (username,)).fetchone()
        if row and row[0]:
            return str(row[0])
        row = conn.execute("SELECT student_id FROM students WHERE student_id = ?",
                           (username,)).fetchone()
    return str(row[0]) if row else None


def my_outcomes(student_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return progression_rules.student_outcomes(conn, student_id)


__all__ = ["DECISION_FOR", "LABELS", "OUTCOMES", "exit_awards", "my_outcomes", "on_reopen",
           "outcomes", "propose", "student_id_for", "ratify_outcomes", "record_outcome", "release", "rollover"]
