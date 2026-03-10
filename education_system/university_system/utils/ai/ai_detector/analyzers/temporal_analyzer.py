import re
import statistics
from datetime import datetime
from typing import Dict, Any, Optional

from education_system.university_system.utils.ai.ai_detector.core.constants import logger
from education_system.university_system.utils.ai.ai_detector.core.enums import DetectionMethod, RiskLevel
from education_system.university_system.utils.ai.ai_detector.core.dataclasses import DetectionResult


class TemporalAnalyzer:
    """Analyzes temporal patterns in submissions"""

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
                risk_level=RiskLevel.LOW
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
            evidence['anomaly'] = 'Writing speed too fast for complexity level'

        risk_level = RiskLevel.HIGH if score > 0.7 else RiskLevel.MEDIUM if score > 0.4 else RiskLevel.LOW

        return DetectionResult(
            method=DetectionMethod.TEMPORAL_ANALYSIS,
            score=score,
            confidence=0.8 if time_taken > 300 else 0.5,  # More confident with longer timing data
            evidence=evidence,
            risk_level=risk_level
        )

    def analyze_submission_patterns(self, student_id: str) -> Dict[str, Any]:
        """Analyze student's submission time patterns"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT submission_date, word_count
            FROM ai_detector_submissions
            WHERE student_id = ?
            ORDER BY submission_date DESC
            LIMIT 20
            ''', (student_id,))

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

            # Check for suspicious patterns
            suspicious_hours = sum(1 for h in hours if h < 6 or h > 23)  # Late night submissions
            regular_intervals = len([i for i in intervals if 23.5 <= i <= 24.5])  # Exactly 24h apart

            return {
                'total_submissions': len(submissions),
                'suspicious_hour_ratio': suspicious_hours / len(submissions),
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
