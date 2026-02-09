"""Main AIDetector class combining all mixin functionality."""

from university_system.utils.ai.ai_detector.detector.database_mixin import DatabaseMixin
from university_system.utils.ai.ai_detector.detector.submission_mixin import SubmissionMixin
from university_system.utils.ai.ai_detector.detector.core_analysis_mixin import CoreAnalysisMixin
from university_system.utils.ai.ai_detector.detector.enhanced_detection_mixin import EnhancedDetectionMixin
from university_system.utils.ai.ai_detector.detector.student_management_mixin import StudentManagementMixin
from university_system.utils.ai.ai_detector.detector.analytics_mixin import AnalyticsMixin
from university_system.utils.ai.ai_detector.detector.alerts_mixin import AlertsMixin
from university_system.utils.ai.ai_detector.detector.batch_operations_mixin import BatchOperationsMixin
from university_system.utils.ai.ai_detector.detector.course_management_mixin import CourseManagementMixin
from university_system.utils.ai.ai_detector.detector.model_management_mixin import ModelManagementMixin
from university_system.utils.ai.ai_detector.detector.audit_privacy_mixin import AuditPrivacyMixin
from university_system.utils.ai.ai_detector.detector.integration_mixin import IntegrationMixin


class AIDetector(
    DatabaseMixin,
    SubmissionMixin,
    CoreAnalysisMixin,
    EnhancedDetectionMixin,
    StudentManagementMixin,
    AnalyticsMixin,
    AlertsMixin,
    BatchOperationsMixin,
    CourseManagementMixin,
    ModelManagementMixin,
    AuditPrivacyMixin,
    IntegrationMixin,
):
    """
    AI Content Detection System - Main class.

    Combines all detector functionality through mixins for maintainability.
    The __init__ method is defined in DatabaseMixin.
    """
    pass
