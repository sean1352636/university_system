"""Assessment HTTP routes: assessments, grades, external examiners.

``DOMAIN_BLUEPRINTS`` is what the university mount collects; see
``platform/delivery/api/registry.py``. One blueprint per route module.
"""

from education_system.api.university.assessment.assessment_routes import assessment_bp
from education_system.api.university.assessment.external_examiner_routes import external_examiner_bp
from education_system.api.university.assessment.grade_routes import grade_bp

DOMAIN_BLUEPRINTS = [
    assessment_bp,
    external_examiner_bp,
    grade_bp,
]

__all__ = ["DOMAIN_BLUEPRINTS", "assessment_bp", "external_examiner_bp", "grade_bp"]
