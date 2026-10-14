"""Pastoral HTTP routes: wellbeing, support, careers, community.

``DOMAIN_BLUEPRINTS`` is what the university mount collects; see
``platform/delivery/api/registry.py``. One blueprint per route module.
"""

from education_system.api.university.pastoral.accessibility_routes import accessibility_bp
from education_system.api.university.pastoral.accommodation_routes import accommodation_bp
from education_system.api.university.pastoral.achievement_badge_routes import achievement_badge_bp
from education_system.api.university.pastoral.advising_routes import advising_bp
from education_system.api.university.pastoral.career_routes import career_bp
from education_system.api.university.pastoral.club_routes import club_bp
from education_system.api.university.pastoral.counseling_routes import counseling_bp
from education_system.api.university.pastoral.dentist_routes import dentist_bp
from education_system.api.university.pastoral.early_warning_routes import early_warning_bp
from education_system.api.university.pastoral.election_routes import election_bp
from education_system.api.university.pastoral.emergency_routes import emergency_bp
from education_system.api.university.pastoral.health_routes import health_bp
from education_system.api.university.pastoral.helpdesk_routes import helpdesk_bp
from education_system.api.university.pastoral.mentorship_routes import mentorship_bp
from education_system.api.university.pastoral.social_matching_routes import social_matching_bp
from education_system.api.university.pastoral.student_affairs_routes import student_affairs_bp
from education_system.api.university.pastoral.student_app_routes import student_app_bp
from education_system.api.university.pastoral.student_jobs_routes import student_jobs_bp
from education_system.api.university.pastoral.student_wellbeing_routes import student_wellbeing_bp
from education_system.api.university.pastoral.tutoring_routes import tutoring_bp
from education_system.api.university.pastoral.wellness_routes import wellness_bp

DOMAIN_BLUEPRINTS = [
    accessibility_bp,
    accommodation_bp,
    achievement_badge_bp,
    advising_bp,
    career_bp,
    club_bp,
    counseling_bp,
    dentist_bp,
    early_warning_bp,
    election_bp,
    emergency_bp,
    health_bp,
    helpdesk_bp,
    mentorship_bp,
    social_matching_bp,
    student_affairs_bp,
    student_app_bp,
    student_jobs_bp,
    student_wellbeing_bp,
    tutoring_bp,
    wellness_bp,
]

__all__ = ["DOMAIN_BLUEPRINTS", "accessibility_bp", "accommodation_bp", "achievement_badge_bp", "advising_bp", "career_bp", "club_bp", "counseling_bp", "dentist_bp", "early_warning_bp", "election_bp", "emergency_bp", "health_bp", "helpdesk_bp", "mentorship_bp", "social_matching_bp", "student_affairs_bp", "student_app_bp", "student_jobs_bp", "student_wellbeing_bp", "tutoring_bp", "wellness_bp"]
