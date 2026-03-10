"""
Machine Learning Infrastructure for University Management System.

This module provides advanced ML capabilities including:
- Course recommendation engine (collaborative filtering)
- Automated essay grading with NLP
- Plagiarism detection enhancements
- Predictive analytics for student success
- Learning path optimization
"""

from .course_recommender import (
    CourseRecommender,
    RecommendationEngine,
    get_course_recommender,
)
from .essay_grader import (
    EssayGrader,
    GradingRubric,
    EssayFeedback,
    get_essay_grader,
)
from .plagiarism_detector import (
    AdvancedPlagiarismDetector,
    CodePlagiarismDetector,
    get_plagiarism_detector,
)
from .predictive_analytics import (
    StudentSuccessPredictor,
    CoursePerformancePredictor,
    get_success_predictor,
)
from .learning_path_optimizer import (
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
