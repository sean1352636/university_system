"""
AI Detector Package - Modular AI Content Detection System.

This package provides comprehensive AI-generated content detection capabilities
for academic integrity enforcement. It was refactored from a single monolithic
module into a modular package structure.

All public symbols are re-exported here for backward compatibility.
Existing imports like:
    from education_system.post_18.university_system.infrastructure.ai.ai_detector import AIDetector
will continue to work unchanged.
"""

# Core components
from education_system.post_18.university_system.infrastructure.ai.ai_detector.core.constants import (
    REQUESTS_AVAILABLE,
    ML_AVAILABLE,
    LANG_DETECT_AVAILABLE,
    SPACY_AVAILABLE,
    TRANSFORMERS_AVAILABLE,
    OCR_AVAILABLE,
    OPENCV_AVAILABLE,
    logger,
)
from education_system.post_18.university_system.infrastructure.ai.ai_detector.core.enums import (
    DetectionMethod,
    RiskLevel,
    ViolationType,
)
from education_system.post_18.university_system.infrastructure.ai.ai_detector.core.dataclasses import (
    DetectionResult,
    SubmissionMetadata,
)
from education_system.post_18.university_system.infrastructure.ai.ai_detector.core.exceptions import (
    AIDetectionError,
    DatabaseError,
    APIError,
    ConfigurationError,
    PrivacyError,
)

# Analyzer components
from education_system.post_18.university_system.infrastructure.ai.ai_detector.analyzers import (
    TemporalAnalyzer,
    CitationVerifier,
    BehavioralAnalyzer,
    MultiModalAnalyzer,
    AdversarialDetector,
)

# Feature components
from education_system.post_18.university_system.infrastructure.ai.ai_detector.features import (
    FederatedLearning,
    PrivacyManager,
    BiasDetector,
    BlockchainAuditTrail,
    PredictiveAnalytics,
    RealTimeProcessor,
    InstitutionBenchmarking,
    StudentSelfCheckTool,
)

# ML and Visualization
from education_system.post_18.university_system.infrastructure.ai.ai_detector.ml import AdvancedMLTrainer
from education_system.post_18.university_system.infrastructure.ai.ai_detector.visualization import VisualAnalyzer

# Integration
from education_system.post_18.university_system.infrastructure.ai.ai_detector.integration import (
    APIGateway,
    ComplianceManager,
)

# Main detector class
from education_system.post_18.university_system.infrastructure.ai.ai_detector.detector import AIDetector

# CLI functions
from education_system.post_18.university_system.infrastructure.ai.ai_detector.cli import (
    integrate_ai_detector_with_main,
    create_minimal_ai_detector,
    display_ai_detector_menu_from_main,
    fix_ai_detector_database_schema,
    ultimate_demo,
    main,
)

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
    # CLI functions
    'integrate_ai_detector_with_main',
    'create_minimal_ai_detector',
    'display_ai_detector_menu_from_main',
    'fix_ai_detector_database_schema',
    'ultimate_demo',
    'main',
]
