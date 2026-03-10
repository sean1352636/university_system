# recommendations subpackage
from .recommend_dialog import RecommendCoursesDialog
from .alternative_dialog import AlternativeCourseDialog
from .recommendations_dialog import RecommendationsDialog
from .standalone import (
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
