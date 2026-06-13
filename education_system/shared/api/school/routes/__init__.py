"""Secondary school REST route blueprints.

One blueprint per module. Registered by the unified server.
"""

from education_system.shared.api.school.routes.academics_routes import (
    academics_bp,
)
from education_system.shared.api.school.routes.assessment_routes import (
    assessment_bp,
)
from education_system.shared.api.school.routes.finance_routes import (
    finance_bp,
)
from education_system.shared.api.school.routes.governance_routes import (
    governance_bp,
)
from education_system.shared.api.school.routes.pastoral_routes import (
    pastoral_bp,
)
from education_system.shared.api.school.routes.pupils_routes import (
    pupils_bp,
)
from education_system.shared.api.school.routes.reports_routes import (
    reports_bp,
)
from education_system.shared.api.school.routes.staff_comms_routes import (
    staff_comms_bp,
)

__all__ = [
    "academics_bp",
    "assessment_bp",
    "finance_bp",
    "governance_bp",
    "pastoral_bp",
    "pupils_bp",
    "reports_bp",
    "staff_comms_bp",
]

ALL_BLUEPRINTS = (
    academics_bp,
    assessment_bp,
    finance_bp,
    governance_bp,
    pastoral_bp,
    pupils_bp,
    reports_bp,
    staff_comms_bp,
)
