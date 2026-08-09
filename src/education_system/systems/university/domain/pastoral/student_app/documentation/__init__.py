"""Self-serve enrolment verification / status letters.

Students request "proof of study" letters (council tax, mortgage, employer,
visa) without going through the registry; staff approve and a tamper-evident
reference code + verification token are issued."""

from education_system.systems.university.domain.pastoral.student_app.documentation.services.documentation_service import (
    DocumentationService,
    LETTER_TYPES,
)

__all__ = ["DocumentationService", "LETTER_TYPES"]
