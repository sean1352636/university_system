"""Course Planning CLI package."""

from education_system.systems.university.interfaces.cli.academics.course_planning.planning_cli import PlanningCLI
from education_system.systems.university.interfaces.cli.academics.course_planning.lesson_planner_cli import (
    run_lesson_planner_menu,
)

__all__ = ['PlanningCLI', 'run_lesson_planner_menu']
