"""Mitigating Circumstances (MC/EC) service.

Manages pre-result MC/EC claims: submission, evidence, panel review and
decisions, plus downstream deadline extensions and assessment cap flags.

Distinct from the appeals module (which is post-result only).
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction


VALID_STATUSES = ("submitted", "evidence_pending", "under_review", "panel_scheduled",
                  "approved", "rejected", "withdrawn")
VALID_OUTCOMES = ("extension_granted", "deferral_granted", "uncapped_resit",
                  "capped_resit", "no_action", "rejected")
VALID_GROUNDS = ("medical", "bereavement", "personal", "family",
                 "accident", "technical", "other")


class MitigatingCircumstancesService:
    """Service for student MC/EC claim lifecycle."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mc_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    module_code TEXT,
                    assessment_ref TEXT,
                    grounds TEXT,
                    description TEXT,
                    period_start TEXT,
                    period_end TEXT,
                    impact_statement TEXT,
                    requested_remedy TEXT,
                    status TEXT NOT NULL DEFAULT 'submitted',
                    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    submitted_by TEXT,
                    confidential INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mc_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    evidence_type TEXT,
                    description TEXT,
                    document_ref TEXT,
                    received_date TEXT,
                    verified INTEGER DEFAULT 0,
                    verified_by TEXT,
                    verified_at TEXT,
                    notes TEXT,
                    FOREIGN KEY (claim_id) REFERENCES mc_claims(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mc_panels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    panel_date TEXT NOT NULL,
                    chair TEXT,
                    members TEXT,
                    location TEXT,
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mc_panel_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    panel_id INTEGER NOT NULL,
                    claim_id INTEGER NOT NULL,
                    decision TEXT,
                    outcome TEXT,
                    rationale TEXT,
                    decided_at TEXT,
                    FOREIGN KEY (panel_id) REFERENCES mc_panels(id),
                    FOREIGN KEY (claim_id) REFERENCES mc_claims(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mc_deadline_extensions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    module_code TEXT,
                    assessment_ref TEXT,
                    original_deadline TEXT,
                    new_deadline TEXT,
                    extension_days INTEGER,
                    reason TEXT,
                    granted_by TEXT,
                    granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    applied INTEGER DEFAULT 0,
                    FOREIGN KEY (claim_id) REFERENCES mc_claims(id)
                )
            """)
            conn.commit()

    # ------------------------------------------------------------- Claims
    def submit_claim(self, student_id: str = None, module_code: str = None,
                     assessment_ref: str = None, grounds: str = None,
                     description: str = None, period_start: str = None,
                     period_end: str = None, impact_statement: str = None,
                     requested_remedy: str = None, submitted_by: str = None,
                     **kwargs) -> int:
        if isinstance(student_id, dict):
            data = student_id
            student_id = data.get('student_id')
            module_code = data.get('module_code')
            assessment_ref = data.get('assessment_ref')
            grounds = data.get('grounds')
            description = data.get('description')
            period_start = data.get('period_start')
            period_end = data.get('period_end')
            impact_statement = data.get('impact_statement')
            requested_remedy = data.get('requested_remedy')
            submitted_by = data.get('submitted_by')

        if not student_id:
            raise ValueError("student_id is required")
        if grounds and grounds not in VALID_GROUNDS:
            raise ValueError(f"grounds must be one of {VALID_GROUNDS}")

        with transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO mc_claims
                   (student_id, module_code, assessment_ref, grounds, description,
                    period_start, period_end, impact_statement, requested_remedy, submitted_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, module_code, assessment_ref, grounds, description,
                 period_start, period_end, impact_statement, requested_remedy, submitted_by)
            )
            conn.commit()
            return cursor.lastrowid

    def get_claim(self, claim_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM mc_claims WHERE id = ?", (claim_id,)).fetchone()
            return dict(row) if row else None

    def list_claims(self, student_id: str = None, status: str = None) -> List[Dict]:
        with get_connection() as conn:
            if student_id and status:
                rows = conn.execute(
                    "SELECT * FROM mc_claims WHERE student_id = ? AND status = ? ORDER BY submitted_at DESC",
                    (student_id, status)
                ).fetchall()
            elif student_id:
                rows = conn.execute(
                    "SELECT * FROM mc_claims WHERE student_id = ? ORDER BY submitted_at DESC",
                    (student_id,)
                ).fetchall()
            elif status:
                rows = conn.execute(
                    "SELECT * FROM mc_claims WHERE status = ? ORDER BY submitted_at DESC",
                    (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM mc_claims ORDER BY submitted_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def update_claim_status(self, claim_id: int, status: str) -> bool:
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        with transaction() as conn:
            conn.execute("UPDATE mc_claims SET status = ? WHERE id = ?", (status, claim_id))
            conn.commit()
            return True

    def withdraw_claim(self, claim_id: int) -> bool:
        return self.update_claim_status(claim_id, 'withdrawn')

    # ----------------------------------------------------------- Evidence
    def add_evidence(self, claim_id: int = None, evidence_type: str = None,
                     description: str = None, document_ref: str = None,
                     received_date: str = None, **kwargs) -> int:
        if isinstance(claim_id, dict):
            data = claim_id
            claim_id = data.get('claim_id')
            evidence_type = data.get('evidence_type') or data.get('type')
            description = data.get('description')
            document_ref = data.get('document_ref') or data.get('document')
            received_date = data.get('received_date') or data.get('date')

        if not received_date:
            received_date = datetime.now().strftime('%Y-%m-%d')

        with transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO mc_evidence
                   (claim_id, evidence_type, description, document_ref, received_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (claim_id, evidence_type, description, document_ref, received_date)
            )
            # Once evidence arrives, advance the claim out of evidence_pending.
            conn.execute(
                "UPDATE mc_claims SET status = 'under_review' WHERE id = ? AND status IN ('submitted','evidence_pending')",
                (claim_id,)
            )
            conn.commit()
            return cursor.lastrowid

    def list_evidence(self, claim_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM mc_evidence WHERE claim_id = ? ORDER BY received_date DESC",
                (claim_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def verify_evidence(self, evidence_id: int, verified_by: str, verified: bool = True) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE mc_evidence SET verified = ?, verified_by = ?, verified_at = ? WHERE id = ?",
                (1 if verified else 0, verified_by, datetime.now().isoformat(), evidence_id)
            )
            conn.commit()
            return True

    # ------------------------------------------------------------- Panels
    def schedule_panel(self, panel_date: str, chair: str = None,
                       members: str = None, location: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO mc_panels (panel_date, chair, members, location) VALUES (?, ?, ?, ?)",
                (panel_date, chair, members, location)
            )
            conn.commit()
            return cursor.lastrowid

    def assign_claim_to_panel(self, panel_id: int, claim_id: int) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO mc_panel_items (panel_id, claim_id) VALUES (?, ?)",
                (panel_id, claim_id)
            )
            conn.execute(
                "UPDATE mc_claims SET status = 'panel_scheduled' WHERE id = ?",
                (claim_id,)
            )
            conn.commit()
            return cursor.lastrowid

    def list_panels(self, status: str = None) -> List[Dict]:
        with get_connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM mc_panels WHERE status = ? ORDER BY panel_date DESC",
                    (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM mc_panels ORDER BY panel_date DESC").fetchall()
            return [dict(r) for r in rows]

    def get_panel_items(self, panel_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT pi.*, c.student_id, c.module_code, c.assessment_ref, c.grounds
                   FROM mc_panel_items pi
                   JOIN mc_claims c ON pi.claim_id = c.id
                   WHERE pi.panel_id = ?""",
                (panel_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def record_panel_decision(self, panel_id: int, claim_id: int,
                              decision: str, outcome: str,
                              rationale: str = None) -> bool:
        if outcome not in VALID_OUTCOMES:
            raise ValueError(f"outcome must be one of {VALID_OUTCOMES}")
        if decision not in ('approved', 'rejected', 'deferred'):
            raise ValueError("decision must be approved/rejected/deferred")

        with transaction() as conn:
            conn.execute(
                """UPDATE mc_panel_items SET decision = ?, outcome = ?, rationale = ?, decided_at = ?
                   WHERE panel_id = ? AND claim_id = ?""",
                (decision, outcome, rationale, datetime.now().isoformat(), panel_id, claim_id)
            )
            new_status = 'approved' if decision == 'approved' else (
                'rejected' if decision == 'rejected' else 'under_review'
            )
            conn.execute("UPDATE mc_claims SET status = ? WHERE id = ?", (new_status, claim_id))
            conn.commit()
            return True

    def close_panel(self, panel_id: int) -> bool:
        with transaction() as conn:
            conn.execute("UPDATE mc_panels SET status = 'completed' WHERE id = ?", (panel_id,))
            conn.commit()
            return True

    # -------------------------------------------------- Deadline extensions
    def grant_extension(self, claim_id: int, original_deadline: str,
                        extension_days: int = None, new_deadline: str = None,
                        granted_by: str = None, reason: str = None,
                        module_code: str = None, assessment_ref: str = None) -> int:
        """Record an MC-driven deadline extension.

        Provide either extension_days or new_deadline; the other is derived.
        """
        claim = self.get_claim(claim_id)
        if not claim:
            raise ValueError(f"claim {claim_id} not found")

        student_id = claim['student_id']
        module_code = module_code or claim.get('module_code')
        assessment_ref = assessment_ref or claim.get('assessment_ref')

        if not new_deadline and extension_days is not None:
            try:
                base = datetime.strptime(original_deadline, '%Y-%m-%d')
                new_deadline = (base + timedelta(days=int(extension_days))).strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                new_deadline = original_deadline
        elif new_deadline and extension_days is None:
            try:
                base = datetime.strptime(original_deadline, '%Y-%m-%d')
                target = datetime.strptime(new_deadline, '%Y-%m-%d')
                extension_days = (target - base).days
            except (ValueError, TypeError):
                extension_days = 0

        with transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO mc_deadline_extensions
                   (claim_id, student_id, module_code, assessment_ref,
                    original_deadline, new_deadline, extension_days, reason, granted_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (claim_id, student_id, module_code, assessment_ref,
                 original_deadline, new_deadline, extension_days, reason, granted_by)
            )
            conn.commit()
            return cursor.lastrowid

    def list_extensions(self, student_id: str = None,
                        claim_id: int = None) -> List[Dict]:
        with get_connection() as conn:
            if claim_id:
                rows = conn.execute(
                    "SELECT * FROM mc_deadline_extensions WHERE claim_id = ? ORDER BY granted_at DESC",
                    (claim_id,)
                ).fetchall()
            elif student_id:
                rows = conn.execute(
                    "SELECT * FROM mc_deadline_extensions WHERE student_id = ? ORDER BY granted_at DESC",
                    (student_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM mc_deadline_extensions ORDER BY granted_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_active_extension(self, student_id: str, module_code: str,
                             assessment_ref: str) -> Optional[Dict]:
        """Return the most recent extension for a given assessment, if any."""
        with get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM mc_deadline_extensions
                   WHERE student_id = ? AND module_code = ? AND assessment_ref = ?
                   ORDER BY granted_at DESC LIMIT 1""",
                (student_id, module_code, assessment_ref)
            ).fetchone()
            return dict(row) if row else None

    def mark_extension_applied(self, extension_id: int) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE mc_deadline_extensions SET applied = 1 WHERE id = ?",
                (extension_id,)
            )
            conn.commit()
            return True

    # --------------------------------------------------------- Reporting
    def claim_statistics(self) -> Dict:
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM mc_claims").fetchone()[0]
            by_status = {
                row[0]: row[1] for row in conn.execute(
                    "SELECT status, COUNT(*) FROM mc_claims GROUP BY status"
                ).fetchall()
            }
            by_grounds = {
                row[0]: row[1] for row in conn.execute(
                    "SELECT grounds, COUNT(*) FROM mc_claims GROUP BY grounds"
                ).fetchall()
            }
            extensions_granted = conn.execute(
                "SELECT COUNT(*) FROM mc_deadline_extensions"
            ).fetchone()[0]
            return {
                'total_claims': total,
                'by_status': by_status,
                'by_grounds': by_grounds,
                'extensions_granted': extensions_granted,
            }
