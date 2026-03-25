from education_system.university_system.modules.shared.gui.advanced_search.base import AdvancedSearchGUI

# Import all split modules to apply monkey-patching to AdvancedSearchGUI
# Each module defines methods and patches them onto the class
from education_system.university_system.modules.shared.gui.advanced_search import admin
from education_system.university_system.modules.shared.gui.advanced_search import bulk_operations
from education_system.university_system.modules.shared.gui.advanced_search import charts
from education_system.university_system.modules.shared.gui.advanced_search import database
from education_system.university_system.modules.shared.gui.advanced_search import demographics
from education_system.university_system.modules.shared.gui.advanced_search import export_import
from education_system.university_system.modules.shared.gui.advanced_search import menus
from education_system.university_system.modules.shared.gui.advanced_search import predictive
from education_system.university_system.modules.shared.gui.advanced_search import reports
from education_system.university_system.modules.shared.gui.advanced_search import results
from education_system.university_system.modules.shared.gui.advanced_search import scheduled_reports
from education_system.university_system.modules.shared.gui.advanced_search import search_advanced
from education_system.university_system.modules.shared.gui.advanced_search import search_basic
from education_system.university_system.modules.shared.gui.advanced_search import search_conditional
from education_system.university_system.modules.shared.gui.advanced_search import search_history
from education_system.university_system.modules.shared.gui.advanced_search import search_profiles
from education_system.university_system.modules.shared.gui.advanced_search import student_details
from education_system.university_system.modules.shared.gui.advanced_search import utils

__all__ = ['AdvancedSearchGUI']
