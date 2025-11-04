"""
CLI Services Module

All command line interface implementations for the university system.
Each service provides command-line access to university operations.

Available Services:
- health_portal: Health records and medical management CLI
- library: Library management and book operations CLI
- accommodation: Student housing management CLI
- course_management: Academic course administration CLI
- And many more...

Usage:
    from university_system.services.cli import health_portal
    from university_system.services.cli import library
"""

# Import all CLI services
try:
    from .health_portal import (
        display_health_portal_menu,
        view_health_records,
        schedule_appointment,
        view_medical_history,
        manage_emergency_contacts,
        generate_health_reports,
        view_vaccination_records
    )
    __all__ = ['display_health_portal_menu', 'view_health_records', 'schedule_appointment',
               'view_medical_history', 'manage_emergency_contacts', 'generate_health_reports',
               'view_vaccination_records']
except ImportError:
    __all__ = []

# Add more CLI services as they are consolidated
# from .library import *
# from .accommodation import *
# etc.