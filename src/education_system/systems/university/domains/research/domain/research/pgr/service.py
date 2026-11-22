"""Postgraduate-research administration, separate from taught assessment."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.database.schema_version import (
    require_tables,
)

PGR_STATES = frozenset(
    {
        "proposal",
        "registered_mphil",
        "registered_phd",
        "thesis_submitted",
        "viva_scheduled",
        "corrections",
        "final_deposit",
        "completed",
        "withdrawn",
    }
)


def ensure_schema() -> None:
    """Validate the Alembic-owned schema without mutating it."""
    require_tables(
        ("pgr_projects", frozenset({"project_id"})),
        ("pgr_supervision_team", frozenset({"allocation_id"})),
        ("pgr_supervision_meetings", frozenset({"meeting_id"})),
        ("pgr_training_needs", frozenset({"need_id"})),
        ("pgr_progress_reviews", frozenset({"review_id"})),
        ("pgr_approvals", frozenset({"approval_id"})),
        ("pgr_upgrades", frozenset({"upgrade_id"})),
        ("pgr_thesis_submissions", frozenset({"submission_id"})),
        ("pgr_examiners", frozenset({"nomination_id"})),
        ("pgr_vivas", frozenset({"viva_id"})),
        ("pgr_corrections", frozenset({"correction_id"})),
        ("pgr_final_deposits", frozenset({"deposit_id"})),
        ("pgr_milestones", frozenset({"milestone_id"})),
        ("pgr_history", frozenset({"history_id"})),
    )


def _project(conn, project_id: int):
    row = conn.execute("SELECT * FROM pgr_projects WHERE project_id = ?", (project_id,)).fetchone()
    if row is None:
        raise ValueError(f"PGR project {project_id} does not exist")
    return row


def _transition(conn, project, target: str, actor_id: str, reason: str, **metadata: Any) -> None:
    if target not in PGR_STATES:
        raise ValueError(f"Unknown PGR state {target!r}")
    conn.execute(
        "UPDATE pgr_projects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE project_id = ?",
        (target, project["project_id"]),
    )
    conn.execute(
        """INSERT INTO pgr_history
             (project_id, action, from_status, to_status, actor_id,
              reason, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            project["project_id"],
            f"status:{target}",
            project["status"],
            target,
            actor_id,
            reason,
            json.dumps(metadata, default=str),
        ),
    )


def create_project(
    student_id: str,
    proposal_title: str,
    abstract: str,
    *,
    created_by: str,
    research_questions: str = "",
    methodology: str = "",
    department: str = "",
    route: str = "MPhil/PhD",
    start_date: str | None = None,
    expected_end_date: str | None = None,
    legacy_thesis_id: int | None = None,
) -> int:
    ensure_schema()
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO pgr_projects
                 (student_id, proposal_title, abstract, research_questions,
                  methodology, department, route, start_date,
                  expected_end_date, current_deadline, legacy_thesis_id,
                  created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                student_id,
                proposal_title,
                abstract,
                research_questions,
                methodology,
                department,
                route,
                start_date,
                expected_end_date,
                expected_end_date,
                legacy_thesis_id,
                created_by,
            ),
        )
        return int(cur.lastrowid)


def add_supervisor(
    project_id: int, supervisor_id: str, role: str, *, workload_fte: float, start_date: str
) -> int:
    ensure_schema()
    if role not in {"primary", "secondary", "advisor"}:
        raise ValueError("Invalid supervision role")
    if not 0 < workload_fte <= 1:
        raise ValueError("workload_fte must be greater than 0 and at most 1")
    with transaction() as conn:
        _project(conn, project_id)
        total = conn.execute(
            "SELECT COALESCE(SUM(workload_fte), 0) FROM pgr_supervision_team "
            "WHERE project_id = ? AND active = 1",
            (project_id,),
        ).fetchone()[0]
        if total + workload_fte > 1.0:
            raise ValueError("Supervision team workload exceeds 1.0 FTE")
        cur = conn.execute(
            """INSERT INTO pgr_supervision_team
                 (project_id, supervisor_id, role, workload_fte, start_date)
               VALUES (?, ?, ?, ?, ?)""",
            (project_id, supervisor_id, role, workload_fte, start_date),
        )
        return int(cur.lastrowid)


def supervisor_workload(supervisor_id: str) -> dict[str, Any]:
    ensure_schema()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT st.*, p.proposal_title, p.student_id
                 FROM pgr_supervision_team st
                 JOIN pgr_projects p ON p.project_id = st.project_id
                WHERE st.supervisor_id = ? AND st.active = 1""",
            (supervisor_id,),
        ).fetchall()
        return {
            "supervisor_id": supervisor_id,
            "total_fte": sum(float(r["workload_fte"]) for r in rows),
            "projects": [dict(r) for r in rows],
        }


def log_supervision(
    project_id: int,
    meeting_at: str,
    attendees: list[str],
    *,
    progress_summary: str,
    actions: list[dict[str, Any]],
    created_by: str,
    next_meeting_date: str | None = None,
) -> int:
    ensure_schema()
    with transaction() as conn:
        _project(conn, project_id)
        cur = conn.execute(
            """INSERT INTO pgr_supervision_meetings
                 (project_id, meeting_at, attendees_json, progress_summary,
                  actions_json, next_meeting_date, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                meeting_at,
                json.dumps(attendees),
                progress_summary,
                json.dumps(actions),
                next_meeting_date,
                created_by,
            ),
        )
        return int(cur.lastrowid)


def add_training_need(
    project_id: int,
    category: str,
    description: str,
    *,
    priority: str = "normal",
    planned_activity: str = "",
    target_date: str | None = None,
) -> int:
    ensure_schema()
    with transaction() as conn:
        _project(conn, project_id)
        cur = conn.execute(
            """INSERT INTO pgr_training_needs
                 (project_id, category, description, priority,
                  planned_activity, target_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, category, description, priority, planned_activity, target_date),
        )
        return int(cur.lastrowid)


def schedule_review(project_id: int, review_year: int, due_date: str) -> int:
    ensure_schema()
    with transaction() as conn:
        _project(conn, project_id)
        cur = conn.execute(
            "INSERT INTO pgr_progress_reviews (project_id, review_year, due_date) VALUES (?, ?, ?)",
            (project_id, review_year, due_date),
        )
        return int(cur.lastrowid)


def decide_review(
    review_id: int,
    outcome: str,
    *,
    panel: list[str],
    approved_by: str,
    student_report: str = "",
    supervisor_report: str = "",
    conditions: str = "",
) -> None:
    ensure_schema()
    if outcome not in {"satisfactory", "conditional", "unsatisfactory"}:
        raise ValueError("Invalid annual-review outcome")
    with transaction() as conn:
        cur = conn.execute(
            """UPDATE pgr_progress_reviews SET status = 'completed',
                   submitted_at = COALESCE(submitted_at, CURRENT_TIMESTAMP),
                   panel_json = ?, student_report = ?, supervisor_report = ?,
                   outcome = ?, conditions = ?, approved_at = CURRENT_TIMESTAMP,
                   approved_by = ? WHERE review_id = ?""",
            (
                json.dumps(panel),
                student_report,
                supervisor_report,
                outcome,
                conditions,
                approved_by,
                review_id,
            ),
        )
        if cur.rowcount != 1:
            raise ValueError(f"Review {review_id} does not exist")


def record_approval(
    project_id: int,
    approval_type: str,
    *,
    reference: str,
    status: str,
    approved_by: str | None = None,
    risk_level: str = "",
    expires_at: str | None = None,
    conditions: str = "",
) -> int:
    """Record ethics, data-governance or sponsor approval."""
    ensure_schema()
    with transaction() as conn:
        _project(conn, project_id)
        cur = conn.execute(
            """INSERT INTO pgr_approvals
                 (project_id, approval_type, reference, risk_level, status,
                  submitted_at, approved_at, expires_at, conditions, approved_by)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                       CASE WHEN ? = 'approved' THEN CURRENT_TIMESTAMP END,
                       ?, ?, ?)""",
            (
                project_id,
                approval_type,
                reference,
                risk_level,
                status,
                status,
                expires_at,
                conditions,
                approved_by,
            ),
        )
        return int(cur.lastrowid)


def submit_upgrade(project_id: int, report_reference: str, panel: list[str]) -> int:
    ensure_schema()
    with transaction() as conn:
        project = _project(conn, project_id)
        if project["status"] != "registered_mphil":
            raise ValueError("Only an MPhil registration can be upgraded")
        cur = conn.execute(
            """INSERT INTO pgr_upgrades
                 (project_id, submitted_at, report_reference, panel_json)
               VALUES (?, ?, ?, ?)""",
            (project_id, datetime.now().isoformat(), report_reference, json.dumps(panel)),
        )
        return int(cur.lastrowid)


def decide_upgrade(upgrade_id: int, outcome: str, *, decided_by: str, conditions: str = "") -> None:
    ensure_schema()
    if outcome not in {"approved", "revisions", "rejected"}:
        raise ValueError("Invalid upgrade outcome")
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM pgr_upgrades WHERE upgrade_id = ?", (upgrade_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Upgrade {upgrade_id} does not exist")
        conn.execute(
            """UPDATE pgr_upgrades SET outcome = ?, conditions = ?,
                   decided_at = CURRENT_TIMESTAMP, decided_by = ?,
                   status = 'decided' WHERE upgrade_id = ?""",
            (outcome, conditions, decided_by, upgrade_id),
        )
        if outcome == "approved":
            project = _project(conn, row["project_id"])
            _transition(
                conn,
                project,
                "registered_phd",
                decided_by,
                "MPhil-to-PhD upgrade approved",
            )


def set_registration(project_id: int, route: str, *, actor_id: str) -> None:
    ensure_schema()
    target = "registered_phd" if route.lower() == "phd" else "registered_mphil"
    with transaction() as conn:
        project = _project(conn, project_id)
        if project["status"] != "proposal":
            raise ValueError("Only a proposal can be registered")
        _transition(conn, project, target, actor_id, "Research registration approved")


def submit_thesis(
    project_id: int, title: str, repository_reference: str, *, declaration_accepted: bool
) -> int:
    ensure_schema()
    if not declaration_accepted:
        raise ValueError("The thesis declaration must be accepted")
    with transaction() as conn:
        project = _project(conn, project_id)
        if project["status"] != "registered_phd":
            raise ValueError("A thesis requires an active PhD registration")
        approvals = conn.execute(
            "SELECT COUNT(*) FROM pgr_approvals WHERE project_id = ? AND status != 'approved'",
            (project_id,),
        ).fetchone()[0]
        if approvals:
            raise ValueError("Required ethics/governance approvals are outstanding")
        version = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM pgr_thesis_submissions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        cur = conn.execute(
            """INSERT INTO pgr_thesis_submissions
                 (project_id, version, thesis_title, repository_reference,
                  submitted_at, declaration_accepted)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (project_id, version, title, repository_reference, datetime.now().isoformat()),
        )
        _transition(
            conn, project, "thesis_submitted", "student", "Thesis submitted", version=version
        )
        return int(cur.lastrowid)


def nominate_examiner(
    project_id: int,
    examiner_id: str,
    examiner_type: str,
    *,
    institution: str,
    expertise: str,
    conflict_declaration: str,
    nominated_by: str,
) -> int:
    ensure_schema()
    if examiner_type not in {"internal", "external"}:
        raise ValueError("Examiner must be internal or external")
    if not conflict_declaration.strip():
        raise ValueError("A conflict declaration is required")
    with transaction() as conn:
        _project(conn, project_id)
        cur = conn.execute(
            """INSERT INTO pgr_examiners
                 (project_id, examiner_id, examiner_type, institution,
                  expertise, conflict_declaration, nominated_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                examiner_id,
                examiner_type,
                institution,
                expertise,
                conflict_declaration,
                nominated_by,
            ),
        )
        return int(cur.lastrowid)


def approve_examiner(nomination_id: int, *, approved_by: str) -> None:
    ensure_schema()
    with transaction() as conn:
        cur = conn.execute(
            """UPDATE pgr_examiners SET status = 'approved',
                   approved_by = ?, approved_at = CURRENT_TIMESTAMP
               WHERE nomination_id = ?""",
            (approved_by, nomination_id),
        )
        if cur.rowcount != 1:
            raise ValueError(f"Examiner nomination {nomination_id} does not exist")


def schedule_viva(project_id: int, scheduled_at: str, *, location: str, chair_id: str) -> int:
    ensure_schema()
    with transaction() as conn:
        project = _project(conn, project_id)
        if project["status"] != "thesis_submitted":
            raise ValueError("The thesis must be submitted before scheduling a viva")
        types = {
            r[0]
            for r in conn.execute(
                "SELECT examiner_type FROM pgr_examiners "
                "WHERE project_id = ? AND status = 'approved'",
                (project_id,),
            ).fetchall()
        }
        if types != {"internal", "external"}:
            raise ValueError("Approved internal and external examiners are required")
        cur = conn.execute(
            """INSERT INTO pgr_vivas
                 (project_id, scheduled_at, location, chair_id)
               VALUES (?, ?, ?, ?)""",
            (project_id, scheduled_at, location, chair_id),
        )
        _transition(conn, project, "viva_scheduled", chair_id, "Viva scheduled")
        return int(cur.lastrowid)


def record_viva_outcome(
    project_id: int,
    outcome: str,
    *,
    decided_by: str,
    notes: str = "",
    corrections_due: str | None = None,
    corrections: str = "",
) -> None:
    ensure_schema()
    valid = {"pass", "minor_corrections", "major_corrections", "resubmit", "fail"}
    if outcome not in valid:
        raise ValueError("Invalid viva outcome")
    with transaction() as conn:
        project = _project(conn, project_id)
        if project["status"] != "viva_scheduled":
            raise ValueError("No scheduled viva is awaiting an outcome")
        conn.execute(
            """UPDATE pgr_vivas SET status = 'completed', outcome = ?,
                   outcome_notes = ?, decided_at = CURRENT_TIMESTAMP
               WHERE project_id = ?""",
            (outcome, notes, project_id),
        )
        if outcome in {"minor_corrections", "major_corrections", "resubmit"}:
            if not corrections_due:
                raise ValueError("A corrections deadline is required")
            conn.execute(
                """INSERT INTO pgr_corrections
                     (project_id, correction_type, description, due_date)
                   VALUES (?, ?, ?, ?)""",
                (project_id, outcome, corrections or notes, corrections_due),
            )
            _transition(
                conn,
                project,
                "corrections",
                decided_by,
                "Viva outcome requires corrections",
                outcome=outcome,
            )
        elif outcome == "pass":
            _transition(conn, project, "final_deposit", decided_by, "Viva passed")
        else:
            _transition(conn, project, "withdrawn", decided_by, f"Viva outcome: {outcome}")


def approve_corrections(correction_id: int, *, approved_by: str) -> None:
    ensure_schema()
    with transaction() as conn:
        correction = conn.execute(
            "SELECT * FROM pgr_corrections WHERE correction_id = ?",
            (correction_id,),
        ).fetchone()
        if correction is None:
            raise ValueError(f"Correction {correction_id} does not exist")
        conn.execute(
            """UPDATE pgr_corrections SET status = 'approved',
                   submitted_at = COALESCE(submitted_at, CURRENT_TIMESTAMP),
                   approved_at = CURRENT_TIMESTAMP, approved_by = ?
               WHERE correction_id = ?""",
            (approved_by, correction_id),
        )
        project = _project(conn, correction["project_id"])
        outstanding = conn.execute(
            "SELECT COUNT(*) FROM pgr_corrections WHERE project_id = ? AND status != 'approved'",
            (project["project_id"],),
        ).fetchone()[0]
        if not outstanding:
            _transition(
                conn, project, "final_deposit", approved_by, "All viva corrections approved"
            )


def final_deposit(
    project_id: int,
    repository_reference: str,
    *,
    licence: str,
    checked_by: str,
    embargo_until: str | None = None,
) -> int:
    ensure_schema()
    with transaction() as conn:
        project = _project(conn, project_id)
        if project["status"] != "final_deposit":
            raise ValueError("Project is not ready for final deposit")
        cur = conn.execute(
            """INSERT INTO pgr_final_deposits
                 (project_id, repository_reference, deposited_at,
                  embargo_until, licence, checked_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                repository_reference,
                datetime.now().isoformat(),
                embargo_until,
                licence,
                checked_by,
            ),
        )
        _transition(conn, project, "completed", checked_by, "Final thesis deposited")
        return int(cur.lastrowid)


def add_milestone(project_id: int, milestone_type: str, title: str, due_date: str) -> int:
    ensure_schema()
    with transaction() as conn:
        _project(conn, project_id)
        cur = conn.execute(
            """INSERT INTO pgr_milestones
                 (project_id, milestone_type, title, due_date)
               VALUES (?, ?, ?, ?)""",
            (project_id, milestone_type, title, due_date),
        )
        return int(cur.lastrowid)


def extend_milestone(
    milestone_id: int, extension_until: str, *, reason: str, approved_by: str
) -> None:
    ensure_schema()
    if not reason.strip():
        raise ValueError("An extension reason is required")
    with transaction() as conn:
        cur = conn.execute(
            """UPDATE pgr_milestones SET extension_until = ?,
                   extension_reason = ?, extension_approved_by = ?,
                   status = 'extended' WHERE milestone_id = ?""",
            (extension_until, reason, approved_by, milestone_id),
        )
        if cur.rowcount != 1:
            raise ValueError(f"Milestone {milestone_id} does not exist")


def escalate_overdue(*, as_of: str | None = None, owner: str = "doctoral-college") -> int:
    """Create one open escalation per overdue review, milestone or correction."""
    ensure_schema()
    checked = date.fromisoformat(as_of) if as_of else date.today()
    sources = (
        ("milestone", "pgr_milestones", "milestone_id", ("pending", "extended")),
        ("review", "pgr_progress_reviews", "review_id", ("due",)),
        ("correction", "pgr_corrections", "correction_id", ("outstanding",)),
    )
    created = 0
    with transaction() as conn:
        for source_type, table, id_column, statuses in sources:
            placeholders = ",".join("?" for _ in statuses)
            # db-audit: ignore[DBW001] - literal collection; string literal
            rows = conn.execute(
                f"""SELECT project_id, {id_column} AS source_id, due_date
                      FROM {table}
                     WHERE status IN ({placeholders}) AND due_date < ?""",  # noqa: S608
                (*statuses, checked.isoformat()),
            ).fetchall()
            for row in rows:
                overdue_days = (checked - date.fromisoformat(row["due_date"])).days
                severity = (
                    "critical" if overdue_days > 90
                    else "high" if overdue_days > 30 else "warning"
                )
                cursor = conn.execute(
                    """INSERT INTO pgr_overdue_escalations
                         (project_id, source_type, source_id, due_date,
                          severity, owner)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(source_type, source_id, status) DO NOTHING""",
                    (
                        row["project_id"], source_type, row["source_id"],
                        row["due_date"], severity, owner,
                    ),
                )
                created += max(cursor.rowcount, 0)
    return created


def project_record(project_id: int) -> dict[str, Any]:
    ensure_schema()
    with get_connection() as conn:
        result = dict(_project(conn, project_id))
        for key, table in (
            ("supervisors", "pgr_supervision_team"),
            ("meetings", "pgr_supervision_meetings"),
            ("training_needs", "pgr_training_needs"),
            ("reviews", "pgr_progress_reviews"),
            ("approvals", "pgr_approvals"),
            ("upgrades", "pgr_upgrades"),
            ("submissions", "pgr_thesis_submissions"),
            ("examiners", "pgr_examiners"),
            ("vivas", "pgr_vivas"),
            ("corrections", "pgr_corrections"),
            ("deposits", "pgr_final_deposits"),
            ("milestones", "pgr_milestones"),
            ("history", "pgr_history"),
        ):
            result[key] = [
                dict(r)
                # db-audit: ignore[DBW001] - loop over a literal table
                for r in conn.execute(
                    f"SELECT * FROM {table} WHERE project_id = ? ORDER BY 1",
                    (project_id,),
                ).fetchall()
            ]
        return result


def list_projects(status: str | None = None) -> list[dict[str, Any]]:
    """Every PGR project, optionally filtered to one lifecycle state."""
    ensure_schema()
    with get_connection() as conn:
        sql = "SELECT * FROM pgr_projects"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        rows = conn.execute(sql + " ORDER BY project_id DESC", params).fetchall()
        return [dict(r) for r in rows]


__all__ = [
    "create_project",
    "add_supervisor",
    "supervisor_workload",
    "log_supervision",
    "add_training_need",
    "schedule_review",
    "decide_review",
    "record_approval",
    "set_registration",
    "submit_upgrade",
    "decide_upgrade",
    "submit_thesis",
    "nominate_examiner",
    "approve_examiner",
    "schedule_viva",
    "record_viva_outcome",
    "approve_corrections",
    "final_deposit",
    "add_milestone",
    "extend_milestone",
    "escalate_overdue",
    "project_record",
    "list_projects",
    "ensure_schema",
]
