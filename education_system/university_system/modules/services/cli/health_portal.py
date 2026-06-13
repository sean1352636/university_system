"""
Health Portal CLI - imports from the full implementation.

This module provides access to the full Health Portal CLI implementation
located in the domain module. It re-exports functions for
backwards compatibility.
"""
from typing import Any
import logging

from education_system.university_system.core.i18n import get_text as _t

logger = logging.getLogger(__name__)

# Try to import the full implementation
try:
    from education_system.university_system.modules.domain.health.services.health_portal import (
        display_health_portal_menu as _real_display_menu,
        display_basic_health_menu as _real_display_basic_menu,
        view_health_records as _real_view_records,
        schedule_appointment as _real_schedule_appointment,
        view_medical_history as _real_view_history,
        manage_emergency_contacts as _real_manage_contacts,
        generate_health_reports as _real_generate_reports,
        view_vaccination_records as _real_view_vaccinations,
    )

    # Re-export the real implementations
    display_health_portal_menu = _real_display_menu
    display_basic_health_menu = _real_display_basic_menu
    view_health_records = _real_view_records
    schedule_appointment = _real_schedule_appointment
    view_medical_history = _real_view_history
    manage_emergency_contacts = _real_manage_contacts
    generate_health_reports = _real_generate_reports
    view_vaccination_records = _real_view_vaccinations
    REAL_IMPLEMENTATION_AVAILABLE = True

except ImportError as e:
    logger.warning(f"Could not import full Health Portal CLI implementation: {e}")
    logger.warning("Using stub implementation with limited functionality")
    REAL_IMPLEMENTATION_AVAILABLE = False

    # Fallback stub implementations
    def display_health_portal_menu(*args: Any, **kwargs: Any) -> None:
        """Display the health portal CLI menu (stub)."""
        logger.warning("display_health_portal_menu() called but full implementation not available")
        print(_t("services.health_portal.menu_not_available"))
        return None

    def display_basic_health_menu(*args: Any, **kwargs: Any) -> None:
        """Display basic health menu (stub)."""
        logger.warning("display_basic_health_menu() called but full implementation not available")
        print(_t("services.health_portal.basic_menu_not_available"))
        return None

    def view_health_records(*args: Any, **kwargs: Any) -> None:
        """View health records (stub)."""
        logger.warning("view_health_records() called but full implementation not available")
        print(_t("services.health_portal.view_records_not_available"))
        return None

    def schedule_appointment(*args: Any, **kwargs: Any) -> None:
        """Schedule an appointment (stub)."""
        logger.warning("schedule_appointment() called but full implementation not available")
        print(_t("services.health_portal.schedule_not_available"))
        return None

    def view_medical_history(*args: Any, **kwargs: Any) -> None:
        """View medical history (stub)."""
        logger.warning("view_medical_history() called but full implementation not available")
        print(_t("services.health_portal.history_not_available"))
        return None

    def manage_emergency_contacts(*args: Any, **kwargs: Any) -> None:
        """Manage emergency contacts (stub)."""
        logger.warning("manage_emergency_contacts() called but full implementation not available")
        print(_t("services.health_portal.contacts_not_available"))
        return None

    def generate_health_reports(*args: Any, **kwargs: Any) -> None:
        """Generate health reports (stub)."""
        logger.warning("generate_health_reports() called but full implementation not available")
        print(_t("services.health_portal.reports_not_available"))
        return None

    def view_vaccination_records(*args: Any, **kwargs: Any) -> None:
        """View vaccination records (stub)."""
        logger.warning("view_vaccination_records() called but full implementation not available")
        print(_t("services.health_portal.vaccinations_not_available"))
        return None


__all__ = [
    'display_health_portal_menu',
    'display_basic_health_menu',
    'view_health_records',
    'schedule_appointment',
    'view_medical_history',
    'manage_emergency_contacts',
    'generate_health_reports',
    'view_vaccination_records',
    'REAL_IMPLEMENTATION_AVAILABLE'
]