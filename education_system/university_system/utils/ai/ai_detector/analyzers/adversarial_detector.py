import re
from typing import List

from education_system.university_system.utils.ai.ai_detector.core.constants import logger
from education_system.university_system.utils.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.university_system.utils.ai.ai_detector.core.dataclasses import DetectionResult


class AdversarialDetector:
    """Detects attempts to fool the detection system"""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.adversarial_patterns = [
            r'[a-zA-Z]\u200b[a-zA-Z]',  # Zero-width space
            r'[а-я]',  # Cyrillic characters that look like Latin
            r'[αβγδε]',  # Greek characters
            r'[０-９]',  # Full-width numbers
        ]

    def detect_evasion_attempts(self, text: str) -> DetectionResult:
        """Detect attempts to evade AI detection"""
        score = 0
        evidence = {}
        evasion_techniques = []

        # Check for invisible characters
        invisible_chars = self._count_invisible_characters(text)
        if invisible_chars > 0:
            score += min(0.5, invisible_chars / 100)
            evasion_techniques.append('invisible_characters')
            evidence['invisible_chars'] = invisible_chars

        # Check for character substitution
        substitutions = self._detect_character_substitution(text)
        if substitutions > 0:
            score += min(0.4, substitutions / 50)
            evasion_techniques.append('character_substitution')
            evidence['substitutions'] = substitutions

        # Check for unusual spacing patterns
        spacing_anomalies = self._detect_spacing_anomalies(text)
        if spacing_anomalies:
            score += 0.3
            evasion_techniques.append('spacing_manipulation')
            evidence['spacing_anomalies'] = spacing_anomalies

        # Check for format manipulation
        format_manipulation = self._detect_format_manipulation(text)
        if format_manipulation:
            score += 0.2
            evasion_techniques.append('format_manipulation')
            evidence['format_issues'] = format_manipulation

        score = min(1.0, score)
        risk_level = RiskLevel.CRITICAL if score > 0.8 else RiskLevel.HIGH if score > 0.5 else RiskLevel.LOW

        return DetectionResult(
            method=DetectionMethod.ADVERSARIAL_DETECTION,
            score=score,
            confidence=0.9,
            evidence={
                'evasion_techniques': evasion_techniques,
                'details': evidence
            },
            risk_level=risk_level
        )

    def _count_invisible_characters(self, text: str) -> int:
        """Count invisible Unicode characters"""
        invisible_chars = [
            '\u200b',  # Zero width space
            '\u200c',  # Zero width non-joiner
            '\u200d',  # Zero width joiner
            '\u2060',  # Word joiner
            '\ufeff',  # Zero width no-break space
        ]

        count = 0
        for char in invisible_chars:
            count += text.count(char)

        return count

    def _detect_character_substitution(self, text: str) -> int:
        """Detect character substitution (e.g., Cyrillic for Latin)"""
        suspicious_count = 0

        for pattern in self.adversarial_patterns:
            matches = re.findall(pattern, text)
            suspicious_count += len(matches)

        return suspicious_count

    def _detect_spacing_anomalies(self, text: str) -> List[str]:
        """Detect unusual spacing patterns"""
        anomalies = []

        # Check for excessive spaces
        if '  ' in text:
            anomalies.append('multiple_spaces')

        # Check for unusual line breaks
        if '\n\n\n' in text:
            anomalies.append('excessive_line_breaks')

        # Check for tabs mixed with spaces
        if '\t' in text and ' ' in text:
            anomalies.append('mixed_whitespace')

        return anomalies

    def _detect_format_manipulation(self, text: str) -> List[str]:
        """Detect format manipulation attempts"""
        issues = []

        # Check for unusual Unicode normalization
        import unicodedata
        if unicodedata.normalize('NFC', text) != text:
            issues.append('unicode_normalization')

        # Check for RTL/LTR marks
        if '\u202e' in text or '\u202d' in text:
            issues.append('direction_marks')

        return issues
