"""University bursary management — funds, applications, evidence, awards, payments."""
from education_system.university_system.modules.domain.finance.bursary.services.bursary_service import (
    BursaryService,
    BursaryError,
)

__all__ = ["BursaryService", "BursaryError"]
