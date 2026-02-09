"""Feature components for the AI Detector."""

from university_system.utils.ai.ai_detector.features.federated_learning import FederatedLearning
from university_system.utils.ai.ai_detector.features.privacy_manager import PrivacyManager
from university_system.utils.ai.ai_detector.features.bias_detector import BiasDetector
from university_system.utils.ai.ai_detector.features.blockchain_audit import BlockchainAuditTrail
from university_system.utils.ai.ai_detector.features.predictive_analytics import PredictiveAnalytics
from university_system.utils.ai.ai_detector.features.realtime_processor import RealTimeProcessor
from university_system.utils.ai.ai_detector.features.institution_benchmarking import InstitutionBenchmarking
from university_system.utils.ai.ai_detector.features.student_self_check import StudentSelfCheckTool

__all__ = [
    'FederatedLearning', 'PrivacyManager', 'BiasDetector', 'BlockchainAuditTrail',
    'PredictiveAnalytics', 'RealTimeProcessor', 'InstitutionBenchmarking', 'StudentSelfCheckTool',
]
