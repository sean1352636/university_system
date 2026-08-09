"""Eligibility checks, compliance documents, functional skills, audit trail."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.compliance.eligibility import (
    AuditEntry,
    ComplianceDocument,
    ComplianceStatus,
    EligibilityCheck,
    FunctionalSkill,
    default_documents,
    default_eligibility_checks,
    default_functional_skills,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
)


def _map_check(row: Any) -> EligibilityCheck:
    return EligibilityCheck(
        check_key=row["check_key"],
        passed=to_bool(col(row, "passed")),
        evidence=col(row, "evidence"),
        checked_by=col(row, "checked_by"),
        checked_at=col(row, "checked_at"),
        check_id=col(row, "check_id"),
    )


def _map_document(row: Any) -> ComplianceDocument:
    return ComplianceDocument(
        doc_key=row["doc_key"],
        status=col(row, "status", "Missing"),
        issued_date=col(row, "issued_date"),
        signed_date=col(row, "signed_date"),
        expiry_date=col(row, "expiry_date"),
        file_name=col(row, "file_name"),
        notes=col(row, "notes"),
        updated_at=col(row, "updated_at", ""),
        document_id=col(row, "document_id"),
    )


def _map_skill(row: Any) -> FunctionalSkill:
    return FunctionalSkill(
        subject=row["subject"],
        level=col(row, "level"),
        status=col(row, "status", "Not started"),
        achieved_date=col(row, "achieved_date"),
        exemption_reason=col(row, "exemption_reason"),
        notes=col(row, "notes"),
        updated_at=col(row, "updated_at", ""),
        fs_id=col(row, "fs_id"),
    )


# ── Eligibility ─────────────────────────────────────────────────────

def list_eligibility(apprentice_id: int) -> list[EligibilityCheck]:
    """Every criterion, including the ones nobody has checked yet.

    Merging stored rows onto the full default set is what makes the
    screens honest: an unchecked criterion shows as outstanding rather
    than being invisible because no row exists.
    """
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM eligibility_checks WHERE apprentice_id = ?", (apprentice_id,)
        ).fetchall()
    stored = {r["check_key"]: _map_check(r) for r in rows}
    return [stored.get(check.check_key, check) for check in default_eligibility_checks()]


def set_eligibility(
    apprentice_id: int,
    check_key: str,
    *,
    passed: bool,
    evidence: str | None,
    checked_by: str | None,
    checked_at: str,
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """INSERT INTO eligibility_checks
                   (apprentice_id, check_key, passed, evidence, checked_by, checked_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(apprentice_id, check_key) DO UPDATE SET
                   passed = excluded.passed,
                   evidence = excluded.evidence,
                   checked_by = excluded.checked_by,
                   checked_at = excluded.checked_at""",
            (apprentice_id, check_key, 1 if passed else 0, evidence, checked_by, checked_at),
        )


# ── Documents ───────────────────────────────────────────────────────

def list_documents(apprentice_id: int) -> list[ComplianceDocument]:
    """Every document, including the ones still missing."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM compliance_documents WHERE apprentice_id = ?", (apprentice_id,)
        ).fetchall()
    stored = {r["doc_key"]: _map_document(r) for r in rows}
    return [stored.get(doc.doc_key, doc) for doc in default_documents()]


def set_document(
    apprentice_id: int,
    doc_key: str,
    *,
    status: str,
    issued_date: str | None = None,
    signed_date: str | None = None,
    expiry_date: str | None = None,
    file_name: str | None = None,
    notes: str | None = None,
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """INSERT INTO compliance_documents
                   (apprentice_id, doc_key, status, issued_date, signed_date,
                    expiry_date, file_name, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(apprentice_id, doc_key) DO UPDATE SET
                   status = excluded.status,
                   issued_date = excluded.issued_date,
                   signed_date = excluded.signed_date,
                   expiry_date = excluded.expiry_date,
                   file_name = excluded.file_name,
                   notes = excluded.notes,
                   updated_at = datetime('now')""",
            (apprentice_id, doc_key, status, issued_date, signed_date,
             expiry_date, file_name, notes),
        )


# ── Functional skills ───────────────────────────────────────────────

def list_functional_skills(apprentice_id: int) -> list[FunctionalSkill]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM functional_skills WHERE apprentice_id = ?", (apprentice_id,)
        ).fetchall()
    stored = {r["subject"]: _map_skill(r) for r in rows}
    return [stored.get(skill.subject, skill) for skill in default_functional_skills()]


def get_functional_skill(apprentice_id: int, subject: str) -> FunctionalSkill | None:
    for skill in list_functional_skills(apprentice_id):
        if skill.subject == subject:
            return skill
    return None


def set_functional_skill(
    apprentice_id: int,
    subject: str,
    *,
    status: str,
    level: str | None = None,
    achieved_date: str | None = None,
    exemption_reason: str | None = None,
    notes: str | None = None,
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """INSERT INTO functional_skills
                   (apprentice_id, subject, level, status, achieved_date,
                    exemption_reason, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(apprentice_id, subject) DO UPDATE SET
                   level = excluded.level,
                   status = excluded.status,
                   achieved_date = excluded.achieved_date,
                   exemption_reason = excluded.exemption_reason,
                   notes = excluded.notes,
                   updated_at = datetime('now')""",
            (apprentice_id, subject, level, status, achieved_date, exemption_reason, notes),
        )


def functional_skill_statuses(apprentice_id: int) -> dict[str, str]:
    """``{"English": "Achieved", "Maths": "In progress"}`` for gateway."""
    return {s.subject: s.status for s in list_functional_skills(apprentice_id)}


# ── Combined status ─────────────────────────────────────────────────

def build_status(apprentice_id: int) -> ComplianceStatus:
    return ComplianceStatus(
        apprentice_id=apprentice_id,
        eligibility=list_eligibility(apprentice_id),
        documents=list_documents(apprentice_id),
        functional_skills=list_functional_skills(apprentice_id),
    )


def flagged_apprentices(
    *, tutor_id: int | None = None, employer_id: int | None = None
) -> list[dict[str, Any]]:
    """Apprentices missing a pre-start document or a failed check.

    Deliberately a coarse SQL filter followed by a Python pass: the
    "satisfactory document" rule involves expiry dates and would make
    the query far harder to read for no measurable gain at this scale.
    """
    init_db()
    qb = QueryBuilder()
    qb.add("a.status NOT IN ('Withdrawn', 'Transferred')")
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT a.apprentice_id,
                       (a.given_name || ' ' || a.family_name) AS apprentice_name,
                       a.status, e.name AS employer_name
                  FROM apprentices a
                  LEFT JOIN employers e ON e.employer_id = a.employer_id
                  {qb.where}
                 ORDER BY a.family_name, a.given_name""",
            qb.args,
        ).fetchall()

    flagged = []
    for row in rows:
        status = build_status(row["apprentice_id"])
        if status.rag_rating == "Green":
            continue
        flagged.append({
            **dict(row),
            "rag": status.rag_rating,
            "missing": [d.label for d in status.missing_documents],
            "failed_checks": [c.label for c in status.failed_checks],
        })
    return flagged


# ── Audit trail ─────────────────────────────────────────────────────

def record(
    *,
    action: str,
    entity: str,
    entity_id: str | int | None = None,
    actor: str | None = None,
    actor_role: str | None = None,
    detail: str | None = None,
) -> None:
    """Append to the audit trail.

    Never raises. An audit write failing must not take down the
    operation it was recording — the alternative is a user unable to
    approve a timesheet because the log table is locked.
    """
    try:
        init_db()
        with connect() as conn:
            conn.execute(
                """INSERT INTO audit_log
                       (actor, actor_role, action, entity, entity_id, detail)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (actor, actor_role, action, entity,
                 None if entity_id is None else str(entity_id), detail),
            )
    except Exception:  # pragma: no cover - defensive
        import logging

        logging.getLogger(__name__).debug("Audit write failed", exc_info=True)


def list_audit(
    *,
    entity: str | None = None,
    entity_id: str | int | None = None,
    actor: str | None = None,
    action: str | None = None,
    since: str | None = None,
    limit: int = 200,
) -> list[AuditEntry]:
    init_db()
    qb = QueryBuilder()
    qb.add_if(entity, "entity = ?", entity)
    qb.add_if(entity_id is not None, "entity_id = ?", str(entity_id))
    qb.add_if(actor, "actor = ?", actor)
    qb.add_if(action, "action = ?", action)
    qb.add_if(since, "ts >= ?", since)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM audit_log {qb.where} ORDER BY ts DESC, audit_id DESC LIMIT ?",
            [*qb.args, int(limit)],
        ).fetchall()
    return [
        AuditEntry(
            audit_id=r["audit_id"],
            ts=r["ts"],
            actor=r["actor"],
            actor_role=r["actor_role"],
            action=r["action"],
            entity=r["entity"],
            entity_id=r["entity_id"],
            detail=r["detail"],
        )
        for r in rows
    ]


def retention_due(as_of: str) -> list[dict[str, Any]]:
    """Records past their retention period, for the purge screen."""
    init_db()
    cutoff_year = int(as_of[:4]) - config.RETENTION_YEARS
    cutoff = f"{cutoff_year}{as_of[4:]}"
    with connect() as conn:
        rows = conn.execute(
            """SELECT apprentice_id,
                      (given_name || ' ' || family_name) AS apprentice_name,
                      status, actual_end_date
                 FROM apprentices
                WHERE actual_end_date IS NOT NULL
                  AND actual_end_date <= ?
                ORDER BY actual_end_date""",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]
