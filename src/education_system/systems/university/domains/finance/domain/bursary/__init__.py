"""University bursary management — funds, applications, evidence, awards, payments."""
from education_system.systems.university.domains.finance.domain.bursary.services.bursary_service import (
    BursaryService,
    BursaryError,
)

__all__ = ["BursaryService", "BursaryError"]
