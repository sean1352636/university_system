"""Immutable programme versions, approvals, regulations and teach-out."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.database.schema_version import (
    require_tables,
)


def ensure_schema() -> None:
    """Validate the Alembic-owned schema without mutating it."""
    require_tables(
        ("governed_programmes", frozenset({"programme_id"})),
        ("programme_proposals", frozenset({"proposal_id"})),
        ("programme_business_cases", frozenset({"business_case_id"})),
        ("programme_versions", frozenset({"version_id"})),
        ("programme_amendments", frozenset({"amendment_id"})),
        ("approval_committees", frozenset({"committee_id"})),
        ("programme_validations", frozenset({"validation_id"})),
        ("programme_accreditations", frozenset({"accreditation_id"})),
        ("programme_teach_out_plans", frozenset({"plan_id"})),
        ("student_regulation_assignments", frozenset({"assignment_id"})),
        ("programme_governance_history", frozenset({"history_id"})),
    )


def _programme(conn, programme_id: int):
    row = conn.execute(
        "SELECT * FROM governed_programmes WHERE programme_id = ?",
        (programme_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Programme {programme_id} does not exist")
    return row


def _version(conn, version_id: int):
    row = conn.execute(
        "SELECT * FROM programme_versions WHERE version_id = ?", (version_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Programme version {version_id} does not exist")
    return row


def _history(
    conn,
    programme_id: int,
    action: str,
    actor_id: str,
    *,
    version_id: int | None = None,
    reason: str = "",
) -> None:
    conn.execute(
        """INSERT INTO programme_governance_history
             (programme_id, version_id, action, actor_id, reason)
           VALUES (?, ?, ?, ?, ?)""",
        (programme_id, version_id, action, actor_id, reason),
    )


def create_proposal(
    programme_code: str,
    programme_name: str,
    award_type: str,
    proposed_start_year: str,
    *,
    created_by: str,
    rationale: str,
    market_need: str = "",
    strategic_alignment: str = "",
    owning_school: str = "",
) -> tuple[int, int]:
    ensure_schema()
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO governed_programmes
                 (programme_code, programme_name, owning_school, award_type,
                  created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (programme_code, programme_name, owning_school, award_type, created_by),
        )
        programme_id = int(cur.lastrowid)
        cur = conn.execute(
            """INSERT INTO programme_proposals
                 (programme_id, rationale, market_need, strategic_alignment,
                  proposed_start_year)
               VALUES (?, ?, ?, ?, ?)""",
            (programme_id, rationale, market_need, strategic_alignment, proposed_start_year),
        )
        _history(conn, programme_id, "proposal_created", created_by)
        return programme_id, int(cur.lastrowid)


def record_business_case(
    proposal_id: int,
    *,
    forecast_students: dict,
    income: dict,
    costs: dict,
    staffing_plan: str,
    facilities_plan: str,
    risk_register: str,
) -> int:
    ensure_schema()
    with transaction() as conn:
        proposal = conn.execute(
            "SELECT * FROM programme_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} does not exist")
        cur = conn.execute(
            """INSERT INTO programme_business_cases
                 (proposal_id, forecast_students_json, income_json, costs_json,
                  staffing_plan, facilities_plan, risk_register)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                proposal_id,
                json.dumps(forecast_students),
                json.dumps(income),
                json.dumps(costs),
                staffing_plan,
                facilities_plan,
                risk_register,
            ),
        )
        return int(cur.lastrowid)


def approve_business_case(business_case_id: int, *, approved_by: str) -> None:
    ensure_schema()
    with transaction() as conn:
        row = conn.execute(
            """SELECT bc.*, p.programme_id FROM programme_business_cases bc
                 JOIN programme_proposals p ON p.proposal_id = bc.proposal_id
                WHERE bc.business_case_id = ?""",
            (business_case_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Business case does not exist")
        conn.execute(
            """UPDATE programme_business_cases SET approved = 1,
                   approved_by = ?, approved_at = CURRENT_TIMESTAMP
               WHERE business_case_id = ?""",
            (approved_by, business_case_id),
        )
        conn.execute(
            "UPDATE programme_proposals SET status = 'business_case_approved' "
            "WHERE proposal_id = ?",
            (row["proposal_id"],),
        )
        _history(conn, row["programme_id"], "business_case_approved", approved_by)


def create_version(
    programme_id: int,
    effective_academic_year: str,
    *,
    curriculum: dict[str, Any],
    regulations: dict[str, Any],
    created_by: str,
    supersedes_version_id: int | None = None,
) -> int:
    ensure_schema()
    with transaction() as conn:
        _programme(conn, programme_id)
        if supersedes_version_id:
            old = _version(conn, supersedes_version_id)
            if old["programme_id"] != programme_id:
                raise ValueError("Superseded version belongs to another programme")
        number = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 "
            "FROM programme_versions WHERE programme_id = ?",
            (programme_id,),
        ).fetchone()[0]
        cur = conn.execute(
            """INSERT INTO programme_versions
                 (programme_id, version_number, effective_academic_year,
                  curriculum_json, regulations_json, supersedes_version_id,
                  created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                programme_id,
                number,
                effective_academic_year,
                json.dumps(curriculum, sort_keys=True),
                json.dumps(regulations, sort_keys=True),
                supersedes_version_id,
                created_by,
            ),
        )
        version_id = int(cur.lastrowid)
        _history(conn, programme_id, "version_created", created_by, version_id=version_id)
        return version_id


def amend_draft(
    version_id: int,
    *,
    curriculum: dict[str, Any] | None = None,
    regulations: dict[str, Any] | None = None,
    actor_id: str,
) -> None:
    """Edit a draft; approved snapshots are immutable."""
    ensure_schema()
    with transaction() as conn:
        version = _version(conn, version_id)
        if version["status"] != "draft":
            raise ValueError("Approved programme versions are immutable")
        conn.execute(
            """UPDATE programme_versions
                  SET curriculum_json = COALESCE(?, curriculum_json),
                      regulations_json = COALESCE(?, regulations_json)
                WHERE version_id = ?""",
            (
                json.dumps(curriculum, sort_keys=True) if curriculum is not None else None,
                json.dumps(regulations, sort_keys=True) if regulations is not None else None,
                version_id,
            ),
        )
        _history(conn, version["programme_id"], "draft_amended", actor_id, version_id=version_id)


def propose_amendment(
    source_version_id: int,
    amendment_type: str,
    summary: str,
    impact_assessment: str,
    *,
    requested_by: str,
    effective_academic_year: str,
) -> tuple[int, int]:
    """Create an amendment and a new draft copied from the approved source."""
    ensure_schema()
    with get_connection() as conn:
        source = _version(conn, source_version_id)
    target = create_version(
        source["programme_id"],
        effective_academic_year,
        curriculum=json.loads(source["curriculum_json"]),
        regulations=json.loads(source["regulations_json"]),
        created_by=requested_by,
        supersedes_version_id=source_version_id,
    )
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO programme_amendments
                 (source_version_id, target_version_id, amendment_type,
                  summary, impact_assessment, requested_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source_version_id, target, amendment_type, summary, impact_assessment, requested_by),
        )
        return int(cur.lastrowid), target


def create_committee(name: str, committee_type: str, quorum: int) -> int:
    ensure_schema()
    if quorum < 1:
        raise ValueError("Committee quorum must be positive")
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO approval_committees(name, committee_type, quorum) VALUES (?, ?, ?)",
            (name, committee_type, quorum),
        )
        return int(cur.lastrowid)


def validate_version(
    version_id: int,
    committee_id: int,
    meeting_at: str,
    members: list[str],
    *,
    external_advisers: list[str],
    outcome: str,
    conditions: list[str],
    minutes_reference: str,
    chair_id: str,
) -> int:
    ensure_schema()
    if outcome not in {"approved", "conditional", "rejected"}:
        raise ValueError("Invalid validation outcome")
    with transaction() as conn:
        version = _version(conn, version_id)
        if version["status"] != "draft":
            raise ValueError("Only draft versions can be validated")
        business_case = conn.execute(
            """SELECT 1 FROM programme_business_cases bc
                 JOIN programme_proposals pp ON pp.proposal_id = bc.proposal_id
                WHERE pp.programme_id = ? AND bc.approved = 1""",
            (version["programme_id"],),
        ).fetchone()
        if business_case is None:
            raise ValueError("An approved business case is required")
        committee = conn.execute(
            "SELECT * FROM approval_committees WHERE committee_id = ?",
            (committee_id,),
        ).fetchone()
        if committee is None or len(set(members)) < committee["quorum"]:
            raise ValueError("Committee quorum was not met")
        cur = conn.execute(
            """INSERT INTO programme_validations
                 (version_id, committee_id, meeting_at, members_json,
                  external_advisers_json, conditions_json, outcome,
                  minutes_reference, chair_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id,
                committee_id,
                meeting_at,
                json.dumps(members),
                json.dumps(external_advisers),
                json.dumps(conditions),
                outcome,
                minutes_reference,
                chair_id,
            ),
        )
        conn.execute(
            "UPDATE programme_versions SET status = ?, validation_outcome = ? WHERE version_id = ?",
            ("validated" if outcome == "approved" else outcome, outcome, version_id),
        )
        _history(
            conn, version["programme_id"], f"validation_{outcome}", chair_id, version_id=version_id
        )
        return int(cur.lastrowid)


def approve_version(version_id: int, *, approved_by: str) -> None:
    ensure_schema()
    with transaction() as conn:
        version = _version(conn, version_id)
        if version["status"] != "validated":
            raise ValueError("Academic validation is required before approval")
        snapshot = version["curriculum_json"] + "\n" + version["regulations_json"]
        digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
        conn.execute(
            """UPDATE programme_versions SET status = 'approved',
                   snapshot_hash = ?, approved_at = CURRENT_TIMESTAMP,
                   approved_by = ? WHERE version_id = ?""",
            (digest, approved_by, version_id),
        )
        conn.execute(
            "UPDATE governed_programmes SET status = 'active' WHERE programme_id = ?",
            (version["programme_id"],),
        )
        _history(
            conn, version["programme_id"], "version_approved", approved_by, version_id=version_id
        )


def record_accreditation(
    programme_id: int,
    body_name: str,
    status: str,
    *,
    version_id: int | None = None,
    accreditation_reference: str = "",
    valid_from: str | None = None,
    valid_until: str | None = None,
    conditions: str = "",
    evidence_reference: str = "",
) -> int:
    ensure_schema()
    with transaction() as conn:
        _programme(conn, programme_id)
        cur = conn.execute(
            """INSERT INTO programme_accreditations
                 (programme_id, version_id, body_name,
                  accreditation_reference, status, valid_from, valid_until,
                  conditions, evidence_reference)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                programme_id,
                version_id,
                body_name,
                accreditation_reference,
                status,
                valid_from,
                valid_until,
                conditions,
                evidence_reference,
            ),
        )
        return int(cur.lastrowid)


def create_teach_out(
    programme_id: int,
    *,
    version_id: int | None,
    last_intake_year: str,
    final_delivery_year: str,
    student_communication: str,
    staffing_commitment: str,
    module_availability: dict[str, Any],
    approved_by: str,
) -> int:
    ensure_schema()
    with transaction() as conn:
        _programme(conn, programme_id)
        cur = conn.execute(
            """INSERT INTO programme_teach_out_plans
                 (programme_id, version_id, last_intake_year,
                  final_delivery_year, student_communication,
                  staffing_commitment, module_availability_json, approved_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                programme_id,
                version_id,
                last_intake_year,
                final_delivery_year,
                student_communication,
                staffing_commitment,
                json.dumps(module_availability),
                approved_by,
            ),
        )
        conn.execute(
            "UPDATE governed_programmes SET status = 'teach_out' WHERE programme_id = ?",
            (programme_id,),
        )
        return int(cur.lastrowid)


def set_programme_status(programme_id: int, status: str, *, actor_id: str, reason: str) -> None:
    ensure_schema()
    if status not in {"active", "suspended", "teach_out", "closed"}:
        raise ValueError("Invalid programme status")
    with transaction() as conn:
        programme = _programme(conn, programme_id)
        if status == "closed":
            plan = conn.execute(
                "SELECT 1 FROM programme_teach_out_plans WHERE programme_id = ?", (programme_id,)
            ).fetchone()
            if plan is None:
                raise ValueError("A teach-out plan is required before closure")
        conn.execute(
            "UPDATE governed_programmes SET status = ? WHERE programme_id = ?",
            (status, programme_id),
        )
        _history(conn, programme_id, f"programme_{status}", actor_id, reason=reason)


def assign_student(
    student_id: str, programme_id: int, version_id: int, *, assigned_by: str, reason: str
) -> int:
    ensure_schema()
    with transaction() as conn:
        version = _version(conn, version_id)
        if version["programme_id"] != programme_id:
            raise ValueError("Version belongs to another programme")
        if version["status"] != "approved":
            raise ValueError("Students can only be assigned approved regulations")
        conn.execute(
            "UPDATE student_regulation_assignments SET active = 0 "
            "WHERE student_id = ? AND programme_id = ? AND active = 1",
            (student_id, programme_id),
        )
        cur = conn.execute(
            """INSERT INTO student_regulation_assignments
                 (student_id, programme_id, version_id, assigned_by, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (student_id, programme_id, version_id, assigned_by, reason),
        )
        return int(cur.lastrowid)


def regulation_for_student(
    student_id: str, programme_id: int | None = None
) -> dict[str, Any] | None:
    """Return the immutable regulation snapshot used by historical audits."""
    ensure_schema()
    with get_connection() as conn:
        sql = (
            "SELECT a.*, v.version_number, v.effective_academic_year, "
            "v.curriculum_json, v.regulations_json, v.snapshot_hash, "
            "p.programme_code, p.programme_name "
            "FROM student_regulation_assignments a "
            "JOIN programme_versions v ON v.version_id = a.version_id "
            "JOIN governed_programmes p ON p.programme_id = a.programme_id "
            "WHERE a.student_id = ? AND a.active = 1"
        )
        params: list[Any] = [student_id]
        if programme_id is not None:
            sql += " AND a.programme_id = ?"
            params.append(programme_id)
        row = conn.execute(sql + " ORDER BY a.assignment_id DESC LIMIT 1", params).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["curriculum"] = json.loads(result.pop("curriculum_json"))
        result["regulations"] = json.loads(result.pop("regulations_json"))
        return result


def effective_version(programme_id: int, academic_year: str) -> dict[str, Any] | None:
    ensure_schema()
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM programme_versions
                WHERE programme_id = ? AND status = 'approved'
                  AND effective_academic_year <= ?
                  AND (end_academic_year IS NULL OR end_academic_year >= ?)
                ORDER BY effective_academic_year DESC LIMIT 1""",
            (programme_id, academic_year, academic_year),
        ).fetchone()
        return dict(row) if row else None


def bind_registration(
    registration_id: int, student_id: str, programme_code: str,
    academic_year: str, *, assigned_by: str,
) -> int:
    """Bind a registration to the immutable regulations effective on entry."""
    ensure_schema()
    with transaction() as conn:
        programme = conn.execute(
            "SELECT programme_id FROM governed_programmes WHERE programme_code=?",
            (programme_code,),
        ).fetchone()
        if programme is None:
            raise ValueError(f"Programme {programme_code!r} is not governed")
        version = conn.execute(
            """SELECT version_id FROM programme_versions
                WHERE programme_id=? AND status='approved'
                  AND effective_academic_year<=?
                  AND (end_academic_year IS NULL OR end_academic_year>=?)
                ORDER BY effective_academic_year DESC LIMIT 1""",
            (programme["programme_id"], academic_year, academic_year),
        ).fetchone()
        if version is None:
            raise ValueError("No approved regulation version is effective for registration")
        conn.execute(
            "UPDATE student_regulation_assignments SET active=0 "
            "WHERE student_id=? AND programme_id=? AND active=1",
            (student_id, programme["programme_id"]),
        )
        assignment = conn.execute(
            """INSERT INTO student_regulation_assignments
                 (student_id, programme_id, version_id, assigned_by, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (
                student_id, programme["programme_id"], version["version_id"],
                assigned_by, f"Registration {registration_id}",
            ),
        )
        conn.execute(
            "UPDATE student_registrations SET regulation_version_id=? "
            "WHERE registration_id=?",
            (version["version_id"], registration_id),
        )
        return int(assignment.lastrowid)


def record_historical_degree_audit(
    student_id: str, completed_modules: dict[str, float]
) -> dict[str, Any]:
    """Calculate and persist an audit solely from the assigned snapshot."""
    ensure_schema()
    regulation = regulation_for_student(student_id)
    if regulation is None:
        raise ValueError("Student has no immutable regulation assignment")
    curriculum = regulation["curriculum"]
    required = {
        module["code"]: float(module.get("credits", 0))
        for module in curriculum.get("modules", [])
        if module.get("core")
    }
    passed = {
        code for code, mark in completed_modules.items() if float(mark) >= 40
    }
    missing = sorted(set(required) - passed)
    result = {
        "eligible": not missing,
        "missing_core_modules": missing,
        "credits_completed": sum(
            credits for code, credits in required.items() if code in passed
        ),
        "regulation_version_id": regulation["version_id"],
    }
    with transaction() as conn:
        conn.execute(
            """INSERT INTO historical_degree_audits
                 (student_id, assignment_id, regulation_version_id,
                  input_json, result_json, snapshot_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                student_id, regulation["assignment_id"], regulation["version_id"],
                json.dumps(completed_modules, sort_keys=True),
                json.dumps(result, sort_keys=True), regulation["snapshot_hash"],
            ),
        )
    return result


def list_programmes() -> list[dict[str, Any]]:
    """Every governed programme with its latest version number and status."""
    ensure_schema()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT p.*,
                      (SELECT MAX(version_number) FROM programme_versions v
                        WHERE v.programme_id = p.programme_id) AS latest_version
                 FROM governed_programmes p
                ORDER BY p.programme_code"""
        ).fetchall()
        return [dict(r) for r in rows]


def list_committees() -> list[dict[str, Any]]:
    ensure_schema()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM approval_committees ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def programme_record(programme_id: int) -> dict[str, Any]:
    """The programme plus every governance artefact attached to it."""
    ensure_schema()
    with get_connection() as conn:
        result = dict(_programme(conn, programme_id))
        result["proposals"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM programme_proposals WHERE programme_id = ? ORDER BY proposal_id",
                (programme_id,),
            ).fetchall()
        ]
        result["business_cases"] = [
            dict(r)
            for r in conn.execute(
                """SELECT bc.* FROM programme_business_cases bc
                     JOIN programme_proposals pp ON pp.proposal_id = bc.proposal_id
                    WHERE pp.programme_id = ? ORDER BY bc.business_case_id""",
                (programme_id,),
            ).fetchall()
        ]
        result["versions"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM programme_versions WHERE programme_id = ? ORDER BY version_number",
                (programme_id,),
            ).fetchall()
        ]
        result["amendments"] = [
            dict(r)
            for r in conn.execute(
                """SELECT a.* FROM programme_amendments a
                     JOIN programme_versions v ON v.version_id = a.source_version_id
                    WHERE v.programme_id = ? ORDER BY a.amendment_id""",
                (programme_id,),
            ).fetchall()
        ]
        result["validations"] = [
            dict(r)
            for r in conn.execute(
                """SELECT pv.* FROM programme_validations pv
                     JOIN programme_versions v ON v.version_id = pv.version_id
                    WHERE v.programme_id = ? ORDER BY pv.validation_id""",
                (programme_id,),
            ).fetchall()
        ]
        result["accreditations"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM programme_accreditations WHERE programme_id = ? "
                "ORDER BY accreditation_id",
                (programme_id,),
            ).fetchall()
        ]
        result["teach_out_plans"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM programme_teach_out_plans WHERE programme_id = ? ORDER BY plan_id",
                (programme_id,),
            ).fetchall()
        ]
        result["history"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM programme_governance_history WHERE programme_id = ? "
                "ORDER BY history_id",
                (programme_id,),
            ).fetchall()
        ]
        return result


__all__ = [
    "create_proposal",
    "record_business_case",
    "approve_business_case",
    "create_version",
    "amend_draft",
    "propose_amendment",
    "create_committee",
    "validate_version",
    "approve_version",
    "record_accreditation",
    "create_teach_out",
    "set_programme_status",
    "assign_student",
    "regulation_for_student",
    "effective_version",
    "bind_registration",
    "record_historical_degree_audit",
    "list_programmes",
    "list_committees",
    "programme_record",
    "ensure_schema",
]
