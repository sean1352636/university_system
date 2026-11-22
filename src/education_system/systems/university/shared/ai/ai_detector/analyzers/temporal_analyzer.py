import re
import statistics
from datetime import datetime
from typing import Dict, Any, Optional

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger
from education_system.systems.university.shared.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.systems.university.shared.ai.ai_detector.core.dataclasses import DetectionResult


class TemporalAnalyzer:
    """Writing speed and submission timing — informational only.

    Words per minute against rough bands is shown to staff when the editor
    recorded how long the work took, as something to ask about; it never adds
    to a reading's strength. When a student submits (late at night, at
    weekends) is reported as plain statistics and is not treated as a sign of
    anything."""

    def __init__(self, detector_instance):
        self.detector = detector_instance

    def analyze_writing_speed(self, text: str, time_taken: Optional[int]) -> DetectionResult:
        """Analyze writing speed vs complexity"""
        if not time_taken or time_taken <= 0:
            return DetectionResult(
                method=DetectionMethod.TEMPORAL_ANALYSIS,
                score=0,
                confidence=0,
                evidence={'reason': 'No timing data available'},
                risk_level=RiskLevel.LOW,
                informational=True,
            )

        word_count = len(text.split())
        wpm = (word_count / time_taken) * 60

        # Calculate text complexity
        complexity = self._calculate_complexity(text)

        # Expected WPM ranges based on complexity
        if complexity < 0.3:  # Simple text
            expected_wpm = (20, 60)
        elif complexity < 0.6:  # Medium complexity
            expected_wpm = (15, 45)
        else:  # High complexity
            expected_wpm = (10, 30)

        score = 0
        evidence = {
            'words_per_minute': wpm,
            'complexity_score': complexity,
            'expected_wpm_range': expected_wpm
        }

        if wpm > expected_wpm[1] * 2:  # Significantly faster than expected
            score = min(1.0, (wpm - expected_wpm[1]) / expected_wpm[1])
            evidence['anomaly'] = ('Written faster than usual for text of this complexity — '
                                   'ask about drafting (it may have been written elsewhere first)')
        evidence['note'] = 'Informational: rough bands, never part of a reading\'s strength.'

        risk_level = RiskLevel.MEDIUM if score > 0.4 else RiskLevel.LOW

        return DetectionResult(
            method=DetectionMethod.TEMPORAL_ANALYSIS,
            score=score,
            confidence=round(min(1.0, time_taken / 1800), 3),  # how much timing data there is
            evidence=evidence,
            risk_level=risk_level,
            informational=True,
        )

    def analyze_submission_patterns(self, student_id: str) -> Dict[str, Any]:
        """Analyze student's submission time patterns"""
        try:
            conn = self.detector._safe_db_connect()
            # Only readings on modules the signed-in member of staff reviews.
            scope, params = self.detector._scope_sql(self.detector._module_scope(conn),
                                                     "course_code")
            cursor = conn.cursor()

            cursor.execute('''
            SELECT submission_date, word_count
            FROM ai_detector_submissions
            WHERE student_id = ?''' + scope + '''
            ORDER BY submission_date DESC
            LIMIT 20
            ''', (student_id, *params))  # nosec B608 - fixed placeholders

            submissions = cursor.fetchall()
            conn.close()

            if len(submissions) < 3:
                return {'insufficient_data': True}

            # Analyze time patterns
            hours = []
            intervals = []

            for i, sub in enumerate(submissions):
                dt = datetime.fromisoformat(sub['submission_date'])
                hours.append(dt.hour)

                if i > 0:
                    prev_dt = datetime.fromisoformat(submissions[i-1]['submission_date'])
                    interval = (dt - prev_dt).total_seconds() / 3600  # hours
                    intervals.append(interval)

            # Plain statistics; when a student works is not a sign of anything.
            night_hours = sum(1 for h in hours if h < 6 or h > 23)
            regular_intervals = len([i for i in intervals if 23.5 <= i <= 24.5])

            return {
                'total_submissions': len(submissions),
                'note': 'Informational only; submission times are not used to judge work.',
                'suspicious_hour_ratio': night_hours / len(submissions),
                'regular_interval_count': regular_intervals,
                'avg_hour': sum(hours) / len(hours),
                'hour_variance': statistics.variance(hours) if len(hours) > 1 else 0
            }

        except Exception as e:
            logger.error(f"Error analyzing submission patterns: {e}")
            return {'error': str(e)}

    def _calculate_complexity(self, text: str) -> float:
        """Calculate text complexity score"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0

        words = text.split()

        # Average sentence length
        avg_sentence_length = len(words) / len(sentences)

        # Syllable complexity
        complex_words = sum(1 for word in words if self._count_syllables(word) > 2)
        complex_ratio = complex_words / len(words) if words else 0

        # Punctuation complexity
        punctuation_count = len(re.findall(r'[,;:()"]', text))
        punctuation_ratio = punctuation_count / len(text)

        # Combine metrics
        complexity = (
            min(1, avg_sentence_length / 20) * 0.4 +
            complex_ratio * 0.4 +
            min(1, punctuation_ratio * 100) * 0.2
        )

        return complexity

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word"""
        word = word.lower()
        vowels = 'aeiouy'
        syllable_count = 0
        prev_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel

        if word.endswith('e'):
            syllable_count -= 1

        return max(1, syllable_count)
