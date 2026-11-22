"""
AI Detector Package - Modular AI Content Detection System.

This package provides comprehensive AI-generated content detection capabilities
for academic integrity enforcement. It was refactored from a single monolithic
module into a modular package structure.

All public symbols are re-exported here for backward compatibility, lazily
(PEP 562): importing one submodule — e.g. ``detector.reading`` from the
automatic reading after a submission — no longer loads the whole detector,
its ML libraries. The console menus live in ``shell/cli/ai/ai_detector``. Existing imports like:
    from education_system.systems.university.shared.ai.ai_detector import AIDetector
will continue to work unchanged.
"""

import importlib

_EXPORTS = {
    'REQUESTS_AVAILABLE': "education_system.systems.university.shared.ai.ai_detector.core.constants",
    'ML_AVAILABLE': "education_system.systems.university.shared.ai.ai_detector.core.constants",
    'LANG_DETECT_AVAILABLE': "education_system.systems.university.shared.ai.ai_detector.core.constants",
    'SPACY_AVAILABLE': "education_system.systems.university.shared.ai.ai_detector.core.constants",
    'TRANSFORMERS_AVAILABLE': "education_system.systems.university.shared.ai.ai_detector.core.constants",
    'OCR_AVAILABLE': "education_system.systems.university.shared.ai.ai_detector.core.constants",
    'OPENCV_AVAILABLE': "education_system.systems.university.shared.ai.ai_detector.core.constants",
    'logger': "education_system.systems.university.shared.ai.ai_detector.core.constants",
    'DetectionMethod': "education_system.systems.university.shared.ai.ai_detector.core.enums",
    'RiskLevel': "education_system.systems.university.shared.ai.ai_detector.core.enums",
    'ViolationType': "education_system.systems.university.shared.ai.ai_detector.core.enums",
    'DetectionResult': "education_system.systems.university.shared.ai.ai_detector.core.dataclasses",
    'SubmissionMetadata': "education_system.systems.university.shared.ai.ai_detector.core.dataclasses",
    'AIDetectionError': "education_system.systems.university.shared.ai.ai_detector.core.exceptions",
    'DatabaseError': "education_system.systems.university.shared.ai.ai_detector.core.exceptions",
    'APIError': "education_system.systems.university.shared.ai.ai_detector.core.exceptions",
    'ConfigurationError': "education_system.systems.university.shared.ai.ai_detector.core.exceptions",
    'PrivacyError': "education_system.systems.university.shared.ai.ai_detector.core.exceptions",
    'TemporalAnalyzer': "education_system.systems.university.shared.ai.ai_detector.analyzers",
    'CitationVerifier': "education_system.systems.university.shared.ai.ai_detector.analyzers",
    'BehavioralAnalyzer': "education_system.systems.university.shared.ai.ai_detector.analyzers",
    'MultiModalAnalyzer': "education_system.systems.university.shared.ai.ai_detector.analyzers",
    'AdversarialDetector': "education_system.systems.university.shared.ai.ai_detector.analyzers",
    'FederatedLearning': "education_system.systems.university.shared.ai.ai_detector.features",
    'PrivacyManager': "education_system.systems.university.shared.ai.ai_detector.features",
    'BiasDetector': "education_system.systems.university.shared.ai.ai_detector.features",
    'BlockchainAuditTrail': "education_system.systems.university.shared.ai.ai_detector.features",
    'PredictiveAnalytics': "education_system.systems.university.shared.ai.ai_detector.features",
    'RealTimeProcessor': "education_system.systems.university.shared.ai.ai_detector.features",
    'InstitutionBenchmarking': "education_system.systems.university.shared.ai.ai_detector.features",
    'StudentSelfCheckTool': "education_system.systems.university.shared.ai.ai_detector.features",
    'AdvancedMLTrainer': "education_system.systems.university.shared.ai.ai_detector.ml",
    'VisualAnalyzer': "education_system.systems.university.shared.ai.ai_detector.visualization",
    'APIGateway': "education_system.systems.university.shared.ai.ai_detector.integration",
    'ComplianceManager': "education_system.systems.university.shared.ai.ai_detector.integration",
    'AIDetector': "education_system.systems.university.shared.ai.ai_detector.detector",
}


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module), name)
    globals()[name] = value
    return value


__all__ = [
    # Feature flags
    'REQUESTS_AVAILABLE',
    'ML_AVAILABLE',
    'LANG_DETECT_AVAILABLE',
    'SPACY_AVAILABLE',
    'TRANSFORMERS_AVAILABLE',
    'OCR_AVAILABLE',
    'OPENCV_AVAILABLE',
    'logger',
    # Enums
    'DetectionMethod',
    'RiskLevel',
    'ViolationType',
    # Dataclasses
    'DetectionResult',
    'SubmissionMetadata',
    # Exceptions
    'AIDetectionError',
    'DatabaseError',
    'APIError',
    'ConfigurationError',
    'PrivacyError',
    # Analyzers
    'TemporalAnalyzer',
    'CitationVerifier',
    'BehavioralAnalyzer',
    'MultiModalAnalyzer',
    'AdversarialDetector',
    # Features
    'FederatedLearning',
    'PrivacyManager',
    'BiasDetector',
    'BlockchainAuditTrail',
    'PredictiveAnalytics',
    'RealTimeProcessor',
    'InstitutionBenchmarking',
    'StudentSelfCheckTool',
    # ML & Visualization
    'AdvancedMLTrainer',
    'VisualAnalyzer',
    # Integration
    'APIGateway',
    'ComplianceManager',
    # Main class
    'AIDetector',
]
