"""Predictive analytics for academic integrity risks."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.ai.ai_detector.core.constants import logger, ML_AVAILABLE

try:
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
except ImportError:
    np = None
    RandomForestClassifier = None


class PredictiveAnalytics:
    """Predictive analytics for academic integrity risks"""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.risk_model = None

    def train_risk_prediction_model(self):
        """Train model to predict students at risk of academic dishonesty"""
        if not ML_AVAILABLE:
            return

        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            # Get training data
            cursor.execute('''
            SELECT
                s.student_id,
                COUNT(*) as submission_count,
                AVG(r.ai_score) as avg_ai_score,
                MAX(r.ai_score) as max_ai_score,
                AVG(s.word_count) as avg_word_count,
                COUNT(CASE WHEN r.ai_score >= 0.7 THEN 1 END) as violations,
                AVG(CAST(strftime('%H', s.submission_date) AS INTEGER)) as avg_submission_hour
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            GROUP BY s.student_id
            HAVING submission_count >= 3
            ''')

            data = cursor.fetchall()
            conn.close()

            if len(data) < 20:
                logger.warning("Insufficient data for risk prediction model")
                return

            # Prepare features and labels
            features = []
            labels = []

            for row in data:
                feature_vector = [
                    row['submission_count'],
                    row['avg_ai_score'],
                    row['max_ai_score'],
                    row['avg_word_count'],
                    row['avg_submission_hour']
                ]
                features.append(feature_vector)

                # Label as high risk if they have violations
                labels.append(1 if row['violations'] > 0 else 0)

            # Train model
            X = np.array(features)
            y = np.array(labels)

            self.risk_model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.risk_model.fit(X, y)

            logger.info("Risk prediction model trained successfully")

        except Exception as e:
            logger.error(f"Error training risk prediction model: {e}")

    def predict_student_risk(self, student_id: str) -> Dict[str, Any]:
        """Predict risk level for a student"""
        if not self.risk_model or not ML_AVAILABLE:
            return {'risk_score': 0, 'risk_level': 'unknown'}

        try:
            # Get student features
            features = self._extract_student_features(student_id)
            if not features:
                return {'risk_score': 0, 'risk_level': 'insufficient_data'}

            # Predict
            risk_prob = self.risk_model.predict_proba([features])[0][1]

            if risk_prob > 0.8:
                risk_level = 'high'
            elif risk_prob > 0.5:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            return {
                'risk_score': risk_prob,
                'risk_level': risk_level,
                'features_used': features
            }

        except Exception as e:
            logger.error(f"Error predicting student risk: {e}")
            return {'risk_score': 0, 'risk_level': 'error'}

    def _extract_student_features(self, student_id: str) -> Optional[List[float]]:
        """Extract features for risk prediction"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT
                COUNT(*) as submission_count,
                AVG(r.ai_score) as avg_ai_score,
                MAX(r.ai_score) as max_ai_score,
                AVG(s.word_count) as avg_word_count,
                AVG(CAST(strftime('%H', s.submission_date) AS INTEGER)) as avg_submission_hour
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()
            conn.close()

            if not result or result['submission_count'] == 0:
                return None

            return [
                result['submission_count'] or 0,
                result['avg_ai_score'] or 0,
                result['max_ai_score'] or 0,
                result['avg_word_count'] or 0,
                result['avg_submission_hour'] or 12
            ]

        except Exception as e:
            logger.error(f"Error extracting student features: {e}")
            return None
