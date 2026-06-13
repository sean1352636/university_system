"""Sixth-form REST route blueprints."""

from education_system.shared.api.sixthform.routes.academic_year_routes import (
    academic_year_bp,
)
from education_system.shared.api.sixthform.routes.students_routes import (
    students_bp,
)
from education_system.shared.api.sixthform.routes.academics_routes import (
    academics_bp,
)
from education_system.shared.api.sixthform.routes.assessment_routes import (
    assessment_bp,
)
from education_system.shared.api.sixthform.routes.finance_routes import (
    finance_bp,
)
from education_system.shared.api.sixthform.routes.governance_routes import (
    governance_bp,
)
from education_system.shared.api.sixthform.routes.pastoral_routes import (
    pastoral_bp,
)
from education_system.shared.api.sixthform.routes.progression_routes import (
    progression_bp,
)
from education_system.shared.api.sixthform.routes.reports_routes import (
    reports_bp,
)
from education_system.shared.api.sixthform.routes.staff_comms_routes import (
    staff_comms_bp,
)
from education_system.shared.api.sixthform.routes.student_services_routes import (
    student_services_bp,
)
from education_system.shared.api.sixthform.routes.advanced_search_routes import (
    advanced_search_bp,
)

__all__ = [
    "academic_year_bp",
    "students_bp",
    "academics_bp",
    "assessment_bp",
    "finance_bp",
    "governance_bp",
    "pastoral_bp",
    "progression_bp",
    "reports_bp",
    "staff_comms_bp",
    "student_services_bp",
    "advanced_search_bp",
]
