"""Formal module, progression and award board processing."""

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


def generate_agenda(board_id: int) -> int:
    """Build the cohort agenda from current student/module results."""
    ensure_schema()
    with transaction() as conn:
        board = _board(conn, board_id)
        if board["status"] not in {"draft", "reopened"}:
            raise ValueError("Agenda can only be generated for an editable board")
        filters, params = ["s.status IN ('Active', 'Completed')"], []
        if board["programme_code"]:
            filters.append("s.course = ?")
            params.append(board["programme_code"])
        if board["module_code"]:
            filters.append("sm.module_code = ?")
            params.append(board["module_code"])
        # db-audit: ignore[DBW001] - join over a code-controlled list
        rows = conn.execute(
            f"""SELECT s.student_id, s.course, s.grade_level,
                       COUNT(sm.id) AS module_count,
                       AVG(CASE
                           WHEN CAST(sm.grade AS REAL) BETWEEN 0 AND 100
                           THEN CAST(sm.grade AS REAL)
                           ELSE NULL END) AS average_mark,
                       SUM(COALESCE(m.credits, 0)) AS credits
                  FROM students s
                  LEFT JOIN student_modules sm ON sm.student_id = s.student_id
                  LEFT JOIN modules m ON m.module_code = sm.module_code
                 WHERE {" AND ".join(filters)}
                 GROUP BY s.student_id""",
            params,
        ).fetchall()
        for row in rows:
            conn.execute(
                """INSERT INTO assessment_board_agenda
                     (board_id, student_id, programme_code, current_level,
                      credits, average_mark)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(board_id, student_id) DO UPDATE SET
                     programme_code=excluded.programme_code,
                     current_level=excluded.current_level,
                     credits=excluded.credits,
                     average_mark=excluded.average_mark""",
                (
                    board_id,
                    row["student_id"],
                    row["course"],
                    row["grade_level"],
                    row["credits"],
                    row["average_mark"],
                ),
            )
        return len(rows)


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
        awards = conn.execute(
            """SELECT student_id, classification
                 FROM assessment_board_decisions
                WHERE board_id = ? AND decision_type = 'award'
                  AND supersedes_decision_id IS NULL""",
            (board_id,),
        ).fetchall()
        now = datetime.now().isoformat()
        for award in awards:
            cursor = conn.execute(
                """INSERT INTO ratified_student_awards
                     (board_id, student_id, programme_code, award_name,
                      classification, academic_year, ratified_at, ratified_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    board_id,
                    award["student_id"],
                    board["programme_code"] or "UNSPECIFIED",
                    award_name,
                    award["classification"],
                    board["academic_year"],
                    now,
                    ratified_by,
                ),
            )
            from education_system.systems.university.infrastructure.events import (
                transactional_publisher,
            )
            award_id = int(cursor.lastrowid)
            transactional_publisher.publish(
                conn,
                "award.ratified",
                {
                    "award_id": award_id,
                    "board_id": board_id,
                    "student_id": award["student_id"],
                    "programme_code": board["programme_code"] or "UNSPECIFIED",
                    "award_name": award_name,
                    "classification": award["classification"],
                },
                aggregate_id=str(award["student_id"]),
                idempotency_key=f"award:{award_id}:ratified",
            )
        conn.execute(
            """UPDATE assessment_boards SET status = 'ratified',
                   ratified_at = ?, ratified_by = ? WHERE board_id = ?""",
            (now, ratified_by, board_id),
        )
    return len(awards)


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
