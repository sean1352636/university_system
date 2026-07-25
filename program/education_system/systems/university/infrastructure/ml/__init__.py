"""
Machine Learning Infrastructure for University Management System.

This module provides advanced ML capabilities including:
- Course recommendation engine (collaborative filtering)
- Automated essay grading with NLP
- Plagiarism detection enhancements
- Predictive analytics for student success
- Learning path optimization
"""

from education_system.systems.university.infrastructure.ml.course_recommender import (
    CourseRecommender,
    RecommendationEngine,
    get_course_recommender,
)
from education_system.systems.university.infrastructure.ml.essay_grader import (
    EssayGrader,
    GradingRubric,
    EssayFeedback,
    get_essay_grader,
)
from education_system.systems.university.infrastructure.ml.plagiarism_detector import (
    AdvancedPlagiarismDetector,
    CodePlagiarismDetector,
    get_plagiarism_detector,
)
from education_system.systems.university.infrastructure.ml.predictive_analytics import (
    StudentSuccessPredictor,
    CoursePerformancePredictor,
    get_success_predictor,
)
from education_system.systems.university.infrastructure.ml.learning_path_optimizer import (
    LearningPathOptimizer,
    get_path_optimizer,
)

__all__ = [
    # Course recommendation
    'CourseRecommender',
    'RecommendationEngine',
    'get_course_recommender',

    # Essay grading
    'EssayGrader',
    'GradingRubric',
    'EssayFeedback',
    'get_essay_grader',

    # Plagiarism detection
    'AdvancedPlagiarismDetector',
    'CodePlagiarismDetector',
    'get_plagiarism_detector',

    # Predictive analytics
    'StudentSuccessPredictor',
    'CoursePerformancePredictor',
    'get_success_predictor',

    # Learning path
    'LearningPathOptimizer',
    'get_path_optimizer',
]
