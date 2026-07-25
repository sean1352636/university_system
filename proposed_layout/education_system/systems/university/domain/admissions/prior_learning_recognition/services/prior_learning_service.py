"""Accreditation of Prior Learning / Recognition of Prior Learning service.

Formal APL/RPL claims for work experience and prior qualifications that
sit outside the standard school-to-uni credit-transfer flow already
handled by ``clearing_adjustment``.
"""

from datetime import datetime
from typing import Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)


CLAIM_TYPES = (
    "prior_qualification",
    "work_experience",
    "professional_certification",
    "credit_transfer",
    "other",
)

CLAIM_STATUSES = (
    "draft",
    "submitted",
    "under_review",
    "approved",
    "partial",
    "rejected",
    "withdrawn",
)


class PriorLearningService:
    """Manage APL/RPL claims, evidence, and credit awards."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS apl_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claimant_id TEXT NOT NULL,
                    claimant_name TEXT,
                    target_course TEXT,
                    target_qualification TEXT,
                    claim_type TEXT NOT NULL,
                    summary TEXT,
                    credits_requested INTEGER DEFAULT 0,
                    credits_awarded INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    submitted_at TEXT,
                    reviewed_by TEXT,
                    decided_at TEXT,
                    decision_notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS apl_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    evidence_type TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    file_path TEXT,
                    issuing_body TEXT,
                    issue_date TEXT,
                    verified INTEGER DEFAULT 0,
                    verified_by TEXT,
                    verified_at TEXT,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (claim_id) REFERENCES apl_claims(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS apl_credit_awards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    module_code TEXT,
                    module_name TEXT,
                    level INTEGER,
                    credits_awarded INTEGER NOT NULL,
                    grade TEXT,
                    awarded_by TEXT,
                    awarded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (claim_id) REFERENCES apl_claims(id)
                )
            """)
            conn.commit()

    # ---------- Claims ----------

    def create_claim(
        self,
        claimant_id: str,
        claim_type: str,
        target_course: str = None,
        target_qualification: str = None,
        claimant_name: str = None,
        summary: str = None,
        credits_requested: int = 0,
    ) -> int:
        if claim_type not in CLAIM_TYPES:
            raise ValueError(f"Invalid claim_type: {claim_type}")
        with transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO apl_claims
                (claimant_id, claimant_name, target_course, target_qualification,
                 claim_type, summary, credits_requested)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (claimant_id, claimant_name, target_course, target_qualification,
                 claim_type, summary, credits_requested),
            )
            conn.commit()
            return cursor.lastrowid

    def get_claim(self, claim_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM apl_claims WHERE id = ?", (claim_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_claims(
        self, status: str = None, claimant_id: str = None
    ) -> List[Dict]:
        sql = "SELECT * FROM apl_claims WHERE 1=1"
        params: List = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if claimant_id:
            sql += " AND claimant_id = ?"
            params.append(claimant_id)
        sql += " ORDER BY created_at DESC"
        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def submit_claim(self, claim_id: int) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE apl_claims SET status = 'submitted', submitted_at = ? "
                "WHERE id = ? AND status = 'draft'",
                (datetime.now().isoformat(), claim_id),
            )
            conn.commit()
        return self.get_claim(claim_id) is not None

    def review_claim(
        self,
        claim_id: int,
        decision: str,
        reviewed_by: str = None,
        notes: str = None,
    ) -> bool:
        if decision not in ("approved", "partial", "rejected", "under_review"):
            raise ValueError(f"Invalid decision: {decision}")
        with transaction() as conn:
            conn.execute(
                """UPDATE apl_claims SET status = ?, reviewed_by = ?,
                   decided_at = ?, decision_notes = ? WHERE id = ?""",
                (decision, reviewed_by, datetime.now().isoformat(), notes, claim_id),
            )
            conn.commit()
        if decision in ("approved", "partial"):
            claim = self.get_claim(claim_id)
            if claim:
                try:
                    from education_system.systems.university.services.bus.integration_bus import (
                        publish_apl_approved,
                    )
                    publish_apl_approved(
                        claim_id,
                        student_id=claim.get("claimant_id") or "",
                        credits_awarded=int(claim.get("credits_awarded") or 0),
                        claim_type=claim.get("claim_type"),
                        decision=decision,
                        target_course=claim.get("target_course"),
                    )
                except Exception:
                    pass
        return True

    def withdraw_claim(self, claim_id: int) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE apl_claims SET status = 'withdrawn' WHERE id = ?",
                (claim_id,),
            )
            conn.commit()
        return True

    # ---------- Evidence ----------

    def add_evidence(
        self,
        claim_id: int,
        title: str,
        evidence_type: str = None,
        description: str = None,
        file_path: str = None,
        issuing_body: str = None,
        issue_date: str = None,
    ) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO apl_evidence
                (claim_id, evidence_type, title, description, file_path,
                 issuing_body, issue_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (claim_id, evidence_type, title, description, file_path,
                 issuing_body, issue_date),
            )
            conn.commit()
            return cursor.lastrowid

    def list_evidence(self, claim_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM apl_evidence WHERE claim_id = ? ORDER BY added_at",
                (claim_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def verify_evidence(self, evidence_id: int, verified_by: str = None) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE apl_evidence SET verified = 1, verified_by = ?, "
                "verified_at = ? WHERE id = ?",
                (verified_by, datetime.now().isoformat(), evidence_id),
            )
            conn.commit()
        return True

    # ---------- Credit awards ----------

    def award_credits(
        self,
        claim_id: int,
        credits_awarded: int,
        module_code: str = None,
        module_name: str = None,
        level: int = None,
        grade: str = None,
        awarded_by: str = None,
        notes: str = None,
    ) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO apl_credit_awards
                (claim_id, module_code, module_name, level, credits_awarded,
                 grade, awarded_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (claim_id, module_code, module_name, level, credits_awarded,
                 grade, awarded_by, notes),
            )
            total_row = conn.execute(
                "SELECT COALESCE(SUM(credits_awarded), 0) FROM apl_credit_awards "
                "WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()
            total = total_row[0] if total_row else 0
            conn.execute(
                "UPDATE apl_claims SET credits_awarded = ? WHERE id = ?",
                (total, claim_id),
            )
            conn.commit()
            return cursor.lastrowid

    def list_awards(self, claim_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM apl_credit_awards WHERE claim_id = ? "
                "ORDER BY awarded_at",
                (claim_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ---------- Cross-module read helpers ----------

    def credits_for_student(self, student_id: str) -> int:
        """Sum awarded credits from approved/partial claims. Used by
        transcripts and the academic progress calculator so APL credits
        roll up into degree completion."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(credits_awarded), 0) FROM apl_claims "
                "WHERE claimant_id = ? AND status IN ('approved', 'partial')",
                (student_id,),
            ).fetchone()
            return int(row[0] if row else 0)

    def awards_for_student(self, student_id: str) -> List[Dict]:
        """List individual credit-award rows for *student_id* across
        all of their approved/partial claims — the per-row form used by
        the transcript renderer."""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT a.* FROM apl_credit_awards a
                   JOIN apl_claims c ON a.claim_id = c.id
                   WHERE c.claimant_id = ?
                     AND c.status IN ('approved', 'partial')
                   ORDER BY a.awarded_at""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ---------- Cross-module builders ----------

    def create_claim_from_clearing(
        self, application_id: int, *, reviewed_by: str = None
    ) -> Optional[int]:
        """Build a draft APL claim from a clearing application.

        Reads the applicant's name, UCAS id, and stated qualifications
        from ``clearing_applications`` and creates a draft claim of type
        ``prior_qualification`` with one seed evidence row pointing at
        the qualifications text. Returns the new claim id (or ``None``
        if the application was not found)."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM clearing_applications WHERE id = ?",
                (application_id,),
            ).fetchone()
        if not row:
            return None
        app = dict(row)
        claimant = app.get("ucas_id") or f"clearing:{application_id}"
        cid = self.create_claim(
            claimant_id=claimant,
            claim_type="prior_qualification",
            target_course=app.get("preferred_course"),
            claimant_name=app.get("applicant_name"),
            summary=(
                f"Imported from clearing application #{application_id}. "
                f"Tariff points: {app.get('tariff_points', 0)}."
            ),
            credits_requested=0,
        )
        if app.get("qualifications"):
            self.add_evidence(
                cid,
                title="Declared qualifications (clearing)",
                evidence_type="declared",
                description=app.get("qualifications"),
                issuing_body=None,
            )
        return cid

    def create_evidence_from_placement(
        self,
        student_id: str,
        *,
        employer: str,
        total_hours: float,
        signed_off_hours: float,
        date_range: str = None,
        target_course: str = None,
    ) -> int:
        """Find or create a draft work-experience claim for *student_id*
        and attach a placement-summary evidence row to it. Returns the
        claim id so callers can route the user back into the APL GUI
        with the right context."""
        existing = self.list_claims(claimant_id=student_id)
        draft = next(
            (c for c in existing
             if c.get("claim_type") == "work_experience"
             and c.get("status") == "draft"),
            None,
        )
        if draft:
            cid = draft["id"]
        else:
            cid = self.create_claim(
                claimant_id=student_id,
                claim_type="work_experience",
                target_course=target_course,
                summary="Placement-derived work experience.",
            )
        title = f"Placement at {employer}"
        if date_range:
            title += f" ({date_range})"
        desc = (
            f"Total logged: {total_hours:g}h; signed off: {signed_off_hours:g}h."
        )
        self.add_evidence(
            cid,
            title=title,
            evidence_type="work_experience",
            description=desc,
            issuing_body=employer,
        )
        return cid

    def create_draft_from_crm_prospect(
        self,
        prospect_id: int,
        *,
        prospect_name: str,
        intended_major: str = None,
        notes: str = None,
    ) -> int:
        """Create a draft APL claim seeded from a CRM prospect row, so
        admissions advisors can record APL conversations before the
        prospect has a student id. Returns the new claim id."""
        return self.create_claim(
            claimant_id=f"prospect:{prospect_id}",
            claim_type="other",
            target_course=intended_major,
            claimant_name=prospect_name,
            summary=notes or (
                f"Pre-enrolment APL enquiry from CRM prospect #{prospect_id}."
            ),
        )

    # ---------- Statistics ----------

    def get_statistics(self) -> Dict:
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM apl_claims").fetchone()[0]
            by_status: Dict[str, int] = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) FROM apl_claims GROUP BY status"
            ).fetchall():
                by_status[row[0]] = row[1]
            by_type: Dict[str, int] = {}
            for row in conn.execute(
                "SELECT claim_type, COUNT(*) FROM apl_claims GROUP BY claim_type"
            ).fetchall():
                by_type[row[0]] = row[1]
            credits_requested = conn.execute(
                "SELECT COALESCE(SUM(credits_requested), 0) FROM apl_claims"
            ).fetchone()[0]
            credits_awarded = conn.execute(
                "SELECT COALESCE(SUM(credits_awarded), 0) FROM apl_claims "
                "WHERE status IN ('approved', 'partial')"
            ).fetchone()[0]
            approval_rate = 0.0
            decided = sum(
                by_status.get(s, 0) for s in ("approved", "partial", "rejected")
            )
            if decided:
                approval_rate = round(
                    100.0
                    * (by_status.get("approved", 0) + by_status.get("partial", 0))
                    / decided,
                    1,
                )
            return {
                "total_claims": total,
                "by_status": by_status,
                "by_type": by_type,
                "credits_requested": credits_requested,
                "credits_awarded": credits_awarded,
                "approval_rate_pct": approval_rate,
            }
