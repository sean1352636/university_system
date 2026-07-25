"""Employer portal service for the university system.

Layered on top of the existing `internships`, `internship_applications`,
and `internship_placements` tables managed by
`student_affairs.services.internship_management`. Adds first-class
employer accounts, portal access, periodic placement reviews and
tripartite sign-offs (employer / student / academic supervisor).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class EmployerPortalError(Exception):
    """Raised for any employer-portal data or workflow failure."""


_VALID_SIGNERS = {"employer", "student", "supervisor"}
_VALID_REVIEW_STATUS = {"scheduled", "completed", "cancelled"}


class EmployerPortalService:
    """Manage employer accounts, placement reviews, and sign-offs."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path
        self.init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _conn(self):
        return get_connection(self._db_path)

    def init_schema(self) -> None:
        """Create employer-portal tables if they do not exist."""
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS employer_accounts (
                    employer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL UNIQUE,
                    contact_name TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    address TEXT,
                    sector TEXT,
                    company_size TEXT DEFAULT 'small',
                    portal_access_enabled INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    notes TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS placement_reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    placement_id INTEGER NOT NULL,
                    review_date TEXT NOT NULL,
                    review_type TEXT DEFAULT 'monthly',
                    status TEXT DEFAULT 'scheduled',
                    on_track INTEGER,
                    competency_progress TEXT,
                    hours_logged REAL,
                    employer_feedback TEXT,
                    student_feedback TEXT,
                    supervisor_feedback TEXT,
                    actions TEXT,
                    next_review_date TEXT,
                    employer_signed INTEGER DEFAULT 0,
                    student_signed INTEGER DEFAULT 0,
                    supervisor_signed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (placement_id) REFERENCES internship_placements (placement_id)
                );

                CREATE TABLE IF NOT EXISTS placement_review_signoffs (
                    signoff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id INTEGER NOT NULL,
                    signer_type TEXT NOT NULL,
                    signer_name TEXT NOT NULL,
                    signed_at TEXT DEFAULT (datetime('now')),
                    comments TEXT,
                    FOREIGN KEY (review_id) REFERENCES placement_reviews (review_id)
                );

                CREATE INDEX IF NOT EXISTS idx_placement_reviews_placement
                    ON placement_reviews (placement_id);
                CREATE INDEX IF NOT EXISTS idx_placement_reviews_status
                    ON placement_reviews (status);
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Employer accounts
    # ------------------------------------------------------------------

    def register_employer(
        self,
        company_name: str,
        contact_name: str = "",
        contact_email: str = "",
        contact_phone: str = "",
        sector: str = "",
        company_size: str = "small",
        address: str = "",
    ) -> int:
        if not company_name.strip():
            raise EmployerPortalError("company_name is required")
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """INSERT INTO employer_accounts
                       (company_name, contact_name, contact_email, contact_phone,
                        address, sector, company_size, is_active, portal_access_enabled,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, datetime('now'), datetime('now'))""",
                    (company_name, contact_name, contact_email, contact_phone,
                     address, sector, company_size),
                )
                conn.commit()
                logger.info("Registered employer '%s' (id=%s)", company_name, cur.lastrowid)
                return cur.lastrowid
        except Exception as exc:
            logger.error("register_employer failed: %s", exc)
            raise EmployerPortalError(f"Failed to register employer: {exc}") from exc

    def list_employers(self, active_only: bool = True) -> list[dict]:
        with self._conn() as conn:
            sql = "SELECT * FROM employer_accounts"
            if active_only:
                sql += " WHERE is_active = 1"
            sql += " ORDER BY company_name"
            return [dict(r) for r in conn.execute(sql).fetchall()]

    def update_employer(self, employer_id: int, **updates: Any) -> None:
        allowed = {
            "company_name", "contact_name", "contact_email", "contact_phone",
            "address", "sector", "company_size", "portal_access_enabled",
            "is_active", "notes",
        }
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        try:
            with self._conn() as conn:
                conn.execute(
                    f"UPDATE employer_accounts SET {sets}, updated_at = datetime('now') "
                    "WHERE employer_id = ?",
                    list(fields.values()) + [employer_id],
                )
                conn.commit()
        except Exception as exc:
            raise EmployerPortalError(f"Failed to update employer: {exc}") from exc

    def get_employer_by_company(self, company_name: str) -> Optional[dict]:
        """Resolve an employer account from a free-text company name on an internship."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM employer_accounts WHERE company_name = ? AND is_active = 1",
                (company_name,),
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def schedule_review(
        self, placement_id: int, review_date: str, review_type: str = "monthly",
    ) -> int:
        try:
            datetime.strptime(review_date, "%Y-%m-%d")
        except ValueError as exc:
            raise EmployerPortalError("review_date must be YYYY-MM-DD") from exc
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """INSERT INTO placement_reviews
                       (placement_id, review_date, review_type, status,
                        created_at, updated_at)
                       VALUES (?, ?, ?, 'scheduled', datetime('now'), datetime('now'))""",
                    (placement_id, review_date, review_type),
                )
                conn.commit()
                return cur.lastrowid
        except Exception as exc:
            raise EmployerPortalError(f"Failed to schedule review: {exc}") from exc

    def list_reviews(
        self, placement_id: Optional[int] = None, status: Optional[str] = None,
    ) -> list[dict]:
        sql = "SELECT * FROM placement_reviews WHERE 1=1"
        params: list[Any] = []
        if placement_id is not None:
            sql += " AND placement_id = ?"
            params.append(placement_id)
        if status:
            if status not in _VALID_REVIEW_STATUS:
                raise EmployerPortalError(f"invalid status: {status}")
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY review_date DESC"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def complete_review(
        self,
        review_id: int,
        on_track: bool,
        competency_progress: str,
        hours_logged: float,
        employer_feedback: str,
        student_feedback: Optional[str] = None,
        supervisor_feedback: Optional[str] = None,
        actions: Optional[str] = None,
        next_review_date: Optional[str] = None,
    ) -> None:
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """UPDATE placement_reviews
                       SET on_track = ?, competency_progress = ?, hours_logged = ?,
                           employer_feedback = ?, student_feedback = ?,
                           supervisor_feedback = ?, actions = ?,
                           next_review_date = ?, status = 'completed',
                           updated_at = datetime('now')
                       WHERE review_id = ?""",
                    (1 if on_track else 0, competency_progress, hours_logged,
                     employer_feedback, student_feedback, supervisor_feedback,
                     actions, next_review_date, review_id),
                )
                if cur.rowcount == 0:
                    raise EmployerPortalError(f"review {review_id} not found")
                conn.commit()
        except EmployerPortalError:
            raise
        except Exception as exc:
            raise EmployerPortalError(f"Failed to complete review: {exc}") from exc

    def sign_off_review(
        self, review_id: int, signer_type: str, signer_name: str,
        comments: Optional[str] = None,
    ) -> None:
        if signer_type not in _VALID_SIGNERS:
            raise EmployerPortalError(
                f"signer_type must be one of {sorted(_VALID_SIGNERS)}",
            )
        if not signer_name.strip():
            raise EmployerPortalError("signer_name is required")
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO placement_review_signoffs
                       (review_id, signer_type, signer_name, signed_at, comments)
                       VALUES (?, ?, ?, datetime('now'), ?)""",
                    (review_id, signer_type, signer_name, comments),
                )
                col = f"{signer_type}_signed"
                conn.execute(
                    f"UPDATE placement_reviews SET {col} = 1, "
                    "updated_at = datetime('now') WHERE review_id = ?",
                    (review_id,),
                )
                conn.commit()
        except Exception as exc:
            raise EmployerPortalError(f"Failed to sign off review: {exc}") from exc

    # ------------------------------------------------------------------
    # Dashboards
    # ------------------------------------------------------------------

    def get_employer_dashboard(self, employer_id: int) -> dict:
        """Summary of all placements at an employer (resolved by company_name match)."""
        with self._conn() as conn:
            emp = conn.execute(
                "SELECT * FROM employer_accounts WHERE employer_id = ?",
                (employer_id,),
            ).fetchone()
            if not emp:
                raise EmployerPortalError(f"employer {employer_id} not found")
            emp = dict(emp)

            placements = conn.execute(
                """SELECT p.*, i.title, i.company
                   FROM internship_placements p
                   JOIN internships i ON i.internship_id = p.internship_id
                   WHERE i.company = ?
                   ORDER BY p.start_date DESC""",
                (emp["company_name"],),
            ).fetchall()

            summaries = []
            for p in placements:
                p = dict(p)
                rs = conn.execute(
                    """SELECT COUNT(*) AS total,
                              SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                              SUM(CASE WHEN on_track = 1 THEN 1 ELSE 0 END) AS on_track,
                              COALESCE(SUM(hours_logged), 0) AS total_hours
                       FROM placement_reviews WHERE placement_id = ?""",
                    (p["placement_id"],),
                ).fetchone()
                p["review_summary"] = dict(rs) if rs else {}
                summaries.append(p)

            return {
                "employer": emp,
                "total_placements": len(summaries),
                "active_placements": sum(
                    1 for s in summaries if s.get("status") == "active"
                ),
                "placements": summaries,
            }

    def get_placement_progress(self, placement_id: int) -> dict:
        """Per-placement progress: reviews, hours, completion %."""
        with self._conn() as conn:
            placement = conn.execute(
                """SELECT p.*, i.title, i.company, i.start_date AS i_start, i.end_date AS i_end
                   FROM internship_placements p
                   JOIN internships i ON i.internship_id = p.internship_id
                   WHERE p.placement_id = ?""",
                (placement_id,),
            ).fetchone()
            if not placement:
                raise EmployerPortalError(f"placement {placement_id} not found")
            placement = dict(placement)

            reviews = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM placement_reviews "
                    "WHERE placement_id = ? ORDER BY review_date DESC",
                    (placement_id,),
                ).fetchall()
            ]

            total_hours = sum(r.get("hours_logged") or 0 for r in reviews)
            completion_pct = 0.0
            start = placement.get("start_date") or placement.get("i_start")
            end = placement.get("end_date") or placement.get("i_end")
            if start and end:
                try:
                    s = datetime.strptime(start, "%Y-%m-%d")
                    e = datetime.strptime(end, "%Y-%m-%d")
                    span = (e - s).days
                    if span > 0:
                        elapsed = (datetime.now() - s).days
                        completion_pct = max(0.0, min(round(elapsed * 100.0 / span, 1), 100.0))
                except ValueError:
                    pass

            return {
                "placement": placement,
                "reviews": reviews,
                "review_count": len(reviews),
                "total_hours_logged": total_hours,
                "completion_pct": completion_pct,
            }

    def get_overdue_reviews(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT pr.*, p.student_id, p.internship_id, i.title, i.company
                   FROM placement_reviews pr
                   JOIN internship_placements p ON p.placement_id = pr.placement_id
                   JOIN internships i ON i.internship_id = p.internship_id
                   WHERE pr.status = 'scheduled' AND pr.review_date < ?
                   ORDER BY pr.review_date ASC""",
                (today,),
            ).fetchall()
            return [dict(r) for r in rows]
