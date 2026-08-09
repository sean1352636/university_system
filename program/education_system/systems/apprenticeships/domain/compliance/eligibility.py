"""Compliance: eligibility, documents, functional skills and the audit trail.

Funding is conditional on paperwork. An apprentice who is ineligible, or
whose training plan was never signed, generates a clawback at audit even
if the training itself was excellent. These records are the evidence
pack: what was checked, by whom, and when.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

CHECK_LABELS: dict[str, str] = dict(config.ELIGIBILITY_CHECKS)
CHECK_KEYS: tuple[str, ...] = tuple(k for k, _ in config.ELIGIBILITY_CHECKS)

DOCUMENT_LABELS: dict[str, str] = dict(config.COMPLIANCE_DOCUMENTS)
DOCUMENT_KEYS: tuple[str, ...] = tuple(k for k, _ in config.COMPLIANCE_DOCUMENTS)

# Documents that must be signed before training starts, not merely
# drafted. These are the ones an auditor asks for first.
PRE_START_DOCUMENTS: frozenset[str] = frozenset({
    "training_plan", "commitment_statement", "training_agreement",
})


@dataclass
class EligibilityCheck:
    """One eligibility criterion for one apprentice."""

    check_key: str
    passed: bool = False
    evidence: str | None = None
    checked_by: str | None = None
    checked_at: str | None = None
    check_id: int | None = None

    @property
    def label(self) -> str:
        return CHECK_LABELS.get(self.check_key, self.check_key)


@dataclass
class ComplianceDocument:
    """One document on an apprentice's file."""

    doc_key: str
    status: str = "Missing"
    issued_date: str | None = None
    signed_date: str | None = None
    expiry_date: str | None = None
    file_name: str | None = None
    notes: str | None = None
    updated_at: str = ""
    document_id: int | None = None

    @property
    def label(self) -> str:
        return DOCUMENT_LABELS.get(self.doc_key, self.doc_key)

    @property
    def is_signed(self) -> bool:
        return self.status == "Signed"

    @property
    def is_expired(self) -> bool:
        if self.status == "Expired":
            return True
        return bool(self.expiry_date) and self.expiry_date < date.today().isoformat()

    @property
    def is_satisfactory(self) -> bool:
        return self.is_signed and not self.is_expired


@dataclass
class FunctionalSkill:
    """An apprentice's position in English or Maths.

    Level 2 English and Maths are a gateway requirement unless the
    apprentice is exempt through prior attainment. Missing functional
    skills are the most common single reason an otherwise-ready
    apprentice cannot go to gateway.
    """

    subject: str
    level: str | None = None
    status: str = "Not started"
    achieved_date: str | None = None
    exemption_reason: str | None = None
    notes: str | None = None
    updated_at: str = ""
    fs_id: int | None = None

    @property
    def is_satisfied(self) -> bool:
        """Achieved or exempt — either passes the gateway check."""
        return self.status in ("Achieved", "Exempt")


@dataclass
class ComplianceStatus:
    """An apprentice's whole compliance position."""

    apprentice_id: int
    eligibility: list[EligibilityCheck] = field(default_factory=list)
    documents: list[ComplianceDocument] = field(default_factory=list)
    functional_skills: list[FunctionalSkill] = field(default_factory=list)

    @property
    def eligibility_passed(self) -> int:
        return sum(1 for c in self.eligibility if c.passed)

    @property
    def is_eligible(self) -> bool:
        return bool(self.eligibility) and self.eligibility_passed == len(self.eligibility)

    @property
    def failed_checks(self) -> list[EligibilityCheck]:
        return [c for c in self.eligibility if not c.passed]

    @property
    def documents_signed(self) -> int:
        return sum(1 for d in self.documents if d.is_satisfactory)

    @property
    def missing_documents(self) -> list[ComplianceDocument]:
        return [d for d in self.documents if not d.is_satisfactory]

    @property
    def missing_pre_start(self) -> list[ComplianceDocument]:
        """Pre-start documents not signed — the audit red flags."""
        return [d for d in self.missing_documents if d.doc_key in PRE_START_DOCUMENTS]

    @property
    def expired_documents(self) -> list[ComplianceDocument]:
        return [d for d in self.documents if d.is_expired]

    @property
    def functional_skills_satisfied(self) -> bool:
        return bool(self.functional_skills) and all(
            fs.is_satisfied for fs in self.functional_skills
        )

    @property
    def is_audit_ready(self) -> bool:
        """Nothing an auditor could reasonably object to."""
        return self.is_eligible and not self.missing_documents

    @property
    def rag_rating(self) -> str:
        """Traffic light for the compliance dashboard.

        Ineligibility and a missing pre-start document are both red:
        each one means funding already drawn is at risk, not merely that
        paperwork is untidy.
        """
        if not self.is_eligible or self.missing_pre_start:
            return "Red"
        if self.missing_documents or self.expired_documents:
            return "Amber"
        return "Green"

    def skill(self, subject: str) -> FunctionalSkill | None:
        for fs in self.functional_skills:
            if fs.subject == subject:
                return fs
        return None


@dataclass
class AuditEntry:
    """One line of the audit trail."""

    audit_id: int
    ts: str
    actor: str | None
    actor_role: str | None
    action: str
    entity: str
    entity_id: str | None
    detail: str | None


def default_eligibility_checks() -> list[EligibilityCheck]:
    """A blank eligibility set, in the published order."""
    return [EligibilityCheck(check_key=k) for k in CHECK_KEYS]


def default_documents() -> list[ComplianceDocument]:
    """A blank document set, in the published order."""
    return [ComplianceDocument(doc_key=k) for k in DOCUMENT_KEYS]


def default_functional_skills() -> list[FunctionalSkill]:
    """A blank English and Maths pair."""
    return [FunctionalSkill(subject=s) for s in config.FUNCTIONAL_SKILLS]


def retention_expiry(end_date: str | None) -> str | None:
    """When an apprentice's record may be destroyed.

    Records are kept for the statutory retention period after the
    apprenticeship ends, so a funding audit years later still has its
    evidence.
    """
    if not end_date:
        return None
    try:
        end = date.fromisoformat(end_date)
    except ValueError:
        return None
    return end.replace(year=end.year + config.RETENTION_YEARS).isoformat()


def validate_check_key(key: str | None) -> str:
    """Check an eligibility criterion key."""
    cleaned = (key or "").strip()
    if cleaned not in CHECK_KEYS:
        allowed = ", ".join(CHECK_KEYS)
        raise ValidationError(f"Eligibility check must be one of: {allowed}")
    return cleaned


def validate_doc_key(key: str | None) -> str:
    """Check a compliance document key."""
    cleaned = (key or "").strip()
    if cleaned not in DOCUMENT_KEYS:
        allowed = ", ".join(DOCUMENT_KEYS)
        raise ValidationError(f"Document must be one of: {allowed}")
    return cleaned


def validate_doc_status(status: str | None) -> str:
    """Check a document status."""
    cleaned = (status or "Missing").strip().title()
    if cleaned not in config.DOCUMENT_STATUSES:
        allowed = ", ".join(config.DOCUMENT_STATUSES)
        raise ValidationError(f"Document status must be one of: {allowed}")
    return cleaned


def validate_subject(subject: str | None) -> str:
    """Check a functional skills subject."""
    cleaned = (subject or "").strip().title()
    if cleaned not in config.FUNCTIONAL_SKILLS:
        allowed = ", ".join(config.FUNCTIONAL_SKILLS)
        raise ValidationError(f"Subject must be one of: {allowed}")
    return cleaned


def validate_fs_status(status: str | None) -> str:
    """Check a functional skills status."""
    cleaned = (status or "Not started").strip()
    match = {s.lower(): s for s in config.FUNCTIONAL_SKILL_STATUSES}
    if cleaned.lower() not in match:
        allowed = ", ".join(config.FUNCTIONAL_SKILL_STATUSES)
        raise ValidationError(f"Functional skills status must be one of: {allowed}")
    return match[cleaned.lower()]
