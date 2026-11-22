"""Attempts to get text past the checks: disguised characters.

Counted with the similarity check's own folding
(``application/integrity/plagiarism_text.fold``): a look-alike letter from another
alphabet *beside a Latin letter* (Cyrillic "а" in "rаtio"), an invisible
character *inside a word* (zero-width space, soft hyphen), plus
text-direction override marks. Whole Greek or Cyrillic words — maths,
quotations, a student's name — are not counted, and neither are double
spaces, blank lines, tabs or Unicode normalisation, which ordinary editors
produce.
"""

from typing import Dict, List

from education_system.systems.university.application.integrity import plagiarism_text as ptext
from education_system.systems.university.shared.ai.ai_detector.core.constants import logger  # noqa: F401
from education_system.systems.university.shared.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.systems.university.shared.ai.ai_detector.core.dataclasses import DetectionResult

DIRECTION_MARKS = ("‮", "‭", "‪", "‫")


class AdversarialDetector:
    """Detects disguised characters used to fool similarity and AI checks."""

    def __init__(self, detector_instance):
        self.detector = detector_instance

    def _limit(self) -> int:
        """Disguised characters that make a finding (integrity setting
        ``obfuscation_chars``)."""
        try:
            from education_system.systems.university.application.integrity import (
                access as integrity_access,
            )
            conn = self.detector._safe_db_connect()
            try:
                return int(integrity_access.number(conn, "obfuscation_chars"))
            finally:
                conn.close()
        except (AttributeError, ValueError):
            return 5

    def detect_evasion_attempts(self, text: str) -> DetectionResult:
        """Count disguised characters. The finding is a fact about the text
        (the characters are there), not a judgement about who wrote it."""
        text = str(text or "")
        disguised = ptext.fold(text)[1]
        marks = sum(text.count(m) for m in DIRECTION_MARKS)
        techniques: List[str] = []
        if disguised:
            techniques.append("disguised_characters")
        if marks:
            techniques.append("direction_marks")
        found = disguised + marks
        limit = self._limit()
        score = min(1.0, found / max(1, limit * 2))
        risk_level = (RiskLevel.HIGH if found >= limit else
                      RiskLevel.MEDIUM if found else RiskLevel.LOW)
        return DetectionResult(
            method=DetectionMethod.ADVERSARIAL_DETECTION,
            score=score,
            confidence=1.0 if found else 0.0,
            evidence={'evasion_techniques': techniques,
                      'details': {'disguised_characters': disguised, 'direction_marks': marks,
                                  'review_from': limit},
                      'note': 'Look-alike letters beside Latin letters and hidden characters '
                              'inside words only; ordinary Greek or Cyrillic words are not '
                              'counted.'},
            risk_level=risk_level,
        )

    def _count_invisible_characters(self, text: str) -> int:
        """Invisible characters sitting inside words."""
        return ptext.fold(str(text or ""))[1]

    def _detect_character_substitution(self, text: str) -> int:
        """Disguised characters (look-alikes beside Latin letters, hidden
        characters inside words)."""
        return ptext.fold(str(text or ""))[1]

    def _detect_spacing_anomalies(self, text: str) -> List[str]:
        """Not used: double spaces, blank lines and tabs come from ordinary
        editors."""
        return []

    def _detect_format_manipulation(self, text: str) -> List[str]:
        """Text-direction override marks (used to reorder what is displayed)."""
        return ['direction_marks'] if any(m in str(text or "") for m in DIRECTION_MARKS) else []

    def summary(self, text: str) -> Dict:
        return self.detect_evasion_attempts(text).to_dict()
