"""
CLI Services Module

All command line interface implementations for the university system.
Each service provides command-line access to university operations.

Available Services:
- health_portal: Health records and medical management CLI
- library: Library management and book operations CLI
- accommodation: Student housing management CLI
- course_management: Academic course administration CLI
- betting_shop_cli: Betting shop services CLI
- butcher_cli: Butcher shop services CLI
- barber_cli: Barber shop services CLI
- nailbar_cli: Nail bar services CLI
- cinema_cli: Cinema booking services CLI
- And many more...

Usage:
    from university_system.services.cli import health_portal
    from university_system.services.cli import library
    from university_system.services.cli import betting_shop_cli
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

# Commerce and service CLI modules
try:
    from . import betting_shop_cli
    from . import butcher_cli
    from . import barber_cli
    from . import nailbar_cli
    from . import cinema_cli

    __all__.extend(['betting_shop_cli', 'butcher_cli', 'barber_cli', 'nailbar_cli', 'cinema_cli'])
except ImportError:
    pass

# Add more CLI services as they are consolidated
# Note: Import CLI services with explicit imports when available
# Example:
# from .library import library_menu, search_books, checkout_book
# from .accommodation import accommodation_menu, apply_for_housing