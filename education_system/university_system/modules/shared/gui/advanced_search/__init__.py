from .base import AdvancedSearchGUI

# Import all split modules to apply monkey-patching to AdvancedSearchGUI
# Each module defines methods and patches them onto the class
from . import admin
from . import bulk_operations
from . import charts
from . import database
from . import demographics
from . import export_import
from . import menus
from . import predictive
from . import reports
from . import results
from . import scheduled_reports
from . import search_advanced
from . import search_basic
from . import search_conditional
from . import search_history
from . import search_profiles
from . import student_details
from . import utils

__all__ = ['AdvancedSearchGUI']
