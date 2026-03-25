"""
Housing GUI Package

Re-exports from sub-packages for convenience.
"""

try:
    from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui import (
        HousingGUI,
        HousingFinanceManager,
        display_housing_accommodation_menu_gui,
        send_housing_email,
        send_maintenance_email,
    )
except ImportError:
    pass
