"""Collaborative (partner) provision service — partners, agreements, cohorts, reviews.

Data access only, no Tk. The interesting behaviour is in three places:

* :meth:`CollaborativeProvisionService.overdue_reviews` — the register of
  partners nobody has looked at, which is what a QAA audit asks for.
* :meth:`over_recruited` — agreements whose actual headcount exceeds the
  contracted maximum, the most common contractual breach.
* :meth:`provision_map` — one row per programme delivered elsewhere under
  our award, which is the answer to "what do we actually award off-site".
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    sqlite3,
)
from education_system.systems.university.domains.academics.domain.collaborative_provision._db_init import (
    AGREEMENT_STATUSES,
    DELIVERY_MODELS,
    ensure_collaborative_provision_schema,
)

logger = logging.getLogger(__name__)

# Agreement statuses under which a partner may legitimately be teaching.
_LIVE_STATUSES = ("Approved", "Active", "Under Review", "Teach-Out")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


class CollaborativeProvisionService:
    """Read/write access to the partner-provision tables."""

    def __init__(self, db_path=None):
        self.db_path = str(db_path or UNIVERSITY_DEFAULT_DB_PATH)
        ensure_collaborative_provision_schema(self.db_path)

    def _conn(self) -> sqlite3.Connection:
        conn = get_connection(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ------------------------------------------------------------ partners
    def add_partner(self, name: str, partner_type: Optional[str] = None,
                    country: Optional[str] = None, city: Optional[str] = None,
                    ukprn: Optional[str] = None, website: Optional[str] = None,
                    contact_name: Optional[str] = None,
                    contact_email: Optional[str] = None,
                    contact_phone: Optional[str] = None,
                    risk_level: str = "Medium",
                    due_diligence_date: Optional[str] = None,
                    due_diligence_due: Optional[str] = None,
                    notes: Optional[str] = None) -> int:
        if not (name or "").strip():
            raise ValueError("Partner name is required")
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO partner_institutions "
                "(name, partner_type, country, city, ukprn, website, "
                " contact_name, contact_email, contact_phone, risk_level, "
                " due_diligence_date, due_diligence_due, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name.strip(), partner_type, country, city, ukprn, website,
                 contact_name, contact_email, contact_phone, risk_level,
                 due_diligence_date, due_diligence_due, notes))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get_partner(self, partner_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM partner_institutions WHERE partner_id = ?",
                (int(partner_id),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_partners(self, active_only: bool = True,
                      country: Optional[str] = None,
                      search: Optional[str] = None) -> list[dict]:
        sql = ("SELECT p.*, "
               "  (SELECT COUNT(*) FROM partnership_agreements a "
               "    WHERE a.partner_id = p.partner_id) AS agreement_count "
               "FROM partner_institutions p WHERE 1 = 1 ")
        params: list = []
        if active_only:
            sql += "AND p.active = 1 "
        if country and country != "All":
            sql += "AND p.country = ? "
            params.append(country)
        if search:
            like = f"%{search}%"
            sql += "AND (p.name LIKE ? OR p.city LIKE ? OR p.ukprn LIKE ?) "
            params.extend([like, like, like])
        sql += "ORDER BY p.name"
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_partner(self, partner_id: int, **fields: Any) -> bool:
        allowed = {
            "name", "partner_type", "country", "city", "ukprn", "website",
            "contact_name", "contact_email", "contact_phone", "risk_level",
            "due_diligence_date", "due_diligence_due", "notes", "active",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - filtered against a literal allow-list
            conn.execute(
                f"UPDATE partner_institutions SET {sets} WHERE partner_id = ?",  # nosec B608
                (*updates.values(), int(partner_id)))
            conn.commit()
            return True
        finally:
            conn.close()

    def deactivate_partner(self, partner_id: int) -> bool:
        """Partners are never deleted — an ended partnership still has
        students whose award has to be explicable years later."""
        return self.update_partner(partner_id, active=0)

    # ---------------------------------------------------------- agreements
    def add_agreement(self, partner_id: int, delivery_model: str,
                      reference: Optional[str] = None,
                      status: str = "Under Negotiation",
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      review_due: Optional[str] = None,
                      max_students: Optional[int] = None,
                      fee_share_pct: Optional[float] = None,
                      signed_by: Optional[str] = None,
                      signed_date: Optional[str] = None,
                      contract_ref: Optional[str] = None,
                      notes: Optional[str] = None) -> int:
        if delivery_model not in DELIVERY_MODELS:
            raise ValueError(f"Unknown delivery model {delivery_model!r}")
        if status not in AGREEMENT_STATUSES:
            raise ValueError(f"Unknown agreement status {status!r}")
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO partnership_agreements "
                "(partner_id, reference, delivery_model, status, start_date, "
                " end_date, review_due, max_students, fee_share_pct, signed_by, "
                " signed_date, contract_ref, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (int(partner_id), reference, delivery_model, status, start_date,
                 end_date, review_due, max_students, fee_share_pct, signed_by,
                 signed_date, contract_ref, notes))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_agreements(self, partner_id: Optional[int] = None,
                        status: Optional[str] = None,
                        delivery_model: Optional[str] = None) -> list[dict]:
        sql = ("SELECT a.*, p.name AS partner_name, p.country, p.risk_level "
               "FROM partnership_agreements a "
               "JOIN partner_institutions p ON p.partner_id = a.partner_id "
               "WHERE 1 = 1 ")
        params: list = []
        if partner_id:
            sql += "AND a.partner_id = ? "
            params.append(int(partner_id))
        if status and status != "All":
            sql += "AND a.status = ? "
            params.append(status)
        if delivery_model and delivery_model != "All":
            sql += "AND a.delivery_model = ? "
            params.append(delivery_model)
        sql += "ORDER BY p.name, a.start_date DESC"
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_agreement(self, agreement_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT a.*, p.name AS partner_name FROM partnership_agreements a "
                "JOIN partner_institutions p ON p.partner_id = a.partner_id "
                "WHERE a.agreement_id = ?", (int(agreement_id),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def set_agreement_status(self, agreement_id: int, status: str,
                             notes: Optional[str] = None) -> bool:
        if status not in AGREEMENT_STATUSES:
            raise ValueError(f"Unknown agreement status {status!r}")
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE partnership_agreements SET status = ?, "
                "notes = COALESCE(?, notes) WHERE agreement_id = ?",
                (status, notes, int(agreement_id)))
            conn.commit()
            return True
        finally:
            conn.close()

    def update_agreement(self, agreement_id: int, **fields: Any) -> bool:
        allowed = {
            "reference", "delivery_model", "status", "start_date", "end_date",
            "review_due", "max_students", "fee_share_pct", "signed_by",
            "signed_date", "contract_ref", "notes",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - filtered against a literal allow-list
            conn.execute(
                f"UPDATE partnership_agreements SET {sets} WHERE agreement_id = ?",  # nosec B608
                (*updates.values(), int(agreement_id)))
            conn.commit()
            return True
        finally:
            conn.close()

    # ---------------------------------------------------------- programmes
    def add_programme(self, agreement_id: int, programme_title: str,
                      programme_code: Optional[str] = None,
                      award: Optional[str] = None, level: Optional[str] = None,
                      credits: Optional[int] = None,
                      language: str = "English",
                      delivery_site: Optional[str] = None,
                      link_tutor: Optional[str] = None,
                      external_examiner: Optional[str] = None,
                      first_intake: Optional[str] = None,
                      final_intake: Optional[str] = None,
                      status: str = "Active") -> int:
        if not (programme_title or "").strip():
            raise ValueError("Programme title is required")
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO collaborative_programmes "
                "(agreement_id, programme_code, programme_title, award, level, "
                " credits, language, delivery_site, link_tutor, "
                " external_examiner, first_intake, final_intake, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (int(agreement_id), programme_code, programme_title.strip(),
                 award, level, credits, language, delivery_site, link_tutor,
                 external_examiner, first_intake, final_intake, status))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_programmes(self, agreement_id: Optional[int] = None,
                        programme_code: Optional[str] = None) -> list[dict]:
        sql = ("SELECT cp.*, a.delivery_model, a.status AS agreement_status, "
               "       p.name AS partner_name, p.country "
               "FROM collaborative_programmes cp "
               "JOIN partnership_agreements a ON a.agreement_id = cp.agreement_id "
               "JOIN partner_institutions p ON p.partner_id = a.partner_id "
               "WHERE 1 = 1 ")
        params: list = []
        if agreement_id:
            sql += "AND cp.agreement_id = ? "
            params.append(int(agreement_id))
        if programme_code:
            sql += "AND cp.programme_code = ? "
            params.append(programme_code)
        sql += "ORDER BY p.name, cp.programme_title"
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def unlinked_programmes(self) -> list[dict]:
        """Partner programmes whose ``programme_code`` matches no governed
        programme — either a typo or provision running outside governance."""
        conn = self._conn()
        try:
            try:
                rows = conn.execute(
                    "SELECT cp.*, p.name AS partner_name "
                    "FROM collaborative_programmes cp "
                    "JOIN partnership_agreements a "
                    "  ON a.agreement_id = cp.agreement_id "
                    "JOIN partner_institutions p "
                    "  ON p.partner_id = a.partner_id "
                    "WHERE cp.programme_code IS NULL OR cp.programme_code = '' "
                    "   OR NOT EXISTS (SELECT 1 FROM governed_programmes g "
                    "                   WHERE g.programme_code = cp.programme_code) "
                    "ORDER BY p.name").fetchall()
            except sqlite3.OperationalError:
                # No programme governance table here — report only the blanks.
                rows = conn.execute(
                    "SELECT cp.*, p.name AS partner_name "
                    "FROM collaborative_programmes cp "
                    "JOIN partnership_agreements a "
                    "  ON a.agreement_id = cp.agreement_id "
                    "JOIN partner_institutions p "
                    "  ON p.partner_id = a.partner_id "
                    "WHERE cp.programme_code IS NULL OR cp.programme_code = '' "
                    "ORDER BY p.name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------- cohorts
    def add_cohort(self, collab_programme_id: int, academic_year: str,
                   intake_month: Optional[str] = None,
                   planned_headcount: Optional[int] = None,
                   actual_headcount: Optional[int] = None,
                   registered_headcount: Optional[int] = None,
                   completed_headcount: Optional[int] = None,
                   notes: Optional[str] = None) -> int:
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO partner_cohorts "
                "(collab_programme_id, academic_year, intake_month, "
                " planned_headcount, actual_headcount, registered_headcount, "
                " completed_headcount, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (int(collab_programme_id), academic_year, intake_month,
                 planned_headcount, actual_headcount, registered_headcount,
                 completed_headcount, notes))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_cohorts(self, collab_programme_id: Optional[int] = None,
                     academic_year: Optional[str] = None) -> list[dict]:
        sql = ("SELECT c.*, cp.programme_title, p.name AS partner_name "
               "FROM partner_cohorts c "
               "JOIN collaborative_programmes cp "
               "  ON cp.collab_programme_id = c.collab_programme_id "
               "JOIN partnership_agreements a "
               "  ON a.agreement_id = cp.agreement_id "
               "JOIN partner_institutions p ON p.partner_id = a.partner_id "
               "WHERE 1 = 1 ")
        params: list = []
        if collab_programme_id:
            sql += "AND c.collab_programme_id = ? "
            params.append(int(collab_programme_id))
        if academic_year:
            sql += "AND c.academic_year = ? "
            params.append(academic_year)
        sql += "ORDER BY c.academic_year DESC, p.name"
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_cohort(self, cohort_id: int, **fields: Any) -> bool:
        allowed = {
            "academic_year", "intake_month", "planned_headcount",
            "actual_headcount", "registered_headcount", "completed_headcount",
            "notes",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - filtered against a literal allow-list
            conn.execute(
                f"UPDATE partner_cohorts SET {sets} WHERE cohort_id = ?",  # nosec B608
                (*updates.values(), int(cohort_id)))
            conn.commit()
            return True
        finally:
            conn.close()

    # ------------------------------------------------------------- reviews
    def add_review(self, partner_id: int, review_type: str, review_date: str,
                   agreement_id: Optional[int] = None,
                   reviewer: Optional[str] = None,
                   outcome: Optional[str] = None,
                   findings: Optional[str] = None,
                   conditions: Optional[str] = None,
                   next_review_due: Optional[str] = None) -> int:
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO partner_reviews "
                "(partner_id, agreement_id, review_type, review_date, reviewer, "
                " outcome, findings, conditions, next_review_due) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (int(partner_id), agreement_id, review_type,
                 review_date or _today(), reviewer, outcome, findings,
                 conditions, next_review_due))
            # A completed due-diligence review is also the partner's
            # due-diligence date; keeping them in step is why this is here
            # and not left to the caller.
            if review_type == "Initial Due Diligence" and outcome:
                conn.execute(
                    "UPDATE partner_institutions "
                    "SET due_diligence_date = ?, due_diligence_due = "
                    "    COALESCE(?, due_diligence_due) WHERE partner_id = ?",
                    (review_date or _today(), next_review_due, int(partner_id)))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_reviews(self, partner_id: Optional[int] = None) -> list[dict]:
        sql = ("SELECT r.*, p.name AS partner_name FROM partner_reviews r "
               "JOIN partner_institutions p ON p.partner_id = r.partner_id "
               "WHERE 1 = 1 ")
        params: list = []
        if partner_id:
            sql += "AND r.partner_id = ? "
            params.append(int(partner_id))
        sql += "ORDER BY r.review_date DESC"
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    # ---------------------------------------------------------- monitoring
    def overdue_reviews(self, as_of: Optional[str] = None) -> list[dict]:
        """Live agreements whose review date has passed."""
        cutoff = as_of or _today()
        placeholders = ", ".join("?" for _ in _LIVE_STATUSES)
        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - module constant
            rows = conn.execute(
                f"SELECT a.*, p.name AS partner_name, p.country, p.risk_level "
                f"FROM partnership_agreements a "
                f"JOIN partner_institutions p ON p.partner_id = a.partner_id "
                f"WHERE a.status IN ({placeholders}) "  # nosec B608
                f"  AND a.review_due IS NOT NULL AND a.review_due <> '' "
                f"  AND a.review_due < ? "
                f"ORDER BY a.review_due",
                (*_LIVE_STATUSES, cutoff)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def expiring_agreements(self, within_days: int = 180) -> list[dict]:
        from datetime import timedelta
        today = date.today()
        horizon = (today + timedelta(days=int(within_days))).isoformat()
        placeholders = ", ".join("?" for _ in _LIVE_STATUSES)
        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - module constant
            rows = conn.execute(
                f"SELECT a.*, p.name AS partner_name FROM partnership_agreements a "
                f"JOIN partner_institutions p ON p.partner_id = a.partner_id "
                f"WHERE a.status IN ({placeholders}) "  # nosec B608
                f"  AND a.end_date IS NOT NULL AND a.end_date <> '' "
                f"  AND a.end_date >= ? AND a.end_date <= ? "
                f"ORDER BY a.end_date",
                (*_LIVE_STATUSES, today.isoformat(), horizon)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def over_recruited(self) -> list[dict]:
        """Agreements recruiting beyond their contracted student cap.

        Counted across every cohort on every programme under the agreement,
        because the cap is written per agreement, not per programme.
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT a.agreement_id, a.reference, a.max_students, "
                "       a.delivery_model, p.name AS partner_name, "
                "       SUM(COALESCE(c.actual_headcount, "
                "                    c.registered_headcount, 0)) AS enrolled "
                "FROM partnership_agreements a "
                "JOIN partner_institutions p ON p.partner_id = a.partner_id "
                "JOIN collaborative_programmes cp "
                "  ON cp.agreement_id = a.agreement_id "
                "JOIN partner_cohorts c "
                "  ON c.collab_programme_id = cp.collab_programme_id "
                "WHERE a.max_students IS NOT NULL AND a.max_students > 0 "
                "GROUP BY a.agreement_id "
                "HAVING enrolled > a.max_students "
                "ORDER BY (enrolled - a.max_students) DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def provision_map(self) -> list[dict]:
        """One row per programme delivered under our award off-site."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT p.name AS partner_name, p.country, p.risk_level, "
                "       a.delivery_model, a.status AS agreement_status, "
                "       a.end_date, cp.programme_code, cp.programme_title, "
                "       cp.award, cp.link_tutor, cp.delivery_site, "
                "       COALESCE(SUM(c.actual_headcount), 0) AS students "
                "FROM partner_institutions p "
                "JOIN partnership_agreements a ON a.partner_id = p.partner_id "
                "JOIN collaborative_programmes cp "
                "  ON cp.agreement_id = a.agreement_id "
                "LEFT JOIN partner_cohorts c "
                "  ON c.collab_programme_id = cp.collab_programme_id "
                "GROUP BY cp.collab_programme_id "
                "ORDER BY p.country, p.name, cp.programme_title").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def summary(self) -> dict:
        conn = self._conn()
        try:
            def one(sql: str, params: tuple = ()) -> int:
                return int(conn.execute(sql, params).fetchone()[0] or 0)

            placeholders = ", ".join("?" for _ in _LIVE_STATUSES)
            return {
                "partners": one("SELECT COUNT(*) FROM partner_institutions "
                                "WHERE active = 1"),
                "agreements_live": one(
                    f"SELECT COUNT(*) FROM partnership_agreements "  # nosec B608
                    f"WHERE status IN ({placeholders})", _LIVE_STATUSES),
                "programmes": one("SELECT COUNT(*) FROM collaborative_programmes "
                                  "WHERE status = 'Active'"),
                "students": one("SELECT COALESCE(SUM(actual_headcount), 0) "
                                "FROM partner_cohorts"),
                "high_risk": one("SELECT COUNT(*) FROM partner_institutions "
                                 "WHERE active = 1 AND risk_level = 'High'"),
                "overdue_reviews": len(self.overdue_reviews()),
            }
        finally:
            conn.close()


__all__ = ["CollaborativeProvisionService"]
