from dataclasses import dataclass
from typing import Dict, Optional, Any
from datetime import datetime

from education_system.systems.university.shared.ai.ai_detector.core.enums import DetectionMethod, RiskLevel


@dataclass
class DetectionResult:
    """One analyser's finding. ``informational`` findings are shown to staff
    but never add to a reading's strength or risk level."""
    method: DetectionMethod
    score: float
    confidence: float
    evidence: Dict[str, Any]
    risk_level: RiskLevel
    informational: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe: the enums as their values."""
        return {"method": self.method.value, "score": self.score,
                "confidence": self.confidence, "evidence": self.evidence,
                "risk_level": self.risk_level.value, "informational": self.informational}


@dataclass
class SubmissionMetadata:
    timestamp: datetime
    time_taken: Optional[int]  # seconds
    browser_info: Optional[Dict]
    device_fingerprint: Optional[str]
    ip_address: Optional[str]
    location: Optional[Dict]
