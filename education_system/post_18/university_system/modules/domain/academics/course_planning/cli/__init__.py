"""Course Planning CLI package."""

from education_system.post_18.university_system.modules.domain.academics.course_planning.cli.planning_cli import PlanningCLI
from education_system.post_18.university_system.modules.domain.academics.course_planning.cli.lesson_planner_cli import (
    run_lesson_planner_menu,
)

__all__ = ['PlanningCLI', 'run_lesson_planner_menu']
