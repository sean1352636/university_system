"""Learners HTTP routes: students, enrolment, student IDs, lifecycle, alumni.

``DOMAIN_BLUEPRINTS`` is what the university mount collects. Only blueprints
listed here are reachable; the remaining modules in this package are being
rebuilt one at a time, so they stay out of the list until they are ready.
"""

from education_system.api.university.learners.alumni_public_routes import alumni_public_bp
from education_system.api.university.learners.document_routes import document_bp
from education_system.api.university.learners.student_routes import student_bp

DOMAIN_BLUEPRINTS = [student_bp, alumni_public_bp, document_bp]

__all__ = ["DOMAIN_BLUEPRINTS", "alumni_public_bp", "document_bp", "student_bp"]
