"""Consent decisions used by health application workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable


class HealthConsentRequiredError(PermissionError):
    """Raised when no active consent covers the requested health purpose."""


@dataclass(frozen=True, slots=True)
class HealthConsent:
    subject_id: str
    purposes: frozenset[str]
    granted_at: datetime
    withdrawn_at: datetime | None = None

    @classmethod
    def grant(
        cls,
        *,
        subject_id: str,
        purposes: Iterable[str],
        granted_at: datetime | None = None,
    ) -> "HealthConsent":
        normalized = frozenset(purpose.strip() for purpose in purposes if purpose.strip())
        if not normalized:
            raise ValueError("Consent must cover at least one purpose")
        return cls(
            subject_id=subject_id,
            purposes=normalized,
            granted_at=granted_at or datetime.now(UTC),
        )

    def covers(self, purpose: str, *, at: datetime | None = None) -> bool:
        checked_at = at or datetime.now(UTC)
        return (
            purpose in self.purposes
            and self.granted_at <= checked_at
            and (self.withdrawn_at is None or checked_at < self.withdrawn_at)
        )


class HealthConsentService:
    """Enforce consent independently of CLI and persistence concerns."""

    def require(
        self,
        consent: HealthConsent | None,
        *,
        subject_id: str,
        purpose: str,
        at: datetime | None = None,
    ) -> HealthConsent:
        if (
            consent is None
            or consent.subject_id != subject_id
            or not consent.covers(purpose, at=at)
        ):
            raise HealthConsentRequiredError(
                f"Active consent is required for health purpose {purpose!r}"
            )
        return consent

    @staticmethod
    def require_stored(student_id, purpose: str, *, conn=None) -> None:
        """Raise unless the student's stored consent covers ``purpose``."""
        if not has_consent(student_id, purpose, conn=conn):
            raise HealthConsentRequiredError(
                f"Active consent is required for health purpose {purpose!r}"
            )


__all__ = [
    "HealthConsent",
    "HealthConsentRequiredError",
    "HealthConsentService",
]


# ── stored consent (the student's sharing choices) ───────────────────────
#
# The current decision for each purpose is the student's row in
# ``privacy_consent`` with ``consent_type = 'health:<purpose>'`` (the table
# holds one row per student and type). Every grant and withdrawal, and who
# recorded it, goes to the immutable audit log, which is the history.

PURPOSES = ("share_with_tutor", "share_with_accommodation", "share_with_parent",
            "emergency_contact", "research")
CONSENT_VERSION = "health-2026-1"

#: What each purpose may carry when the viewer is not on the health team.
SHAREABLE: dict[str, frozenset] = {
    "share_with_tutor": frozenset({"student_id", "adjustments", "accommodation_type",
                                   "start_date", "end_date", "status"}),
    "share_with_accommodation": frozenset({"student_id", "adjustments", "accommodation_type",
                                           "condition_name", "severity", "start_date",
                                           "end_date", "status", "evidence_received"}),
    "share_with_parent": frozenset({"student_id", "allergies", "allergen", "severity",
                                    "reaction_description", "blood_type", "medications",
                                    "conditions", "doctor_name", "doctor_phone"}),
    "emergency_contact": frozenset({"student_id", "allergies", "allergen", "severity",
                                    "reaction_description", "blood_type", "medications",
                                    "conditions", "doctor_name", "doctor_phone",
                                    "contact_name", "relationship", "phone_primary"}),
    "research": frozenset({"record_type", "record_date", "condition_name", "severity",
                           "status", "vaccine_name", "administered_date"}),
}


def _check_purpose(purpose: str) -> str:
    purpose = str(purpose or "").strip()
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {', '.join(PURPOSES)}")
    return purpose


def _connect(conn=None):
    if conn is not None:
        return conn, False
    from education_system.systems.university.domains.health.infrastructure.health.storage import (
        get_connection,
    )
    return get_connection(), True


def record_consent(student_id, purpose, granted: bool, by: str, *, expires_at=None,
                   conn=None) -> None:
    """Record the student's choice for ``purpose`` (granted or withdrawn).
    ``by`` is who recorded it (the student, or staff on their written word)."""
    purpose = _check_purpose(purpose)
    if not student_id:
        raise ValueError("A consent needs a student")
    if not str(by or "").strip():
        raise ValueError("Say who recorded the consent")
    db, own = _connect(conn)
    try:
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("INSERT INTO privacy_consent (student_id, consent_type, granted, granted_at, "
                   "expires_at, version) VALUES (?, ?, ?, ?, ?, ?) "
                   "ON CONFLICT(student_id, consent_type) DO UPDATE SET granted = excluded.granted, "
                   "granted_at = excluded.granted_at, expires_at = excluded.expires_at, "
                   "version = excluded.version",
                   (str(student_id), f"health:{purpose}", 1 if granted else 0, now, expires_at,
                    CONSENT_VERSION))
        from education_system.systems.university.infrastructure.security.immutable_audit_log import (
            log_security_event,
        )
        log_security_event(user_id=str(by), action="CONSENT_GRANTED" if granted else
                           "CONSENT_WITHDRAWN", resource_type="health_consent",
                           resource_id=str(student_id), details={"purpose": purpose},
                           conn=db)
        if own:
            db.commit()
    except Exception:
        if own:
            db.rollback()
        raise
    finally:
        if own:
            db.close()


def consent_history(student_id, *, conn=None) -> list[dict]:
    """The student's current health consent decisions, one per purpose
    (the trail of changes is in the immutable audit log)."""
    db, own = _connect(conn)
    try:
        rows = db.execute("SELECT consent_type, granted, granted_at, expires_at, version FROM "
                          "privacy_consent WHERE student_id = ? AND consent_type LIKE 'health:%' "
                          "ORDER BY id", (str(student_id),)).fetchall()
        return [{"purpose": r[0].split(":", 1)[1], "granted": bool(r[1]), "at": r[2],
                 "expires_at": r[3], "version": r[4]} for r in rows]
    finally:
        if own:
            db.close()


def has_consent(student_id, purpose, *, conn=None) -> bool:
    """Is there a current, unexpired grant for ``purpose``? (The latest
    decision wins; no decision means no.)"""
    purpose = _check_purpose(purpose)
    db, own = _connect(conn)
    try:
        row = db.execute("SELECT granted, expires_at FROM privacy_consent WHERE student_id = ? "
                         "AND consent_type = ? ORDER BY id DESC LIMIT 1",
                         (str(student_id), f"health:{purpose}")).fetchone()
    finally:
        if own:
            db.close()
    if not row or not row[0]:
        return False
    expires = row[1]
    return not expires or str(expires) >= datetime.now(UTC).strftime("%Y-%m-%d")


def redact(record, viewer, purpose: str) -> dict:
    """``record`` as ``viewer`` may see it for ``purpose`` (need to know).

    The health team (``access.HealthUser.is_clinician``) sees the whole
    record, revealed. Anyone else needs the student's current consent for
    the purpose and then sees only :data:`SHAREABLE` fields; without consent
    :class:`HealthConsentRequiredError` is raised."""
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    purpose = _check_purpose(purpose)
    data = sealed_fields.unseal_row(record)
    if viewer is not None and getattr(viewer, "is_clinician", False):
        return data
    student_id = data.get("student_id")
    if purpose != "research" and not has_consent(student_id, purpose):
        raise HealthConsentRequiredError(
            f"The student has not consented to sharing this for {purpose.replace('_', ' ')}")
    allowed = SHAREABLE[purpose]
    return {k: v for k, v in data.items() if k in allowed}


__all__ += ["PURPOSES", "SHAREABLE", "record_consent", "has_consent", "consent_history",
            "redact"]
