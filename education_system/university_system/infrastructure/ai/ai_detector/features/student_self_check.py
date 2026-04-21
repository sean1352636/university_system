"""Student self-assessment tool for AI detection."""

import hashlib
from datetime import datetime
from typing import Any, Dict

from education_system.university_system.infrastructure.ai.ai_detector.core.constants import logger


class StudentSelfCheckTool:
    """Tool for students to self-assess their work"""

    def __init__(self, detector_instance):
        self.detector = detector_instance

    def preview_analysis(self, text: str, student_id: str) -> Dict[str, Any]:
        """Provide non-punitive preview of analysis"""
        # Run lightweight analysis
        results = {
            'overall_assessment': 'pending',
            'suggestions': [],
            'risk_indicators': [],
            'confidence': 0
        }

        try:
            # Basic pattern detection
            pattern_results = self.detector._detect_ai_patterns(text)

            # Calculate preliminary score
            preliminary_score = pattern_results['overall_score']

            if preliminary_score > 0.8:
                results['overall_assessment'] = 'high_risk'
                results['suggestions'].extend([
                    "Consider adding more personal examples and experiences",
                    "Review your writing for overly formal or generic language",
                    "Ensure your arguments reflect your own perspective"
                ])
            elif preliminary_score > 0.5:
                results['overall_assessment'] = 'moderate_risk'
                results['suggestions'].extend([
                    "Consider making your writing more personal and specific",
                    "Add more varied sentence structures"
                ])
            else:
                results['overall_assessment'] = 'low_risk'
                results['suggestions'].append("Your writing appears to have good personal voice")

            # Educational indicators
            for indicator in pattern_results['indicators']:
                if indicator['score'] > 0.3:
                    results['risk_indicators'].append({
                        'type': indicator['name'],
                        'severity': 'high' if indicator['score'] > 0.7 else 'medium',
                        'suggestion': self._get_improvement_suggestion(indicator['name'])
                    })

            results['confidence'] = pattern_results['confidence']

            # Record self-check (anonymized)
            self._record_self_check(student_id, preliminary_score)

        except Exception as e:
            logger.error(f"Error in self-check analysis: {e}")
            results['error'] = "Analysis temporarily unavailable"

        return results

    def _get_improvement_suggestion(self, indicator_name: str) -> str:
        """Get educational suggestion for improvement"""
        suggestions = {
            'lack_of_personal_references': "Try including more personal experiences, examples from your own life, or references to 'I think' or 'In my experience'",
            'hedging_language': "Consider being more direct in your statements rather than using phrases like 'it seems' or 'it appears'",
            'perfectly_balanced_arguments': "Real arguments often have stronger evidence on one side. Consider developing your strongest points more fully",
            'formal_language_overuse': "Academic writing can still have personality. Try varying your vocabulary and sentence structures",
            'ai_fingerprints': "Some phrases in your text are commonly associated with AI writing. Try expressing ideas in your own words"
        }

        return suggestions.get(indicator_name, "Consider reviewing this aspect of your writing for authenticity")

    def _record_self_check(self, student_id: str, score: float):
        """Record self-check usage (anonymized)"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            # Create table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS self_check_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_hash TEXT NOT NULL,
                score_range TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            ''')

            # Hash student ID for privacy
            student_hash = hashlib.sha256(student_id.encode()).hexdigest()[:16]

            # Score range for anonymization
            if score > 0.7:
                score_range = 'high'
            elif score > 0.4:
                score_range = 'medium'
            else:
                score_range = 'low'

            cursor.execute('''
            INSERT INTO self_check_usage (student_hash, score_range, timestamp)
            VALUES (?, ?, ?)
            ''', (student_hash, score_range, datetime.now().isoformat()))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.debug(f"Error recording self-check: {e}")
