"""Bursary management service for the university system.

Implements the full bursary workflow:

    fund -> application -> evidence (+ verification) -> award -> scheduled payments

Tables are created on init (mirrors the EmployerPortalService pattern). All
amounts are stored as REAL; all dates are validated/stored as ISO ``YYYY-MM-DD``
strings.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name=__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class BursaryError(Exception):
    """Raised for any bursary data or workflow failure."""


_VALID_FUND_TYPES = {"hardship", "maintenance", "scholarship", "emergency"}
_VALID_FUND_STATUS = {"open", "closed", "exhausted"}
_VALID_APP_STATUS = {"submitted", "under_review", "approved", "rejected", "awarded"}
_VALID_FREQUENCY = {"one_off", "weekly", "monthly", "termly"}
_VALID_PAYMENT_STATUS = {"scheduled", "paid", "skipped", "failed"}


def _validate_date(value: str, field: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise BursaryError(f"{field} must be YYYY-MM-DD") from exc


def _add_months(d: datetime, months: int) -> datetime:
    """Add ``months`` calendar months to ``d`` (clamping day for short months)."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    # clamp day
    import calendar
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day)


class BursaryService:
    """Manage bursary funds, applications, evidence, awards, and payments."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path
        logger.debug("BursaryService init db_path=%s", db_path or "<default>")
        self.init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _conn(self):
        return get_connection(self._db_path)

    def init_schema(self) -> None:
        """Create bursary tables and indexes if they do not exist."""
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS bursary_funds (
                    fund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    fund_type TEXT NOT NULL DEFAULT 'hardship',
                    total_budget REAL NOT NULL DEFAULT 0,
                    allocated REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS bursary_applications (
                    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    fund_id INTEGER NOT NULL,
                    requested_amount REAL NOT NULL DEFAULT 0,
                    household_income REAL,
                    circumstances TEXT,
                    status TEXT NOT NULL DEFAULT 'submitted',
                    decision_notes TEXT,
                    submitted_at TEXT DEFAULT (datetime('now')),
                    decided_at TEXT,
                    FOREIGN KEY (fund_id) REFERENCES bursary_funds (fund_id)
                );

                CREATE TABLE IF NOT EXISTS bursary_evidence (
                    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    evidence_type TEXT NOT NULL,
                    filename TEXT,
                    description TEXT,
                    verified INTEGER NOT NULL DEFAULT 0,
                    verified_by TEXT,
                    verified_at TEXT,
                    uploaded_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (application_id) REFERENCES bursary_applications (application_id)
                );

                CREATE TABLE IF NOT EXISTS bursary_awards (
                    award_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL UNIQUE,
                    awarded_amount REAL NOT NULL,
                    payment_frequency TEXT NOT NULL,
                    num_payments INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (application_id) REFERENCES bursary_applications (application_id)
                );

                CREATE TABLE IF NOT EXISTS bursary_payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    award_id INTEGER NOT NULL,
                    scheduled_date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    paid_date TEXT,
                    reference TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (award_id) REFERENCES bursary_awards (award_id)
                );

                CREATE INDEX IF NOT EXISTS idx_bursary_apps_student
                    ON bursary_applications (student_id);
                CREATE INDEX IF NOT EXISTS idx_bursary_apps_fund
                    ON bursary_applications (fund_id);
                CREATE INDEX IF NOT EXISTS idx_bursary_apps_status
                    ON bursary_applications (status);
                CREATE INDEX IF NOT EXISTS idx_bursary_evidence_app
                    ON bursary_evidence (application_id);
                CREATE INDEX IF NOT EXISTS idx_bursary_payments_award
                    ON bursary_payments (award_id);
                CREATE INDEX IF NOT EXISTS idx_bursary_payments_status
                    ON bursary_payments (status);
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Funds
    # ------------------------------------------------------------------

    def create_fund(
        self,
        name: str,
        fund_type: str = "hardship",
        total_budget: float = 0.0,
        status: str = "open",
    ) -> int:
        if not name or not name.strip():
            raise BursaryError("fund name is required")
        if fund_type not in _VALID_FUND_TYPES:
            raise BursaryError(
                f"fund_type must be one of {sorted(_VALID_FUND_TYPES)}"
            )
        if status not in _VALID_FUND_STATUS:
            raise BursaryError(
                f"status must be one of {sorted(_VALID_FUND_STATUS)}"
            )
        if total_budget < 0:
            raise BursaryError("total_budget must be >= 0")
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """INSERT INTO bursary_funds
                       (name, fund_type, total_budget, allocated, status,
                        created_at, updated_at)
                       VALUES (?, ?, ?, 0, ?, datetime('now'), datetime('now'))""",
                    (name.strip(), fund_type, float(total_budget), status),
                )
                conn.commit()
                logger.info("Created bursary fund '%s' (id=%s)", name, cur.lastrowid)
                return cur.lastrowid
        except BursaryError:
            raise
        except Exception as exc:
            logger.exception("create_fund failed name=%r type=%r budget=%s", name, fund_type, total_budget)
            raise BursaryError(f"Failed to create fund: {exc}") from exc

    def list_funds(
        self,
        fund_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        sql = "SELECT * FROM bursary_funds WHERE 1=1"
        params: list[Any] = []
        if fund_type:
            if fund_type not in _VALID_FUND_TYPES:
                raise BursaryError(f"invalid fund_type: {fund_type}")
            sql += " AND fund_type = ?"
            params.append(fund_type)
        if status:
            if status not in _VALID_FUND_STATUS:
                raise BursaryError(f"invalid status: {status}")
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY name"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_fund(self, fund_id: int) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM bursary_funds WHERE fund_id = ?", (fund_id,)
            ).fetchone()
            if not row:
                raise BursaryError(f"fund {fund_id} not found")
            return dict(row)

    def update_fund_budget(self, fund_id: int, total_budget: float) -> None:
        if total_budget < 0:
            raise BursaryError("total_budget must be >= 0")
        fund = self.get_fund(fund_id)
        if total_budget < (fund.get("allocated") or 0):
            raise BursaryError(
                "total_budget cannot be less than already allocated "
                f"({fund['allocated']})"
            )
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE bursary_funds SET total_budget = ?, "
                    "updated_at = datetime('now') WHERE fund_id = ?",
                    (float(total_budget), fund_id),
                )
                conn.commit()
                logger.info(
                    "Updated bursary fund id=%s budget=%s (was=%s, allocated=%s)",
                    fund_id, total_budget, fund.get("total_budget"), fund.get("allocated"),
                )
        except Exception as exc:
            logger.exception("update_fund_budget failed id=%s budget=%s", fund_id, total_budget)
            raise BursaryError(f"Failed to update fund budget: {exc}") from exc

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------

    def submit_application(
        self,
        student_id: int,
        fund_id: int,
        requested_amount: float,
        household_income: Optional[float] = None,
        circumstances: str = "",
    ) -> int:
        if requested_amount <= 0:
            raise BursaryError("requested_amount must be > 0")
        # ensure fund exists
        self.get_fund(fund_id)
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """INSERT INTO bursary_applications
                       (student_id, fund_id, requested_amount, household_income,
                        circumstances, status, submitted_at)
                       VALUES (?, ?, ?, ?, ?, 'submitted', datetime('now'))""",
                    (student_id, fund_id, float(requested_amount),
                     household_income, circumstances),
                )
                conn.commit()
                logger.info(
                    "Submitted bursary application id=%s student=%s fund=%s",
                    cur.lastrowid, student_id, fund_id,
                )
                return cur.lastrowid
        except Exception as exc:
            logger.exception(
                "submit_application failed student=%s fund=%s amount=%s",
                student_id, fund_id, requested_amount,
            )
            raise BursaryError(f"Failed to submit application: {exc}") from exc

    def list_applications(
        self,
        status: Optional[str] = None,
        student_id: Optional[int] = None,
        fund_id: Optional[int] = None,
    ) -> list[dict]:
        sql = "SELECT * FROM bursary_applications WHERE 1=1"
        params: list[Any] = []
        if status:
            if status not in _VALID_APP_STATUS:
                raise BursaryError(f"invalid status: {status}")
            sql += " AND status = ?"
            params.append(status)
        if student_id is not None:
            sql += " AND student_id = ?"
            params.append(student_id)
        if fund_id is not None:
            sql += " AND fund_id = ?"
            params.append(fund_id)
        sql += " ORDER BY submitted_at DESC"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_application(self, application_id: int) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM bursary_applications WHERE application_id = ?",
                (application_id,),
            ).fetchone()
            if not row:
                raise BursaryError(f"application {application_id} not found")
            return dict(row)

    def update_application_status(
        self,
        application_id: int,
        status: str,
        decision_notes: Optional[str] = None,
    ) -> None:
        if status not in _VALID_APP_STATUS:
            raise BursaryError(
                f"status must be one of {sorted(_VALID_APP_STATUS)}"
            )
        # ensure exists
        self.get_application(application_id)
        decided_at = (
            "datetime('now')"
            if status in {"approved", "rejected", "awarded"}
            else "decided_at"
        )
        try:
            with self._conn() as conn:
                conn.execute(
                    f"""UPDATE bursary_applications
                        SET status = ?, decision_notes = ?,
                            decided_at = {decided_at}
                        WHERE application_id = ?""",
                    (status, decision_notes, application_id),
                )
                conn.commit()
                logger.info(
                    "Updated bursary application id=%s status=%s notes=%r",
                    application_id, status, decision_notes,
                )
        except Exception as exc:
            logger.exception(
                "update_application_status failed id=%s status=%s",
                application_id, status,
            )
            raise BursaryError(
                f"Failed to update application status: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def add_evidence(
        self,
        application_id: int,
        evidence_type: str,
        filename: str = "",
        description: str = "",
    ) -> int:
        if not evidence_type or not evidence_type.strip():
            raise BursaryError("evidence_type is required")
        # ensure application exists
        self.get_application(application_id)
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """INSERT INTO bursary_evidence
                       (application_id, evidence_type, filename, description,
                        verified, uploaded_at)
                       VALUES (?, ?, ?, ?, 0, datetime('now'))""",
                    (application_id, evidence_type.strip(), filename, description),
                )
                conn.commit()
                logger.info(
                    "Added bursary evidence id=%s app=%s type=%s file=%r",
                    cur.lastrowid, application_id, evidence_type, filename,
                )
                return cur.lastrowid
        except Exception as exc:
            logger.exception(
                "add_evidence failed app=%s type=%s", application_id, evidence_type,
            )
            raise BursaryError(f"Failed to add evidence: {exc}") from exc

    def verify_evidence(self, evidence_id: int, verified_by: str) -> None:
        if not verified_by or not verified_by.strip():
            raise BursaryError("verified_by is required")
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """UPDATE bursary_evidence
                       SET verified = 1, verified_by = ?, verified_at = datetime('now')
                       WHERE evidence_id = ?""",
                    (verified_by.strip(), evidence_id),
                )
                if cur.rowcount == 0:
                    raise BursaryError(f"evidence {evidence_id} not found")
                conn.commit()
                logger.info(
                    "Verified bursary evidence id=%s by=%s", evidence_id, verified_by,
                )
        except BursaryError:
            raise
        except Exception as exc:
            logger.exception("verify_evidence failed id=%s", evidence_id)
            raise BursaryError(f"Failed to verify evidence: {exc}") from exc

    def list_evidence(self, application_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM bursary_evidence WHERE application_id = ? "
                "ORDER BY uploaded_at",
                (application_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Awards + payments
    # ------------------------------------------------------------------

    def _generate_payment_dates(
        self, frequency: str, num_payments: int, start: datetime,
    ) -> list[datetime]:
        if frequency == "one_off":
            return [start]
        dates: list[datetime] = []
        for i in range(num_payments):
            if frequency == "weekly":
                dates.append(start + timedelta(weeks=i))
            elif frequency == "monthly":
                dates.append(_add_months(start, i))
            elif frequency == "termly":
                # 13 weeks per term
                dates.append(start + timedelta(weeks=13 * i))
        return dates

    def award_bursary(
        self,
        application_id: int,
        amount: float,
        frequency: str,
        num_payments: int,
        start_date: str,
    ) -> int:
        if amount <= 0:
            raise BursaryError("amount must be > 0")
        if frequency not in _VALID_FREQUENCY:
            raise BursaryError(
                f"frequency must be one of {sorted(_VALID_FREQUENCY)}"
            )
        if frequency == "one_off":
            num_payments = 1
        if num_payments <= 0:
            raise BursaryError("num_payments must be > 0")
        start_dt = _validate_date(start_date, "start_date")

        app = self.get_application(application_id)
        if app["status"] != "approved":
            raise BursaryError(
                "application must be in 'approved' status before awarding "
                f"(current: {app['status']})"
            )

        fund = self.get_fund(app["fund_id"])
        remaining = (fund["total_budget"] or 0) - (fund["allocated"] or 0)
        if amount > remaining:
            raise BursaryError(
                f"award amount {amount} exceeds remaining fund budget {remaining}"
            )

        # generate payment schedule
        per_payment = round(float(amount) / num_payments, 2)
        dates = self._generate_payment_dates(frequency, num_payments, start_dt)
        # adjust last payment to absorb rounding remainder
        amounts = [per_payment] * num_payments
        diff = round(float(amount) - sum(amounts), 2)
        if amounts:
            amounts[-1] = round(amounts[-1] + diff, 2)
        end_date = dates[-1].strftime("%Y-%m-%d") if dates else start_date

        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """INSERT INTO bursary_awards
                       (application_id, awarded_amount, payment_frequency,
                        num_payments, start_date, end_date, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'active', datetime('now'))""",
                    (application_id, float(amount), frequency, num_payments,
                     start_date, end_date),
                )
                award_id = cur.lastrowid
                created_payment_ids = []
                for d, amt in zip(dates, amounts):
                    inst_cur = conn.execute(
                        """INSERT INTO bursary_payments
                           (award_id, scheduled_date, amount, status, created_at)
                           VALUES (?, ?, ?, 'scheduled', datetime('now'))""",
                        (award_id, d.strftime("%Y-%m-%d"), amt),
                    )
                    created_payment_ids.append((
                        inst_cur.lastrowid, d.strftime("%Y-%m-%d"), amt,
                    ))
                conn.execute(
                    "UPDATE bursary_funds SET allocated = allocated + ?, "
                    "updated_at = datetime('now') WHERE fund_id = ?",
                    (float(amount), app["fund_id"]),
                )
                conn.execute(
                    "UPDATE bursary_applications SET status = 'awarded', "
                    "decided_at = COALESCE(decided_at, datetime('now')) "
                    "WHERE application_id = ?",
                    (application_id,),
                )
                conn.commit()
                logger.info(
                    "Awarded bursary id=%s app=%s amount=%s freq=%s n=%s",
                    award_id, application_id, amount, frequency, num_payments,
                )

            # 8.117.103: mirror each scheduled instalment into the
            # unified ``payments`` table tagged source_type='bursary'.
            # Failure is logged but doesn't roll back the bursary
            # award — the canonical ledger above is bursary_payments.
            try:
                from education_system.post_18.university_system.modules.domain.finance.core.unified_payments import (
                    record_payment,
                )
                student_id = (app.get("student_id") or "").strip()
                for bp_id, scheduled_date, amt in created_payment_ids:
                    if not student_id:
                        continue
                    record_payment(
                        student_id=student_id,
                        amount=float(amt),
                        payment_method='bursary',
                        source_type='bursary',
                        source_payment_id=str(bp_id),
                        payment_type='bursary_disbursement',
                        reference_type='bursary_award',
                        reference_id=str(award_id),
                        department='bursary',
                        description='Bursary disbursement (scheduled)',
                        payment_date=scheduled_date,
                        status='pending',
                    )
            except Exception as exc:
                logger.warning(f"Unified payment mirror failed (bursary): {exc}")

            return award_id
        except BursaryError:
            raise
        except Exception as exc:
            logger.exception(
                "award_bursary failed app=%s amount=%s freq=%s n=%s start=%s",
                application_id, amount, frequency, num_payments, start_date,
            )
            raise BursaryError(f"Failed to award bursary: {exc}") from exc

    def mark_payment_paid(self, payment_id: int, reference: str) -> None:
        if not reference or not reference.strip():
            raise BursaryError("reference is required")
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """UPDATE bursary_payments
                       SET status = 'paid', paid_date = datetime('now'),
                           reference = ?
                       WHERE payment_id = ?""",
                    (reference.strip(), payment_id),
                )
                if cur.rowcount == 0:
                    raise BursaryError(f"payment {payment_id} not found")
                conn.commit()
                logger.info(
                    "Marked bursary payment id=%s paid ref=%s", payment_id, reference,
                )
                # 8.117.103: keep the unified payments mirror in sync.
                try:
                    conn.execute(
                        """UPDATE payments
                           SET status = 'completed',
                               payment_date = datetime('now'),
                               payment_reference = ?,
                               updated_at = datetime('now')
                           WHERE source_type = 'bursary'
                             AND source_payment_id = ?""",
                        (reference.strip(), str(payment_id)),
                    )
                    conn.commit()
                except Exception as exc:
                    logger.warning(
                        f"Unified payments mirror update failed (bursary): {exc}")
        except BursaryError:
            raise
        except Exception as exc:
            logger.exception("mark_payment_paid failed id=%s", payment_id)
            raise BursaryError(f"Failed to mark payment paid: {exc}") from exc

    def get_payment_schedule(self, award_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM bursary_payments WHERE award_id = ? "
                "ORDER BY scheduled_date",
                (award_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def get_application_summary(self, application_id: int) -> dict:
        """Return application + fund + evidence + award + payments."""
        app = self.get_application(application_id)
        fund = self.get_fund(app["fund_id"])
        evidence = self.list_evidence(application_id)
        with self._conn() as conn:
            award_row = conn.execute(
                "SELECT * FROM bursary_awards WHERE application_id = ?",
                (application_id,),
            ).fetchone()
        award = dict(award_row) if award_row else None
        payments = self.get_payment_schedule(award["award_id"]) if award else []
        return {
            "application": app,
            "fund": fund,
            "evidence": evidence,
            "award": award,
            "payments": payments,
        }
