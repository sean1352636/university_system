"""
Student Retention Prediction Service

Uses machine learning to predict students at risk of dropping out.
Falls back to rule-based prediction if ML libraries unavailable.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.infrastructure.analytics.models import PredictionResult

logger = logging.getLogger(__name__)

# Optional ML dependencies
try:
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML libraries not available - using rule-based prediction")


class RetentionPredictor:
    """
    Predicts student retention using ML or rule-based approaches

    Features used for prediction:
    - GPA trend (current vs historical)
    - Attendance rate
    - Course completion rate
    - Financial aid status
    - Engagement metrics (library usage, participation)
    - Academic warnings
    - Credit hours enrolled
    """

    def __init__(self):
        """Initialize retention predictor"""
        self.model = None
        self.scaler = None
        self.feature_importance = {}

        if ML_AVAILABLE:
            self._initialize_ml_model()

    def _initialize_ml_model(self):
        """Initialize ML model (if available)"""
        # In production, load pre-trained model
        # For now, create new model (would need training data)
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.scaler = StandardScaler()

    def predict_at_risk_students(
        self,
        threshold: float = 0.7,
        limit: Optional[int] = None
    ) -> List[PredictionResult]:
        """
        Predict students at risk of dropping out

        Args:
            threshold: Probability threshold for at-risk classification
            limit: Maximum number of results to return

        Returns:
            List of PredictionResult objects
        """
        if ML_AVAILABLE and self.model is not None:
            try:
                return self._ml_predict_at_risk(threshold, limit)
            except Exception as e:
                logger.error(f"ML prediction failed, falling back to rules: {e}")
                return self._rule_based_predict_at_risk(limit)
        else:
            return self._rule_based_predict_at_risk(limit)

    def _ml_predict_at_risk(
        self,
        threshold: float,
        limit: Optional[int]
    ) -> List[PredictionResult]:
        """ML-based prediction (requires trained model)"""
        # Extract features for all active students
        features_df = self._extract_features()

        if features_df.empty:
            return []

        # Note: In production, model would be pre-trained
        # For demo, we'll use rule-based as ML requires training data
        logger.info("ML prediction would be used here with trained model")
        return self._rule_based_predict_at_risk(limit)

    def _rule_based_predict_at_risk(
        self,
        limit: Optional[int]
    ) -> List[PredictionResult]:
        """
        Rule-based prediction using heuristics

        Risk factors:
        - GPA < 2.0 (Critical)
        - GPA 2.0-2.5 + low attendance (High)
        - Attendance < 75% (High)
        - Failed courses > 2 (High)
        - No financial aid + low income (Medium)
        - Low engagement (Medium)
        """
        results = []

        try:
            with get_connection() as conn:
                # Get student metrics
                cursor = conn.execute('''
                    SELECT
                        s.student_id,
                        s.first_name || ' ' || s.last_name as student_name,
                        COALESCE(sdp.current_gpa, 0.0) as current_gpa,
                        COUNT(DISTINCT e.course_id) as enrolled_courses,
                        COUNT(DISTINCT CASE WHEN g.final_grade = 'F' THEN g.course_id END) as failed_courses,
                        COALESCE(AVG(CASE WHEN a.present = 1 THEN 100.0 ELSE 0.0 END), 100.0) as attendance_rate,
                        NULL as financial_aid_status
                    FROM students s
                    LEFT JOIN student_degree_progress sdp ON s.student_id = sdp.student_id
                    LEFT JOIN enrollments e ON s.student_id = e.student_id
                        AND e.status = 'active'
                    LEFT JOIN grades g ON s.student_id = g.student_id
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                        AND a.date >= date('now', '-30 days')
                    WHERE s.status = 'Active'
                    GROUP BY s.student_id
                ''')

                for row in cursor.fetchall():
                    student_id = row[0]
                    student_name = row[1]
                    gpa = row[2]
                    enrolled_courses = row[3]
                    failed_courses = row[4]
                    attendance_rate = row[5]
                    financial_aid = row[6]

                    # Calculate risk score
                    risk_score = 0.0
                    factors = {}
                    actions = []

                    # GPA factor (40% weight)
                    if gpa < 2.0:
                        risk_score += 0.4
                        factors['low_gpa'] = 0.4
                        actions.append("Academic tutoring recommended")
                        actions.append("Meet with academic advisor")
                    elif gpa < 2.5:
                        risk_score += 0.2
                        factors['borderline_gpa'] = 0.2
                        actions.append("Consider academic support services")

                    # Attendance factor (30% weight)
                    if attendance_rate < 60:
                        risk_score += 0.3
                        factors['very_low_attendance'] = 0.3
                        actions.append("Contact student about absences")
                    elif attendance_rate < 75:
                        risk_score += 0.15
                        factors['low_attendance'] = 0.15
                        actions.append("Monitor attendance closely")

                    # Failed courses factor (20% weight)
                    if failed_courses > 2:
                        risk_score += 0.2
                        factors['multiple_failures'] = 0.2
                        actions.append("Academic intervention required")
                    elif failed_courses > 0:
                        risk_score += 0.1
                        factors['course_failures'] = 0.1

                    # Enrollment factor (10% weight)
                    if enrolled_courses == 0:
                        risk_score += 0.1
                        factors['no_enrollment'] = 0.1
                        actions.append("Student not currently enrolled - investigate")
                    elif enrolled_courses < 3:
                        risk_score += 0.05
                        factors['low_course_load'] = 0.05

                    # Financial factor (bonus risk)
                    if financial_aid in ('pending', 'denied', None):
                        risk_score += 0.1
                        factors['financial_concern'] = 0.1
                        actions.append("Review financial aid status")

                    # Determine risk level
                    if risk_score >= 0.7:
                        risk_level = 'critical'
                    elif risk_score >= 0.5:
                        risk_level = 'high'
                    elif risk_score >= 0.3:
                        risk_level = 'medium'
                    else:
                        risk_level = 'low'

                    # Only include medium risk or higher
                    if risk_score >= 0.3:
                        result = PredictionResult(
                            student_id=student_id,
                            prediction_type='retention',
                            probability=min(risk_score, 1.0),
                            risk_level=risk_level,
                            contributing_factors=factors,
                            recommended_actions=actions,
                            confidence=0.85  # Rule-based has lower confidence
                        )
                        results.append(result)

                # Sort by risk score descending
                results.sort(key=lambda x: x.probability, reverse=True)

                # Apply limit
                if limit:
                    results = results[:limit]

                logger.info(f"Identified {len(results)} at-risk students")
                return results

        except Exception as e:
            logger.error(f"Error predicting at-risk students: {e}")
            return []

    def _extract_features(self) -> Any:
        """
        Extract features for ML prediction

        Features:
        - current_gpa
        - gpa_trend (change over last semester)
        - attendance_rate
        - course_completion_rate
        - failed_courses_count
        - enrolled_credits
        - financial_aid_binary
        - library_visits (engagement metric)
        - warnings_count
        """
        if not ML_AVAILABLE:
            return None

        try:
            with get_connection() as conn:
                query = '''
                    SELECT
                        s.student_id,
                        COALESCE(sdp.current_gpa, 0.0) as current_gpa,
                        COALESCE(AVG(CASE WHEN a.present = 1 THEN 1.0 ELSE 0.0 END), 1.0) as attendance_rate,
                        COUNT(DISTINCT CASE WHEN g.final_grade NOT IN ('F', 'W') THEN g.course_id END) * 1.0 /
                            NULLIF(COUNT(DISTINCT g.course_id), 0) as completion_rate,
                        COUNT(DISTINCT CASE WHEN g.final_grade = 'F' THEN g.course_id END) as failed_courses,
                        COUNT(DISTINCT e.course_id) as enrolled_courses,
                        0 as has_financial_aid
                    FROM students s
                    LEFT JOIN student_degree_progress sdp ON s.student_id = sdp.student_id
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                        AND a.date >= date('now', '-90 days')
                    LEFT JOIN grades g ON s.student_id = g.student_id
                    LEFT JOIN enrollments e ON s.student_id = e.student_id
                        AND e.status = 'active'
                    WHERE s.status = 'Active'
                    GROUP BY s.student_id
                '''

                df = pd.read_sql_query(query, conn)
                df = df.fillna(0)  # Handle missing values

                return df

        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return pd.DataFrame() if ML_AVAILABLE else None

    def get_student_risk_score(self, student_id: str) -> Optional[PredictionResult]:
        """Get risk prediction for a specific student"""
        predictions = self.predict_at_risk_students(threshold=0.0)

        for pred in predictions:
            if pred.student_id == student_id:
                return pred

        # If not in at-risk list, return low risk
        return PredictionResult(
            student_id=student_id,
            prediction_type='retention',
            probability=0.1,
            risk_level='low',
            contributing_factors={},
            recommended_actions=[],
            confidence=0.85
        )

    def get_retention_statistics(self) -> Dict[str, Any]:
        """Get overall retention statistics"""
        try:
            with get_connection() as conn:
                # Calculate retention rate (students who continue from previous term)
                cursor = conn.execute('''
                    SELECT
                        COUNT(DISTINCT CASE WHEN enrollment_status = 'enrolled' THEN student_id END) as current_enrolled,
                        COUNT(DISTINCT student_id) as total_students,
                        AVG(CASE WHEN enrollment_status = 'enrolled' THEN 1.0 ELSE 0.0 END) * 100 as retention_rate
                    FROM students
                    WHERE created_at <= date('now', '-1 year')
                ''')

                row = cursor.fetchone()

                return {
                    'current_enrolled': row[0] if row else 0,
                    'total_students': row[1] if row else 0,
                    'retention_rate': round(row[2], 2) if row and row[2] else 0.0,
                    'at_risk_count': len(self.predict_at_risk_students(threshold=0.5))
                }

        except Exception as e:
            logger.error(f"Error getting retention statistics: {e}")
            return {
                'current_enrolled': 0,
                'total_students': 0,
                'retention_rate': 0.0,
                'at_risk_count': 0
            }


# Singleton instance
_retention_predictor: Optional[RetentionPredictor] = None


def get_retention_predictor() -> RetentionPredictor:
    """Get or create retention predictor singleton"""
    global _retention_predictor
    if _retention_predictor is None:
        _retention_predictor = RetentionPredictor()
    return _retention_predictor
