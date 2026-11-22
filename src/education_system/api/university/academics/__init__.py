"""Academics HTTP routes: teaching, courses, assessment, research, study.

``DOMAIN_BLUEPRINTS`` is what the university mount collects. Only blueprints
listed here are reachable; the remaining modules in this package are being
rebuilt one at a time and stay out of the list until they are ready.
"""

from education_system.api.university.academics.academic_integrity_routes import (
    academic_integrity_bp,
)
from education_system.api.university.academics.ai_study_routes import ai_study_bp
from education_system.api.university.academics.calendar_feed_routes import calendar_feed_bp
from education_system.api.university.academics.course_routes import course_bp
from education_system.api.university.academics.graduation_routes import graduation_bp

DOMAIN_BLUEPRINTS = [course_bp, graduation_bp, calendar_feed_bp, academic_integrity_bp,
                     ai_study_bp]

__all__ = ["DOMAIN_BLUEPRINTS", "academic_integrity_bp", "ai_study_bp", "calendar_feed_bp",
           "course_bp", "graduation_bp"]
