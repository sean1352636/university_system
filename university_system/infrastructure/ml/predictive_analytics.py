"""
Predictive Analytics for Student Success

Predicts student outcomes and course performance using historical data.
"""

import logging
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SuccessPrediction:
    """Student success prediction"""
    predicted_gpa: float
    graduation_probability: float
    at_risk: bool
    risk_factors: List[str]
    recommendations: List[str]


class StudentSuccessPredictor:
    """Predicts student success metrics"""

    def __init__(self):
        """Initialize predictor"""
        logger.info("StudentSuccessPredictor initialized")

    def predict_success(
        self,
        student_id: str,
        current_gpa: float,
        credits_completed: int,
        attendance_rate: float
    ) -> SuccessPrediction:
        """
        Predict student success probability.

        Args:
            student_id: Student identifier
            current_gpa: Current GPA
            credits_completed: Credits completed
            attendance_rate: Attendance rate (0-1)

        Returns:
            SuccessPrediction with predicted outcomes
        """
        # Simple predictive model (can be enhanced with ML)
        predicted_gpa = current_gpa * 0.7 + attendance_rate * 3.0 * 0.3

        graduation_prob = 0.5
        if current_gpa >= 3.0:
            graduation_prob += 0.3
        if attendance_rate >= 0.9:
            graduation_prob += 0.2

        # Identify risk factors
        risk_factors = []
        at_risk = False

        if current_gpa < 2.5:
            risk_factors.append("Low GPA")
            at_risk = True
        if attendance_rate < 0.8:
            risk_factors.append("Poor attendance")
            at_risk = True
        if credits_completed < 30 and current_gpa < 3.0:
            risk_factors.append("Slow progress")

        # Generate recommendations
        recommendations = []
        if current_gpa < 3.0:
            recommendations.append("Consider tutoring services")
        if attendance_rate < 0.9:
            recommendations.append("Improve class attendance")
        if at_risk:
            recommendations.append("Meet with academic advisor")

        return SuccessPrediction(
            predicted_gpa=round(predicted_gpa, 2),
            graduation_probability=round(graduation_prob, 2),
            at_risk=at_risk,
            risk_factors=risk_factors,
            recommendations=recommendations
        )


class CoursePerformancePredictor:
    """Predicts course-level performance"""

    def __init__(self):
        """Initialize predictor"""
        logger.info("CoursePerformancePredictor initialized")

    def predict_grade(
        self,
        student_id: str,
        course_id: str,
        student_gpa: float
    ) -> Dict:
        """Predict expected grade in a course"""
        # Simple model
        if student_gpa >= 3.5:
            predicted_grade = 'A'
            probability = 0.8
        elif student_gpa >= 3.0:
            predicted_grade = 'B'
            probability = 0.75
        elif student_gpa >= 2.5:
            predicted_grade = 'C'
            probability = 0.7
        else:
            predicted_grade = 'D'
            probability = 0.6

        return {
            'predicted_grade': predicted_grade,
            'confidence': probability,
            'success_probability': probability
        }


_success_predictor: Optional[StudentSuccessPredictor] = None


def get_success_predictor() -> StudentSuccessPredictor:
    """Get singleton success predictor"""
    global _success_predictor
    if _success_predictor is None:
        _success_predictor = StudentSuccessPredictor()
    return _success_predictor
