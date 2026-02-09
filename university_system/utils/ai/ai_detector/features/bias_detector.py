"""Bias detection and mitigation in AI detection."""

import statistics
from typing import Any, Dict

from university_system.utils.ai.ai_detector.core.constants import logger


class BiasDetector:
    """Detects and mitigates bias in AI detection"""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.bias_metrics = {}

    def analyze_detection_bias(self, demographic_data: Dict[str, str]) -> Dict[str, Any]:
        """Analyze bias in detection across demographic groups"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            # Analyze detection rates by demographic groups
            bias_analysis = {}

            for demographic, value in demographic_data.items():
                cursor.execute('''
                SELECT AVG(r.ai_score), COUNT(*) as total_submissions,
                       SUM(CASE WHEN r.ai_score >= 0.7 THEN 1 ELSE 0 END) as flagged_submissions
                FROM ai_detector_results r
                JOIN ai_detector_submissions s ON r.submission_id = s.id
                JOIN student_demographics d ON s.student_id = d.student_id
                WHERE d.{} = ?
                '''.format(demographic), (value,))

                result = cursor.fetchone()
                if result and result['total_submissions'] > 0:
                    bias_analysis[f"{demographic}_{value}"] = {
                        'avg_ai_score': result[0],
                        'total_submissions': result['total_submissions'],
                        'flagged_rate': result['flagged_submissions'] / result['total_submissions']
                    }

            conn.close()

            # Calculate bias metrics
            flagged_rates = [data['flagged_rate'] for data in bias_analysis.values()]
            if len(flagged_rates) > 1:
                bias_variance = statistics.variance(flagged_rates)
                bias_analysis['bias_variance'] = bias_variance
                bias_analysis['needs_calibration'] = bias_variance > 0.1

            return bias_analysis

        except Exception as e:
            logger.error(f"Error analyzing detection bias: {e}")
            return {}

    def apply_bias_correction(self, ai_score: float, student_demographics: Dict) -> float:
        """Apply bias correction to AI score"""
        # Implement fairness through demographic parity or equalized odds
        correction_factor = 1.0

        # This would be calibrated based on historical bias analysis
        # For now, implementing a simple correction

        return min(1.0, ai_score * correction_factor)
