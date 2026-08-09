"""First-class tutor-group entity with pastoral assignment."""
from education_system.systems.university.domains.pastoral.domain.tutor_groups.services.tutor_group_service import (
    TutorGroupService,
    TutorGroupError,
)

__all__ = ["TutorGroupService", "TutorGroupError"]
