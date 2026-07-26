"""
GUI Services Module

All graphical user interface implementations for the university system.
Each service provides a complete GUI for managing different aspects
of the university operations.

Available Services:
- health_portal_gui: Health records and medical management
- integration_marketplace_gui: Third-party integration management
- library_gui: Library management and book operations
- accommodation_gui: Student housing management
- course_management_gui: Academic course administration
- And many more...

Usage:
    from education_system.systems.university.interfaces.gui.shell.services import health_portal_gui
    from education_system.systems.university.interfaces.gui.shell.services import integration_marketplace_gui
"""

# Import all GUI services
__all__ = []

try:
    from education_system.systems.university.interfaces.gui.shell.services.health_portal_gui import HealthPortalGUI
    __all__.append('HealthPortalGUI')
except ImportError:
    pass

try:
    from education_system.systems.university.interfaces.gui.shell.services.integration_marketplace_gui import launch_integration_marketplace_gui
    __all__.append('launch_integration_marketplace_gui')
except ImportError:
    pass

# Add more GUI services as they are consolidated
# from .library_gui import LibraryGUI
# from .accommodation_gui import AccommodationGUI
# etc.