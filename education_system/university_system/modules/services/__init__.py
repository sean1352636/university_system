"""
Consolidated University System Services

This module provides easy access to all university system services
organized by interface type (GUI, CLI, API).

Organization:
- gui/: All graphical user interface implementations
- cli/: All command line interface implementations
- api/: All REST API implementations

This reorganization improves:
1. Code discoverability - clear separation by interface type
2. Import paths - shorter, more intuitive imports
3. Maintenance - easier to find and update related functionality
4. Testing - can test different interfaces separately
"""

# Re-export key services for backward compatibility
try:
    from education_system.university_system.modules.services.gui import HealthPortalGUI
except ImportError:
    HealthPortalGUI = None

try:
    from education_system.university_system.modules.services.cli import (
        display_health_portal_menu,
        view_health_records,
        schedule_appointment,
        view_medical_history,
        manage_emergency_contacts,
        generate_health_reports,
        view_vaccination_records
    )
except ImportError:
    display_health_portal_menu = None
    view_health_records = None
    schedule_appointment = None
    view_medical_history = None
    manage_emergency_contacts = None
    generate_health_reports = None
    view_vaccination_records = None

# Version and metadata
__version__ = "2.0.0"
__author__ = "University System Team"
__description__ = "Consolidated University System Services"