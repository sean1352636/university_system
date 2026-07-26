"""
Housing GUI Package

Re-exports from sub-packages for convenience.
"""

try:
    from education_system.systems.university.interfaces.gui.operations.campus.housing.housing_accommodation_gui import (
        HousingGUI,
        HousingFinanceManager,
        display_housing_accommodation_menu_gui,
        send_housing_email,
        send_maintenance_email,
    )
except ImportError:
    pass

# Alias: tests reference ``housing.gui.accommodation_gui`` rather than the
# full ``housing.gui.housing_accommodation_gui`` sub-package.
from education_system.systems.university.interfaces.gui.operations.campus.housing import housing_accommodation_gui as accommodation_gui
