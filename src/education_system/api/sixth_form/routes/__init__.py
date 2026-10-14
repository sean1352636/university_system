"""Sixth-form REST route blueprints."""

from education_system.api.sixth_form.routes.academic_year_routes import (
    academic_year_bp,
)
from education_system.api.sixth_form.routes.students_routes import (
    students_bp,
)
from education_system.api.sixth_form.routes.academics_routes import (
    academics_bp,
)
from education_system.api.sixth_form.routes.assessment_routes import (
    assessment_bp,
)
from education_system.api.sixth_form.routes.finance_routes import (
    finance_bp,
)
from education_system.api.sixth_form.routes.governance_routes import (
    governance_bp,
)
from education_system.api.sixth_form.routes.pastoral_routes import (
    pastoral_bp,
)
from education_system.api.sixth_form.routes.progression_routes import (
    progression_bp,
)
from education_system.api.sixth_form.routes.reports_routes import (
    reports_bp,
)
from education_system.api.sixth_form.routes.staff_comms_routes import (
    staff_comms_bp,
)
from education_system.api.sixth_form.routes.student_services_routes import (
    student_services_bp,
)
from education_system.api.sixth_form.routes.advanced_search_routes import (
    advanced_search_bp,
)
from education_system.api.sixth_form.routes.calendar_routes import (
    calendar_bp,
)

__all__ = [
    "academic_year_bp",
    "calendar_bp",
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

# ── Mounted surface ──────────────────────────────────────────────────
# One list instead of a hand-maintained name tuple in registry.py: adding a
# blueprint here is enough to mount it.
from education_system.api.sixth_form.routes.menu import MENU_BLUEPRINTS  # noqa: E402

ALL_BLUEPRINTS = (
    academic_year_bp,
    students_bp,
    academics_bp,
    assessment_bp,
    finance_bp,
    governance_bp,
    pastoral_bp,
    progression_bp,
    reports_bp,
    staff_comms_bp,
    student_services_bp,
    advanced_search_bp,
    calendar_bp,
) + tuple(MENU_BLUEPRINTS)
