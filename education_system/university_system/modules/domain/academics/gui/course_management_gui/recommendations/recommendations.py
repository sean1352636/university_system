# Backwards-compatibility shim.
# This module was split into smaller files. All public names are re-exported
# here so that existing ``from ...recommendations.recommendations import X``
# statements continue to work.

from education_system.university_system.modules.domain.academics.gui.course_management_gui.recommendations.recommend_dialog import RecommendCoursesDialog
from education_system.university_system.modules.domain.academics.gui.course_management_gui.recommendations.alternative_dialog import AlternativeCourseDialog
from education_system.university_system.modules.domain.academics.gui.course_management_gui.recommendations.recommendations_dialog import RecommendationsDialog
from education_system.university_system.modules.domain.academics.gui.course_management_gui.recommendations.standalone import (
    show_recommend_courses,
    find_alternative_courses,
    recommend_courses_wrapper,
    find_alternative_courses_wrapper,
)

__all__ = [
    "RecommendCoursesDialog",
    "AlternativeCourseDialog",
    "RecommendationsDialog",
    "show_recommend_courses",
    "find_alternative_courses",
    "recommend_courses_wrapper",
    "find_alternative_courses_wrapper",
]
