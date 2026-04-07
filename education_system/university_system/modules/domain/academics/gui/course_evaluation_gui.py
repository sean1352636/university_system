# Backward-compatible re-export — code moved to course_management_gui/
from education_system.university_system.modules.domain.academics.gui.course_management_gui.course_evaluation_gui import *  # noqa: F401,F403
from education_system.university_system.modules.domain.academics.gui.course_management_gui.course_evaluation_gui import (
    CourseEvaluationGUI,
    launch_course_evaluation_gui,
)
