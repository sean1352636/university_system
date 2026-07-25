"""Core components for the AI Detector package."""

from education_system.systems.university.infrastructure.ai.ai_detector.core.constants import (
    REQUESTS_AVAILABLE,
    ML_AVAILABLE,
    LANG_DETECT_AVAILABLE,
    SPACY_AVAILABLE,
    TRANSFORMERS_AVAILABLE,
    OCR_AVAILABLE,
    OPENCV_AVAILABLE,
    logger,
)
from education_system.systems.university.infrastructure.ai.ai_detector.core.enums import (
    DetectionMethod,
    RiskLevel,
    ViolationType,
)
from education_system.systems.university.infrastructure.ai.ai_detector.core.dataclasses import (
    DetectionResult,
    SubmissionMetadata,
)
from education_system.systems.university.infrastructure.ai.ai_detector.core.exceptions import (
    AIDetectionError,
    DatabaseError,
    APIError,
    ConfigurationError,
    PrivacyError,
)

__all__ = [
    'REQUESTS_AVAILABLE', 'ML_AVAILABLE', 'LANG_DETECT_AVAILABLE',
    'SPACY_AVAILABLE', 'TRANSFORMERS_AVAILABLE', 'OCR_AVAILABLE', 'OPENCV_AVAILABLE',
    'logger',
    'DetectionMethod', 'RiskLevel', 'ViolationType',
    'DetectionResult', 'SubmissionMetadata',
    'AIDetectionError', 'DatabaseError', 'APIError', 'ConfigurationError', 'PrivacyError',
]
