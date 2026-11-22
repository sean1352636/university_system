"""What the submission metadata shows — informational only.

Kept: how much of the text was pasted in (from the editor's paste events),
and tab switching, both shown to staff to ask about. Removed, because they
mark honest students: browser extensions (Grammarly and other writing
aids), the time of day or day of the week a student submits, the absence
of typos, and several students sharing one device (library and lab
computers). Nothing here adds to a reading's strength.
"""

from typing import Dict, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger  # noqa: F401
from education_system.systems.university.shared.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.systems.university.shared.ai.ai_detector.core.dataclasses import DetectionResult, SubmissionMetadata


class BehavioralAnalyzer:
    """Summarises submission behaviour for staff (informational)."""

    def __init__(self, detector_instance):
        self.detector = detector_instance

    def analyze_submission_behavior(self, metadata: SubmissionMetadata, text: str) -> DetectionResult:
        evidence: Dict[str, Any] = {}
        score = 0.0
        if metadata is not None and metadata.browser_info:
            evidence.update(self._analyze_browser_behavior(metadata.browser_info))
            score = evidence.get('pasted_share', 0.0)
        if not evidence:
            evidence['reason'] = 'No editor data recorded for this submission'
        evidence['note'] = ('Informational. Writing aids, submission times, spelling and shared '
                            'computers are not used.')
        return DetectionResult(
            method=DetectionMethod.BEHAVIORAL_ANALYSIS,
            score=round(min(1.0, score), 3),
            confidence=1.0 if 'pasted_share' in evidence else 0.0,
            evidence=evidence,
            risk_level=RiskLevel.MEDIUM if score >= 0.8 else RiskLevel.LOW,
            informational=True,
        )

    def _analyze_browser_behavior(self, browser_info: Dict) -> Dict[str, Any]:
        """Share of the text that arrived by pasting, and tab switches."""
        found: Dict[str, Any] = {}
        pasted = browser_info.get('pasted_characters')
        length = browser_info.get('text_length')
        if pasted is not None and length:
            found['pasted_share'] = round(min(1.0, float(pasted) / float(length)), 3)
        if 'tab_switches' in browser_info:
            found['tab_switches'] = int(browser_info['tab_switches'])
        if 'paste_events' in browser_info:
            found['paste_events'] = int(browser_info['paste_events'])
        return found

    def _analyze_device_patterns(self, device_fingerprint: str) -> float:
        """Not used: shared library and lab computers are normal."""
        return 0.0

    def _analyze_timing_patterns(self, timestamp) -> float:
        """Not used: when a student works is not evidence of anything."""
        return 0.0

    def _analyze_text_entry_patterns(self, text: str) -> float:
        """Not used: careful spelling is not evidence of anything."""
        return 0.0
