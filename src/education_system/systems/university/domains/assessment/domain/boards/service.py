"""Formal module, progression and award board processing.

Academic integrity cases that are not settled (``integrity_review
.blocking_cases``) hold a student's results: the agenda flags them, an
award or a pass / compensate / condone decision on an affected module is
refused (defer it until the case is decided), confirmation leaves those
modules unlocked so a penalty can still be applied, and ratification is
refused while an award student has one.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.database.schema_version import (
    require_tables,
)
from education_system.systems.university.application.assessment import (
    classification,
    classification_rules,
    module_results,
)
from education_system.systems.university.domains.assessment.domain.boards import (
    progression,
)

BOARD_TYPES = frozenset({"module", "progression_award"})
DECISIONS = frozenset(
    {
        "pass",
        "fail",
        "compensate",
        "condone",
        "reassess",
        "continue",
        "repeat",
        "withdraw",
        "award",
    }
)


def ensure_schema() -> None:
    """Validate the Alembic-owned schema without mutating it."""
    require_tables(
        ("assessment_boards", frozenset({"board_id"})),
        ("assessment_board_members", frozenset({"board_id"})),
        ("assessment_board_rules", frozenset({"rule_id"})),
        ("assessment_board_agenda", frozenset({"agenda_id"})),
        ("assessment_board_decisions", frozenset({"decision_id"})),
        ("assessment_board_minutes", frozenset({"board_id"})),
        ("ratified_student_awards", frozenset({"award_id"})),
        ("assessment_board_corrections", frozenset({"correction_id"})),
    )


#: Module decisions that would settle a result an integrity case may still change.
_SETTLING_DECISIONS = frozenset({"pass", "compensate", "condone"})


def _blocking(conn, student_id, module_code=None) -> list[dict]:
    from education_system.systems.university.application.integrity import (
        review as integrity_review,
    )
    return integrity_review.blocking_cases(conn, str(student_id), module_code)


def _case_list(cases) -> str:
    return ", ".join(f"case {c['id']}" + (f" ({c['module_code']})" if c["module_code"] else "")
                     for c in cases)


def _board(conn, board_id: int):
    row = conn.execute("SELECT * FROM assessment_boards WHERE board_id = ?", (board_id,)).fetchone()
    if row is None:
        raise ValueError(f"Assessment board {board_id} does not exist")
    return row


def create_board(
    board_type: str,
    name: str,
    academic_year: str,
    *,
    created_by: str,
    programme_code: str | None = None,
    module_code: str | None = None,
    meeting_at: str | None = None,
    chair_id: str | None = None,
) -> int:
    ensure_schema()
    if board_type not in BOARD_TYPES:
        raise ValueError(f"Unknown board type {board_type!r}")
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO assessment_boards
                 (board_type, name, academic_year, programme_code,
                  module_code, meeting_at, chair_id, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                board_type,
                name,
                academic_year,
                programme_code,
                module_code,
                meeting_at,
                chair_id,
                created_by,
            ),
        )
        return int(cur.lastrowid)


def add_member(board_id: int, member_id: str, role: str) -> None:
    ensure_schema()
    with transaction() as conn:
        board = _board(conn, board_id)
        if board["status"] not in {"draft", "reopened"}:
            raise ValueError("Membership is locked for this board")
        conn.execute(
            "INSERT INTO assessment_board_members VALUES (?, ?, ?)",
            (board_id, member_id, role),
        )


def add_rule(
    board_id: int,
    rule_type: str,
    *,
    minimum_mark: float | None = None,
    maximum_credits: float | None = None,
    exclude_core_modules: bool = True,
    notes: str = "",
) -> int:
    """Configure a compensation or condonation rule for a board."""
    ensure_schema()
    if rule_type not in {"compensation", "condonation"}:
        raise ValueError("rule_type must be compensation or condonation")
    with transaction() as conn:
        board = _board(conn, board_id)
        if board["status"] not in {"draft", "reopened"}:
            raise ValueError("Rules are locked for this board")
        cur = conn.execute(
            """INSERT INTO assessment_board_rules
                 (board_id, rule_type, minimum_mark, maximum_credits,
                  exclude_core_modules, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (board_id, rule_type, minimum_mark, maximum_credits, int(exclude_core_modules), notes),
        )
        return int(cur.lastrowid)


def _agenda_filters(board):
    filters, params = ["s.status IN ('Active', 'Completed')"], []
    if board["programme_code"]:
        filters.append("s.course = ?")
        params.append(board["programme_code"])
    if board["module_code"]:
        filters.append("sm.module_code = ?")
        params.append(board["module_code"])
    return filters, params


def _agenda_entry(conn, board, student_id):
    """Average, credits, level, classification and flags from module results.

    Read from ``module_grades`` — where results actually live. This used to
    average ``student_modules.grade``, which nothing filled in, so every
    agenda showed blank averages.
    """
    where, params = "mg.student_id = ?", [student_id]
    if board["module_code"]:
        where += " AND mg.module_code = ?"
        params.append(board["module_code"])
    rows = conn.execute(
        "SELECT mg.module_code, mg.final_score, mg.outcome, mg.is_complete, m.year, "
        "       COALESCE(m.credits, 0) FROM module_grades mg "
        "LEFT JOIN modules m ON m.module_code = mg.module_code "
        f"WHERE {where} AND mg.final_score IS NOT NULL", params).fetchall()  # nosec B608
    if not rows:
        return None
    weights = [(float(r[1]), float(r[5]) or 1.0) for r in rows]
    average = round(sum(m * w for m, w in weights) / sum(w for _, w in weights), 2)
    passed_credits = sum(float(r[5]) for r in rows if r[1] >= classification.PASS_MARK and r[3])
    levels = [lvl for lvl in (classification.module_level(r[0], r[4]) for r in rows) if lvl]
    flags = _agenda_flags(conn, student_id, rows)
    proposed = None
    if board["board_type"] == "progression_award":
        # The student's regulation-bound rule set (the university default when unbound).
        degree = classification_rules.classify(conn, student_id)
        proposed = degree["classification"]
        if degree.get("raised"):
            flags.append("borderline raised under " + degree["rule_set"])
        elif degree["borderline"]:
            flags.append("borderline classification")
        if degree["scheme"] != "default":
            flags.append("rules: " + degree["rule_set"])
    return {"average": average, "credits": passed_credits,
            "level": f"Level {max(levels)}" if levels else None,
            "classification": proposed, "flags": "; ".join(flags) or None}


def _agenda_flags(conn, student_id, rows) -> list[str]:
    """What the board should look at: fails, incomplete modules, compensation."""
    flags = []
    fails = [r[0] for r in rows if r[1] < classification.PASS_MARK and r[3]]
    if fails:
        flags.append("fails: " + ", ".join(fails))
    incomplete = [r[0] for r in rows if not r[3]]
    if incomplete:
        flags.append("incomplete: " + ", ".join(incomplete))
    compensable = classification.compensation_candidates(conn, student_id)
    if compensable:
        flags.append("compensation possible: " + ", ".join(c["module_code"] for c in compensable))
    cases = _blocking(conn, student_id)
    if cases:
        flags.append("open integrity case(s): " + _case_list(cases))
    return flags


def generate_agenda(board_id: int) -> int:
    """Build the cohort agenda from the students' module results."""
    ensure_schema()
    with transaction() as conn:
        board = _board(conn, board_id)
        if board["status"] not in {"draft", "reopened"}:
            raise ValueError("Agenda can only be generated for an editable board")
        filters, params = _agenda_filters(board)
        # db-audit: ignore[DBW001] - join over a code-controlled list
        students = conn.execute(
            f"""SELECT DISTINCT s.student_id, s.course
                  FROM students s
                  LEFT JOIN student_modules sm ON sm.student_id = s.student_id
                 WHERE {" AND ".join(filters)}""",
            params,
        ).fetchall()
        added = 0
        for student in students:
            entry = _agenda_entry(conn, board, student["student_id"])
            if entry is None:
                continue
            conn.execute(
                """INSERT INTO assessment_board_agenda
                     (board_id, student_id, programme_code, current_level,
                      credits, average_mark, proposed_classification, flags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(board_id, student_id) DO UPDATE SET
                     programme_code=excluded.programme_code,
                     current_level=excluded.current_level,
                     credits=excluded.credits,
                     average_mark=excluded.average_mark,
                     proposed_classification=excluded.proposed_classification,
                     flags=excluded.flags""",
                (board_id, student["student_id"], student["course"], entry["level"],
                 entry["credits"], entry["average"], entry["classification"], entry["flags"]),
            )
            added += 1
        return added


def lock_agenda(board_id: int, *, actor_id: str) -> None:
    ensure_schema()
    with transaction() as conn:
        board = _board(conn, board_id)
        if board["status"] not in {"draft", "reopened"}:
            raise ValueError("Board agenda cannot be locked from this state")
        count = conn.execute(
            "SELECT COUNT(*) FROM assessment_board_agenda WHERE board_id = ?",
            (board_id,),
        ).fetchone()[0]
        if not count:
            raise ValueError("Cannot lock an empty agenda")
        conn.execute(
            "UPDATE assessment_boards SET status = 'agenda_locked' WHERE board_id = ?", (board_id,)
        )


def record_decision(
    board_id: int,
    student_id: str,
    decision_type: str,
    *,
    decided_by: str,
    rationale: str,
    module_code: str | None = None,
    original_result: str | None = None,
    confirmed_result: str | None = None,
    credits_affected: float | None = None,
    classification: str | None = None,
    supersedes_decision_id: int | None = None,
) -> int:
    ensure_schema()
    if decision_type not in DECISIONS:
        raise ValueError(f"Unknown board decision {decision_type!r}")
    with transaction() as conn:
        board = _board(conn, board_id)
        if board["status"] not in {"agenda_locked", "convened", "reopened"}:
            raise ValueError("Board is not open for decisions")
        item = conn.execute(
            "SELECT 1 FROM assessment_board_agenda WHERE board_id = ? AND student_id = ?",
            (board_id, student_id),
        ).fetchone()
        if item is None:
            raise ValueError("Student is not on this board's agenda")
        if decision_type == "award" and not classification:
            raise ValueError("Award decisions require a classification")
        if decision_type == "award" or (decision_type in _SETTLING_DECISIONS and module_code):
            cases = _blocking(conn, student_id,
                              None if decision_type == "award" else module_code)
            if cases:
                raise ValueError("This student has academic integrity cases not yet settled ("
                                 + _case_list(cases) + "). Defer the decision until the case "
                                 "is decided.")
        if decision_type in {"compensate", "condone"}:
            rule_type = "compensation" if decision_type == "compensate" else "condonation"
            rule = conn.execute(
                """SELECT * FROM assessment_board_rules
                    WHERE board_id = ? AND rule_type = ? AND active = 1
                    ORDER BY rule_id DESC LIMIT 1""",
                (board_id, rule_type),
            ).fetchone()
            if rule is None:
                raise ValueError(f"No active {rule_type} rule for this board")
            if rule["maximum_credits"] is not None and (
                credits_affected is None or credits_affected > rule["maximum_credits"]
            ):
                raise ValueError(f"{rule_type.title()} exceeds the permitted credit limit")
            try:
                result_mark = float(confirmed_result)
            except (TypeError, ValueError):
                result_mark = None
            if rule["minimum_mark"] is not None and (
                result_mark is None or result_mark < rule["minimum_mark"]
            ):
                raise ValueError(f"{rule_type.title()} result is below the minimum mark")
        cur = conn.execute(
            """INSERT INTO assessment_board_decisions
                 (board_id, student_id, module_code, decision_type,
                  original_result, confirmed_result, credits_affected,
                  classification, rationale, decided_by,
                  supersedes_decision_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                board_id,
                student_id,
                module_code,
                decision_type,
                original_result,
                confirmed_result,
                credits_affected,
                classification,
                rationale,
                decided_by,
                supersedes_decision_id,
            ),
        )
        conn.execute(
            "UPDATE assessment_board_agenda SET status = 'decided', "
            "proposed_classification = COALESCE(?, proposed_classification) "
            "WHERE board_id = ? AND student_id = ?",
            (classification, board_id, student_id),
        )
        conn.execute(
            "UPDATE assessment_boards SET status = 'convened' WHERE board_id = ?", (board_id,)
        )
        return int(cur.lastrowid)


def save_minutes(board_id: int, minutes_text: str, *, actor_id: str) -> None:
    ensure_schema()
    digest = hashlib.sha256(minutes_text.encode("utf-8")).hexdigest()
    with transaction() as conn:
        board = _board(conn, board_id)
        existing = conn.execute(
            "SELECT locked FROM assessment_board_minutes WHERE board_id = ?",
            (board_id,),
        ).fetchone()
        if existing and existing["locked"] and board["status"] != "reopened":
            raise ValueError("Board minutes are locked")
        conn.execute(
            """INSERT INTO assessment_board_minutes
                 (board_id, minutes_text, minutes_hash, updated_by)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(board_id) DO UPDATE SET
                 minutes_text=excluded.minutes_text,
                 minutes_hash=excluded.minutes_hash,
                 updated_by=excluded.updated_by,
                 updated_at=CURRENT_TIMESTAMP""",
            (board_id, minutes_text, digest, actor_id),
        )


def chair_approve(board_id: int, *, chair_id: str) -> None:
    ensure_schema()
    with transaction() as conn:
        board = _board(conn, board_id)
        if board["status"] != "convened":
            raise ValueError("Only a convened board can be chair-approved")
        if board["chair_id"] and board["chair_id"] != chair_id:
            raise ValueError("Only the recorded chair can approve this board")
        undecided = conn.execute(
            "SELECT COUNT(*) FROM assessment_board_agenda "
            "WHERE board_id = ? AND status != 'decided'",
            (board_id,),
        ).fetchone()[0]
        if undecided:
            raise ValueError("Every agenda item requires a decision")
        minutes = conn.execute(
            "SELECT 1 FROM assessment_board_minutes WHERE board_id = ?",
            (board_id,),
        ).fetchone()
        if minutes is None:
            raise ValueError("Board minutes must be recorded")
        conn.execute(
            "UPDATE assessment_board_minutes SET locked = 1 WHERE board_id = ?",
            (board_id,),
        )
        conn.execute(
            """UPDATE assessment_boards SET status = 'chair_approved',
                   chair_id = ?, chair_approved_at = CURRENT_TIMESTAMP
               WHERE board_id = ?""",
            (chair_id, board_id),
        )


def ratify(board_id: int, *, ratified_by: str, award_name: str = "University Award") -> int:
    ensure_schema()
    with transaction() as conn:
        board = _board(conn, board_id)
        if board["status"] != "chair_approved":
            raise ValueError("Chair approval is required before ratification")
        awards = _awards_to_ratify(conn, board_id, award_name)
        held = {a["student_id"]: _blocking(conn, a["student_id"]) for a in awards}
        held = {sid: cases for sid, cases in held.items() if cases}
        if held:
            raise ValueError("Awards cannot be ratified while academic integrity cases are not "
                             "settled: " + "; ".join(f"{sid}: {_case_list(c)}"
                                                     for sid, c in held.items()))
        now = datetime.now().isoformat()
        for award in awards:
            award_id = _store_award(conn, board, award, now, ratified_by)
            from education_system.systems.university.infrastructure.events import (
                transactional_publisher,
            )
            transactional_publisher.publish(
                conn,
                "award.ratified",
                {
                    "award_id": award_id,
                    "board_id": board_id,
                    "student_id": award["student_id"],
                    "programme_code": board["programme_code"] or "UNSPECIFIED",
                    "award_name": award["award_name"],
                    "classification": award["classification"],
                },
                aggregate_id=str(award["student_id"]),
                idempotency_key=f"award:{award_id}:ratified:v{board['version']}",
            )
        progression.ratify_outcomes(conn, board, ratified_by, now)
        _confirm_module_results(conn, board)
        conn.execute(
            """UPDATE assessment_boards SET status = 'ratified',
                   ratified_at = ?, ratified_by = ? WHERE board_id = ?""",
            (now, ratified_by, board_id),
        )
    # After commit: tell sixth-form learners' colleges who progressed.
    # Best-effort — it never raises, and the ratification stands either way.
    from education_system.systems.university.application.students import sixth_form_feedback
    sixth_form_feedback.publish_board_progressions(board_id)
    return len(awards)


def _awards_to_ratify(conn, board_id, award_name) -> list[dict]:
    """The board's effective award decisions, plus exit awards from progression outcomes.

    A decision that a later one supersedes is not ratified; an exit award (or a
    withdrawal with an exit award) carries its own award name.
    """
    rows = conn.execute(
        "SELECT decision_id, student_id, decision_type, classification, supersedes_decision_id "
        "FROM assessment_board_decisions WHERE board_id = ? ORDER BY decision_id",
        (board_id,)).fetchall()
    superseded = {r["supersedes_decision_id"] for r in rows if r["supersedes_decision_id"]}
    exits = progression.exit_awards(conn, board_id)
    awards: dict[str, dict] = {}
    for row in rows:
        if row["decision_id"] in superseded or row["decision_type"] != "award":
            continue
        name, cls = exits.get(row["student_id"], (award_name, row["classification"]))
        awards[row["student_id"]] = {"student_id": row["student_id"], "award_name": name,
                                     "classification": cls or row["classification"]}
    for student_id, (name, cls) in exits.items():
        awards.setdefault(student_id, {"student_id": student_id, "award_name": name,
                                       "classification": cls})
    return list(awards.values())


def _store_award(conn, board, award, now, ratified_by) -> int:
    """Insert the ratified award, or re-ratify the row a reopened board corrected."""
    programme = board["programme_code"] or "UNSPECIFIED"
    existing = conn.execute(
        "SELECT award_id FROM ratified_student_awards WHERE student_id = ? "
        "AND programme_code = ? AND academic_year = ?",
        (award["student_id"], programme, board["academic_year"])).fetchone()
    if existing:
        conn.execute(
            "UPDATE ratified_student_awards SET board_id = ?, award_name = ?, "
            "classification = ?, status = 'ratified', release_authorised = 1, "
            "ratified_at = ?, ratified_by = ? WHERE award_id = ?",
            (board["board_id"], award["award_name"], award["classification"], now,
             ratified_by, existing["award_id"]))
        return int(existing["award_id"])
    cursor = conn.execute(
        """INSERT INTO ratified_student_awards
             (board_id, student_id, programme_code, award_name,
              classification, academic_year, ratified_at, ratified_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (board["board_id"], award["student_id"], programme, award["award_name"],
         award["classification"], board["academic_year"], now, ratified_by),
    )
    return int(cursor.lastrowid)


def _confirm_module_results(conn, board) -> None:
    """Confirm and lock every agenda student's module results.

    Module-level decisions (pass, fail, compensate, condone, reassess) set the
    outcome; modules without one pass or fail on their mark. Passing outcomes
    award the module's credits. First-sit marks are locked against change
    until the board is reopened.
    """
    board_id = board["board_id"]
    decisions: dict[str, dict[str, str]] = {}
    for d in conn.execute(
            "SELECT student_id, module_code, decision_type FROM assessment_board_decisions "
            "WHERE board_id = ? AND module_code IS NOT NULL ORDER BY decision_id", (board_id,)):
        decisions.setdefault(d["student_id"], {})[d["module_code"]] = d["decision_type"]
    for item in conn.execute("SELECT student_id FROM assessment_board_agenda WHERE board_id = ?",
                             (board_id,)).fetchall():
        student_id = item["student_id"]
        modules = [board["module_code"]] if board["module_code"] else [
            r[0] for r in conn.execute(
                "SELECT module_code FROM module_grades WHERE student_id = ? "
                "AND COALESCE(status, 'provisional') IN ('provisional', 'awaiting_resit')",
                (str(student_id),))]
        # A result an integrity case may still change stays unconfirmed and unlocked.
        modules = [m for m in modules if not _blocking(conn, student_id, m)]
        if modules:
            module_results.confirm_results(conn, board_id, student_id, modules,
                                           decisions.get(student_id))


def reopen(
    board_id: int,
    *,
    requested_by: str,
    approved_by: str,
    reason: str,
    decision_id: int | None = None,
) -> int:
    """Controlled reopening; existing decisions remain immutable."""
    ensure_schema()
    if not reason.strip() or requested_by == approved_by:
        raise ValueError("Reopening requires a reason and independent approval")
    with transaction() as conn:
        board = _board(conn, board_id)
        if board["status"] not in {"chair_approved", "ratified"}:
            raise ValueError("Only an approved or ratified board can be reopened")
        cur = conn.execute(
            """INSERT INTO assessment_board_corrections
                 (board_id, decision_id, reason, requested_by, approved_by)
               VALUES (?, ?, ?, ?, ?)""",
            (board_id, decision_id, reason, requested_by, approved_by),
        )
        conn.execute(
            """UPDATE assessment_boards SET status = 'reopened',
                   version = version + 1, reopened_at = CURRENT_TIMESTAMP,
                   reopened_by = ?, reopen_reason = ?
               WHERE board_id = ?""",
            (approved_by, reason, board_id),
        )
        conn.execute(
            "UPDATE assessment_board_minutes SET locked = 0 WHERE board_id = ?",
            (board_id,),
        )
        conn.execute(
            "UPDATE ratified_student_awards SET release_authorised = 0, "
            "status = 'under_correction' WHERE board_id = ?",
            (board_id,),
        )
        # Awards already conferred stop verifying until graduation reviews them.
        from education_system.systems.university.application.graduation import (
            conferral as graduation_conferral,
        )
        graduation_conferral.suspend_for_board(conn, board_id, actor=approved_by)
        # Its progression outcomes go back under correction, unreleased.
        progression.on_reopen(conn, board_id)
        # The marks this board locked become editable again.
        module_results.unlock_board(conn, board_id)
        return int(cur.lastrowid)


def releasable_award(student_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM ratified_student_awards
                WHERE student_id = ? AND status = 'ratified'
                  AND release_authorised = 1
                ORDER BY ratified_at DESC LIMIT 1""",
            (student_id,),
        ).fetchone()
        return dict(row) if row else None


def get_board(board_id: int) -> dict[str, Any]:
    ensure_schema()
    with get_connection() as conn:
        result = dict(_board(conn, board_id))
        result["agenda"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM assessment_board_agenda WHERE board_id = ? ORDER BY agenda_id",
                (board_id,),
            ).fetchall()
        ]
        result["decisions"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM assessment_board_decisions WHERE board_id = ? ORDER BY decision_id",
                (board_id,),
            ).fetchall()
        ]
        result["members"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM assessment_board_members WHERE board_id = ? ORDER BY member_id",
                (board_id,),
            ).fetchall()
        ]
        result["rules"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM assessment_board_rules WHERE board_id = ? ORDER BY rule_id",
                (board_id,),
            ).fetchall()
        ]
        minutes = conn.execute(
            "SELECT * FROM assessment_board_minutes WHERE board_id = ?", (board_id,)
        ).fetchone()
        result["minutes"] = dict(minutes) if minutes else None
        result["awards"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM ratified_student_awards WHERE board_id = ? ORDER BY award_id",
                (board_id,),
            ).fetchall()
        ]
        return result


def list_boards(academic_year: str | None = None) -> list[dict[str, Any]]:
    """Every assessment board, newest first, optionally for one academic year."""
    ensure_schema()
    with get_connection() as conn:
        sql = "SELECT * FROM assessment_boards"
        params: list[Any] = []
        if academic_year:
            sql += " WHERE academic_year = ?"
            params.append(academic_year)
        rows = conn.execute(sql + " ORDER BY board_id DESC", params).fetchall()
        return [dict(r) for r in rows]


__all__ = [
    "create_board",
    "add_member",
    "add_rule",
    "generate_agenda",
    "lock_agenda",
    "record_decision",
    "save_minutes",
    "chair_approve",
    "ratify",
    "reopen",
    "releasable_award",
    "get_board",
    "list_boards",
    "ensure_schema",
]
