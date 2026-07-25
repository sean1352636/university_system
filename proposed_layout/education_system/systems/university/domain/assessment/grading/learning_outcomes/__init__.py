from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.domain.assessment.grading.learning_outcomes.menu import (
    learning_outcome_menu,
    generate_outcome_report,
)
from education_system.systems.university.domain.assessment.grading.learning_outcomes.management import (
    manage_learning_outcomes,
)
from education_system.systems.university.domain.assessment.grading.learning_outcomes.achievement import (
    record_outcome_achievement,
    view_student_outcome_achievement,
)
from education_system.systems.university.domain.assessment.grading.learning_outcomes.reports import (
    generate_student_outcome_report,
    generate_course_outcome_report,
    generate_all_courses_outcome_report,
    generate_module_outcome_report,
)
