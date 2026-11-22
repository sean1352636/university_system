"""Menu wiring reference for the main health portal.

Kept in its own module because it is the only consumer of the health
portal's heavier UI entrypoints; importing it pulls those in, and nothing
else in this package should have to pay that cost.
"""

from education_system.systems.university.domains.health.domain.health.appointments.appointment_booking import (
    manage_provider_schedules,
    manage_screening_schedules,
    provider_dashboard,
)
from education_system.systems.university.domains.health.domain.health.records.records.templates import enhanced_health_record_templates
from education_system.systems.university.domains.health.domain.health.records.referrals.referrals import manage_referrals
from education_system.systems.university.domains.health.domain.health.records.student.dashboard import student_health_dashboard

from .integrations import integration_management
from .security_admin import advanced_security_menu

def add_missing_menu_integrations():
    """
    Integration points for adding missing menus to the main health portal.
    Add these to the display_health_portal_menu function:
    """

    # Add to Provider/Admin section:
    provider_admin_menus = [
        ("Provider Dashboard", provider_dashboard),
        ("Provider Schedule Management", manage_provider_schedules),
        ("Referral Management", manage_referrals),
        ("Screening Schedule Management", manage_screening_schedules),
        ("Enhanced Record Templates", enhanced_health_record_templates),
        ("Advanced Security Management", advanced_security_menu),
        ("Integration Management", integration_management)
    ]

    # Add to Student section:
    student_menus = [
        ("Personal Health Dashboard", student_health_dashboard)
    ]
