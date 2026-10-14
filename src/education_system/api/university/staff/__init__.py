"""Staff HTTP routes: HR.

``DOMAIN_BLUEPRINTS`` is what the university mount collects; see
``platform/delivery/api/registry.py``. One blueprint per route module.
"""

from education_system.api.university.staff.hr_routes import hr_bp
from education_system.api.university.staff.staff_hr_routes import staff_hr_bp

DOMAIN_BLUEPRINTS = [
    hr_bp,
    staff_hr_bp,
]

__all__ = ["DOMAIN_BLUEPRINTS", "hr_bp", "staff_hr_bp"]
