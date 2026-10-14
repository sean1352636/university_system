"""Academics HTTP routes: teaching, courses, assessment, research, study.

``DOMAIN_BLUEPRINTS`` is what the university mount collects. Only blueprints
listed here are reachable; the remaining modules in this package are being
rebuilt one at a time and stay out of the list until they are ready.
"""

from education_system.api.university.academics.course_routes import course_bp

DOMAIN_BLUEPRINTS = [course_bp]

__all__ = ["DOMAIN_BLUEPRINTS", "course_bp"]
