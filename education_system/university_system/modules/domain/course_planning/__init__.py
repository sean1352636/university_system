"""
Course Planning Assistant Module

Provides intelligent multi-semester course planning with:
- Prerequisite tracking and visualization
- Conflict detection and resolution
- Workload balancing
- Course recommendations
"""

from education_system.university_system.modules.domain.course_planning.services.planning_service import PlanningService

__all__ = ['PlanningService']
