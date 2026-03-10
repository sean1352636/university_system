"""Feature components for the AI Detector."""

from education_system.university_system.utils.ai.ai_detector.features.federated_learning import FederatedLearning
from education_system.university_system.utils.ai.ai_detector.features.privacy_manager import PrivacyManager
from education_system.university_system.utils.ai.ai_detector.features.bias_detector import BiasDetector
from education_system.university_system.utils.ai.ai_detector.features.blockchain_audit import BlockchainAuditTrail
from education_system.university_system.utils.ai.ai_detector.features.predictive_analytics import PredictiveAnalytics
from education_system.university_system.utils.ai.ai_detector.features.realtime_processor import RealTimeProcessor
from education_system.university_system.utils.ai.ai_detector.features.institution_benchmarking import InstitutionBenchmarking
from education_system.university_system.utils.ai.ai_detector.features.student_self_check import StudentSelfCheckTool

__all__ = [
    'FederatedLearning', 'PrivacyManager', 'BiasDetector', 'BlockchainAuditTrail',
    'PredictiveAnalytics', 'RealTimeProcessor', 'InstitutionBenchmarking', 'StudentSelfCheckTool',
]
