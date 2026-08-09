"""Deposit, sponsorship and right-to-study policy decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.university.infrastructure.database.db import transaction
from education_system.systems.university.services.boundary_errors import AdmissionsBoundaryError


@dataclass(frozen=True, slots=True)
class DepositPolicy:
    minimum_amount: float
    currency: str = "GBP"

    def decide(
        self, application_id: int, *, received_amount: float,
        payment_reference: str = "", actor_id: str,
    ) -> str:
        if self.minimum_amount < 0 or received_amount < 0:
            raise AdmissionsBoundaryError("Deposit amounts cannot be negative")
        status = "satisfied" if received_amount >= self.minimum_amount else "outstanding"
        with transaction() as conn:
            conn.execute(
                """INSERT INTO admission_deposit_decisions
                     (application_id, required_amount, currency, received_amount,
                      status, payment_reference, decided_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(application_id) DO UPDATE SET
                     required_amount=excluded.required_amount,
                     currency=excluded.currency,
                     received_amount=excluded.received_amount,
                     status=excluded.status,
                     payment_reference=excluded.payment_reference,
                     decided_by=excluded.decided_by,
                     decided_at=CURRENT_TIMESTAMP""",
                (
                    application_id, self.minimum_amount, self.currency,
                    received_amount, status, payment_reference, actor_id,
                ),
            )
        return status


class SponsorshipPolicy:
    def approve(
        self, application_id: int, *, sponsor_name: str, reference: str,
        actor_id: str, amount: float | None = None, valid_until: str | None = None,
    ) -> str:
        if not sponsor_name.strip() or not reference.strip():
            raise AdmissionsBoundaryError("Sponsor name and evidence reference are required")
        status = "approved"
        if valid_until and date.fromisoformat(valid_until) < date.today():
            status = "expired"
        with transaction() as conn:
            conn.execute(
                """INSERT INTO admission_sponsorship_decisions
                     (application_id, sponsor_name, reference, amount,
                      valid_until, status, decided_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(application_id) DO UPDATE SET
                     sponsor_name=excluded.sponsor_name, reference=excluded.reference,
                     amount=excluded.amount, valid_until=excluded.valid_until,
                     status=excluded.status, decided_by=excluded.decided_by,
                     decided_at=CURRENT_TIMESTAMP""",
                (
                    application_id, sponsor_name, reference, amount,
                    valid_until, status, actor_id,
                ),
            )
        return status


class RightToStudyPolicy:
    ALLOWED_ROUTES = frozenset({"british", "irish", "settled", "student_visa", "other"})

    def approve(
        self, application_id: int, *, route: str, evidence_reference: str,
        actor_id: str, valid_until: str | None = None,
    ) -> str:
        if route not in self.ALLOWED_ROUTES or not evidence_reference.strip():
            raise AdmissionsBoundaryError("A supported route and evidence reference are required")
        status = "approved"
        if valid_until and date.fromisoformat(valid_until) < date.today():
            status = "expired"
        with transaction() as conn:
            conn.execute(
                """INSERT INTO admission_right_to_study_decisions
                     (application_id, route, evidence_reference, valid_until,
                      status, decided_by)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(application_id) DO UPDATE SET
                     route=excluded.route,
                     evidence_reference=excluded.evidence_reference,
                     valid_until=excluded.valid_until, status=excluded.status,
                     decided_by=excluded.decided_by,
                     decided_at=CURRENT_TIMESTAMP""",
                (
                    application_id, route, evidence_reference, valid_until,
                    status, actor_id,
                ),
            )
        return status


__all__ = ["DepositPolicy", "RightToStudyPolicy", "SponsorshipPolicy"]
