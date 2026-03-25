"""Analytics manager package for grade tracking."""

from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.manager import AnalyticsManager
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.db_init import init_basic_database, init_enhanced_grades_db
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.utils import percentage_to_letter, letter_to_percentage, letter_to_gpa
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.constants import GRADE_SYSTEMS

__all__ = [
    "AnalyticsManager",
    "init_basic_database",
    "init_enhanced_grades_db",
    "percentage_to_letter",
    "letter_to_percentage",
    "letter_to_gpa",
    "GRADE_SYSTEMS",
]
