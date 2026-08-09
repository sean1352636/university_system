"""Explicit lifecycle rules for university records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Any


class Disposition(StrEnum):
    DELETE = "delete"
    REDACT = "redact"
    ARCHIVE = "archive"


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    record_type: str
    period: timedelta
    disposition: Disposition
    legal_basis: str
    redacted_fields: frozenset[str] = frozenset()


UNIVERSITY_POLICIES = {
    "applicant": RetentionPolicy(
        "applicant", timedelta(days=365 * 2), Disposition.REDACT,
        "Admissions administration and limitation period",
        frozenset({"name", "email", "phone", "address"}),
    ),
    "student_record": RetentionPolicy(
        "student_record", timedelta(days=365 * 7), Disposition.REDACT,
        "Education administration and statutory reporting",
        frozenset({"personal_email", "phone", "address", "emergency_contact"}),
    ),
    "finance": RetentionPolicy(
        "finance", timedelta(days=365 * 7), Disposition.ARCHIVE,
        "Tax, accounting and audit obligations",
    ),
    "health": RetentionPolicy(
        "health", timedelta(days=365 * 8), Disposition.DELETE,
        "Provision of health and wellbeing services",
    ),
    "safeguarding": RetentionPolicy(
        "safeguarding", timedelta(days=365 * 25), Disposition.REDACT,
        "Safeguarding and protection from harm",
        frozenset({"reporter_name", "reporter_contact", "free_text"}),
    ),
}


class LegalHoldActive(RuntimeError):
    pass


class LifecycleService:
    """Apply policy only after checking immutable legal-hold state."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def dispose(self, record_type: str, record_id: str, *, actor_id: str) -> str:
        policy = UNIVERSITY_POLICIES[record_type]
        if self.repository.has_active_hold(record_type, record_id):
            raise LegalHoldActive(f"{record_type}/{record_id} is under legal hold")
        if policy.disposition is Disposition.REDACT:
            self.repository.redact(
                record_type, record_id, fields=policy.redacted_fields, actor_id=actor_id
            )
        elif policy.disposition is Disposition.DELETE:
            self.repository.delete(record_type, record_id, actor_id=actor_id)
        else:
            self.repository.archive(record_type, record_id, actor_id=actor_id)
        self.repository.record_disposition(
            record_type, record_id, action=policy.disposition.value, actor_id=actor_id
        )
        return policy.disposition.value


__all__ = [
    "Disposition", "LegalHoldActive", "LifecycleService", "RetentionPolicy",
    "UNIVERSITY_POLICIES",
]
