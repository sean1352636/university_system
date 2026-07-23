"""
Course Evaluation System Service Module
"""

from education_system.post_18.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import (
    EvaluationTemplateManager, CourseEvaluationManager,
    ResponseManager, ResultsAnalyticsManager
)
from education_system.post_18.university_system.modules.domain.academics.services.evaluation import (
    admin,
    analytics,
    authoring,
    compliance,
    extra_analytics,
    integrations,
    respondent,
    scheduling,
    workflow,
)

__all__ = [
    'EvaluationTemplateManager', 'CourseEvaluationManager',
    'ResponseManager', 'ResultsAnalyticsManager',
    'authoring', 'scheduling', 'respondent', 'analytics',
    'workflow', 'extra_analytics', 'integrations',
    'compliance', 'admin',
]
