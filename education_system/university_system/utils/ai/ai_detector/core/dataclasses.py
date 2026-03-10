from dataclasses import dataclass
from typing import Dict, Optional, Any
from datetime import datetime

from education_system.university_system.utils.ai.ai_detector.core.enums import DetectionMethod, RiskLevel


@dataclass
class DetectionResult:
    method: DetectionMethod
    score: float
    confidence: float
    evidence: Dict[str, Any]
    risk_level: RiskLevel

@dataclass
class SubmissionMetadata:
    timestamp: datetime
    time_taken: Optional[int]  # seconds
    browser_info: Optional[Dict]
    device_fingerprint: Optional[str]
    ip_address: Optional[str]
    location: Optional[Dict]
