from enum import Enum


class DetectionMethod(Enum):
    PATTERN_MATCHING = "pattern_matching"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"
    TEMPORAL_ANALYSIS = "temporal_analysis"
    CITATION_VERIFICATION = "citation_verification"
    MULTI_MODAL = "multi_modal"
    ENSEMBLE_API = "ensemble_api"
    ML_MODEL = "ml_model"
    STYLE_DEVIATION = "style_deviation"
    SENTENCE_ANALYSIS = "sentence_analysis"
    ADVERSARIAL_DETECTION = "adversarial_detection"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ViolationType(Enum):
    AI_GENERATED = "ai_generated_content"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    CITATION_FRAUD = "citation_fraud"
    TEMPORAL_ANOMALY = "temporal_anomaly"
    COLLABORATION = "unauthorized_collaboration"
