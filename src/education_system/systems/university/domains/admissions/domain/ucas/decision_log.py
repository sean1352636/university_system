"""Who decided what, and when, on every UCAS choice naming this university.

A decision used to leave three traces, none of which was a record. The
sixth form's ``ucas_choices`` row held the *current* status with no author
— it is the school's table, and the school is not who decided. The link
row had a ``linked_by`` column that nothing ever filled in. And the
university logged a line at INFO, which is a debug aid, not evidence.

So "who made this offer?" had no answer, and "was this rejection changed
after the fact?" had no answer either.

This module is the answer to both. Every call to ``record_decision``
appends a row here — it is a history, not a current-state table, so a
conditional offer later confirmed on results day leaves both steps
standing rather than one overwriting the other. Alongside it, each
decision is written to the platform audit log, which is the tamper-evident
store the rest of the platform already reports against; this table is the
domain's own detailed copy, carrying the offer terms the audit log has no
column for.

Recording is best-effort at the call site — see ``record_decision`` — for
the same reason the link is: the decision itself is already committed on
the sixth form's side, and losing its provenance must not appear to the
officer as the decision having failed. A failure here is logged loudly
rather than silently, because an unattributable decision is exactly the
thing this exists to prevent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
)

logger = logging.getLogger(__name__)

__all__ = [
    "Decision",
    "history_for_choice",
    "last_decision",
    "latest_for_choices",
    "list_decisions",
    "record",
]

#: The system key this university's audit entries are filed under.
_AUDIT_SYSTEM = "university"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_decisions (
    decision_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sf_choice_id      INTEGER NOT NULL,
    sf_application_id INTEGER,
    sf_student_id     TEXT,
    decision_status   TEXT NOT NULL,
    offer_terms       TEXT,
    notes             TEXT,
    decided_by        TEXT,
    decided_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ucas_decisions_choice
    ON ucas_decisions(sf_choice_id, decided_at);
CREATE INDEX IF NOT EXISTS idx_ucas_decisions_student
    ON ucas_decisions(sf_student_id);
CREATE INDEX IF NOT EXISTS idx_ucas_decisions_when
    ON ucas_decisions(decided_at);
"""


@dataclass
class Decision:
    decision_id: int
    sf_choice_id: int
    sf_application_id: int | None
    sf_student_id: str | None
    decision_status: str
    offer_terms: str | None
    notes: str | None
    decided_by: str | None
    decided_at: str


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    logger.debug("UCAS decision-log schema ready")
    _DB_READY = True


def _row(r) -> Decision:
    return Decision(
        decision_id=r["decision_id"],
        sf_choice_id=r["sf_choice_id"],
        sf_application_id=r["sf_application_id"],
        sf_student_id=r["sf_student_id"],
        decision_status=r["decision_status"],
        offer_terms=r["offer_terms"],
        notes=r["notes"],
        decided_by=r["decided_by"],
        decided_at=r["decided_at"],
    )


# ── Write ──────────────────────────────────────────────────────────

def record(
    *,
    sf_choice_id: int,
    decision_status: str,
    sf_application_id: int | None = None,
    sf_student_id: str | None = None,
    offer_terms: str | None = None,
    notes: str | None = None,
    decided_by: str | None = None,
) -> Decision:
    """Append one decision to the history and mirror it to the audit log.

    The audit write is deliberately *not* swallowed here. It goes through
    ``AuditLogger``, which raises if it cannot record — and a decision the
    platform's tamper-evident log never saw is precisely what the caller
    needs to hear about.
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO ucas_decisions
                   (sf_choice_id, sf_application_id, sf_student_id,
                    decision_status, offer_terms, notes, decided_by,
                    decided_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (sf_choice_id, sf_application_id, sf_student_id,
             decision_status, offer_terms, notes,
             (decided_by or "").strip() or None),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()

    out = _get(new_id)
    assert out is not None
    _audit(out)
    logger.info(
        "UCAS decision #%d logged: choice #%d -> %s by %s",
        new_id, sf_choice_id, decision_status, out.decided_by or "unknown")
    return out


def _audit(decision: Decision) -> None:
    """Mirror a decision into the platform audit log.

    An admissions decision is a change to a person's record made by a
    member of staff, which is the definition of what that log is for. It
    is filed as an update against the UCAS choice, with the applicant on
    the row so a subject-access request can find it.
    """
    from education_system.platform.governance.audit import (
        AuditAction,
        AuditLogger,
    )
    AuditLogger(_AUDIT_SYSTEM).log(
        AuditAction.UPDATE,
        username=decision.decided_by,
        target_type="ucas_choice",
        target_id=str(decision.sf_choice_id),
        details={
            "decision_status": decision.decision_status,
            "offer_terms": decision.offer_terms,
            "sf_application_id": decision.sf_application_id,
            "sf_student_id": decision.sf_student_id,
            "decided_by": decision.decided_by,
        },
        # A rejection is as consequential as an offer, and an unattributed
        # decision is the one worth noticing in a filtered log.
        severity="warning" if not decision.decided_by else "info",
    )


# ── Read ───────────────────────────────────────────────────────────

def _get(decision_id: int) -> Decision | None:
    conn = get_connection()
    try:
        r = conn.execute(
            "SELECT * FROM ucas_decisions WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        return _row(r) if r else None
    finally:
        conn.close()


def history_for_choice(sf_choice_id: int) -> list[Decision]:
    """Every decision ever recorded against a choice, oldest first."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM ucas_decisions WHERE sf_choice_id = ?
               ORDER BY decided_at, decision_id""",
            (sf_choice_id,),
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        conn.close()


def last_decision(sf_choice_id: int) -> Decision | None:
    """The most recent decision on a choice — who currently owns it."""
    history = history_for_choice(sf_choice_id)
    return history[-1] if history else None


def latest_for_choices(sf_choice_ids) -> dict[int, Decision]:
    """``{sf_choice_id: latest Decision}`` for many choices, one query.

    What the admissions screens overlay on the sixth form's copy of each
    choice, so a decision shows here the moment it is recorded rather than
    once the sixth form has applied the published event.
    """
    ids = sorted({int(i) for i in sf_choice_ids if i is not None})
    if not ids:
        return {}
    init_db()
    out: dict[int, Decision] = {}
    conn = get_connection()
    try:
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            # db-audit: ignore[DBW001] - placeholder join only
            rows = conn.execute(
                f"""SELECT * FROM ucas_decisions
                     WHERE sf_choice_id IN ({marks})
                     ORDER BY decided_at, decision_id""",  # nosec B608
                chunk,
            ).fetchall()
            for r in rows:
                out[r["sf_choice_id"]] = _row(r)
    finally:
        conn.close()
    return out


def list_decisions(
    *,
    decided_by: str | None = None,
    since: str | None = None,
    decision_status: str | None = None,
    limit: int = 500,
) -> list[Decision]:
    """Recent decisions, newest first — the "what went out today" view."""
    init_db()
    clauses: list[str] = []
    args: list = []
    if decided_by:
        clauses.append("decided_by = ?")
        args.append(decided_by)
    if since:
        clauses.append("decided_at >= ?")
        args.append(since)
    if decision_status:
        clauses.append("decision_status = ?")
        args.append(decision_status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(int(limit))
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""SELECT * FROM ucas_decisions {where}
                ORDER BY decided_at DESC, decision_id DESC
                LIMIT ?""",  # nosec B608
            args,
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        conn.close()
