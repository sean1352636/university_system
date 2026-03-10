"""
Course Recommendation Engine

Uses collaborative filtering and content-based filtering to recommend courses
based on student profiles, past performance, and similar students.
"""

import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from collections import defaultdict, Counter
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CourseRecommendation:
    """Course recommendation with score and reasoning"""
    course_id: str
    course_name: str
    score: float
    reasoning: List[str]
    prerequisites_met: bool
    estimated_difficulty: float
    success_probability: float


class CourseRecommender:
    """
    Advanced course recommendation system using multiple algorithms.

    Combines:
    - Collaborative filtering (similar students)
    - Content-based filtering (course attributes)
    - Performance-based filtering (success prediction)
    - Prerequisite checking
    """

    def __init__(self, db_connection=None):
        """Initialize recommender"""
        self.db = db_connection

        # Student-course interaction matrix
        self.interaction_matrix = {}

        # Course similarity matrix
        self.course_similarity = {}

        # Student profiles
        self.student_profiles = {}

        # Course metadata
        self.course_metadata = {}

        logger.info("CourseRecommender initialized")

    def recommend_courses(
        self,
        student_id: str,
        num_recommendations: int = 10,
        filters: Optional[Dict] = None
    ) -> List[CourseRecommendation]:
        """
        Generate personalized course recommendations.

        Args:
            student_id: Student identifier
            num_recommendations: Number of recommendations to return
            filters: Optional filters (department, level, etc.)

        Returns:
            List of CourseRecommendation objects
        """
        # Load student profile
        student_profile = self._get_student_profile(student_id)

        # Get candidate courses (not already taken)
        candidate_courses = self._get_candidate_courses(student_id, filters)

        # Score each course using multiple methods
        course_scores = {}
        for course_id in candidate_courses:
            scores = {
                'collaborative': self._collaborative_filtering_score(student_id, course_id),
                'content_based': self._content_based_score(student_profile, course_id),
                'performance': self._performance_based_score(student_profile, course_id),
                'popularity': self._popularity_score(course_id),
            }

            # Weighted combination
            combined_score = (
                0.35 * scores['collaborative'] +
                0.30 * scores['content_based'] +
                0.25 * scores['performance'] +
                0.10 * scores['popularity']
            )

            course_scores[course_id] = {
                'score': combined_score,
                'component_scores': scores
            }

        # Sort by score and get top N
        top_courses = sorted(
            course_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )[:num_recommendations]

        # Create detailed recommendations
        recommendations = []
        for course_id, score_data in top_courses:
            recommendations.append(
                self._create_recommendation(
                    course_id,
                    score_data,
                    student_profile
                )
            )

        return recommendations

    def _get_student_profile(self, student_id: str) -> Dict:
        """Get comprehensive student profile"""
        if student_id in self.student_profiles:
            return self.student_profiles[student_id]

        # Build profile from database
        profile = {
            'student_id': student_id,
            'completed_courses': [],
            'grades': {},
            'interests': [],
            'major': None,
            'gpa': 0.0,
            'credits_completed': 0,
            'preferred_difficulty': 'medium'
        }

        # Load from database if available
        if self.db:
            try:
                from education_system.university_system.infrastructure.database.db import get_connection

                with get_connection() as conn:
                    # Get completed courses
                    cursor = conn.execute("""
                        SELECT course_id, final_grade
                        FROM enrollments
                        WHERE student_id = ? AND status = 'completed'
                    """, (student_id,))

                    for row in cursor:
                        profile['completed_courses'].append(row[0])
                        if row[1]:
                            profile['grades'][row[0]] = row[1]

                    # Get student info
                    cursor = conn.execute("""
                        SELECT major, gpa
                        FROM students
                        WHERE student_id = ?
                    """, (student_id,))

                    row = cursor.fetchone()
                    if row:
                        profile['major'] = row[0]
                        profile['gpa'] = row[1] or 0.0

            except Exception as e:
                logger.error(f"Error loading student profile: {e}")

        self.student_profiles[student_id] = profile
        return profile

    def _get_candidate_courses(
        self,
        student_id: str,
        filters: Optional[Dict]
    ) -> List[str]:
        """Get courses that student hasn't taken"""
        profile = self._get_student_profile(student_id)
        completed = set(profile['completed_courses'])

        candidates = []

        if self.db:
            try:
                from education_system.university_system.infrastructure.database.db import get_connection

                with get_connection() as conn:
                    query = "SELECT course_id FROM courses WHERE course_id NOT IN ({})".format(
                        ','.join('?' * len(completed)) if completed else "''"
                    )

                    params = list(completed) if completed else []

                    # Apply filters
                    if filters:
                        if 'department' in filters:
                            query += " AND department = ?"
                            params.append(filters['department'])
                        if 'level' in filters:
                            query += " AND level = ?"
                            params.append(filters['level'])

                    cursor = conn.execute(query, params)
                    candidates = [row[0] for row in cursor]

            except Exception as e:
                logger.error(f"Error getting candidate courses: {e}")

        return candidates

    def _collaborative_filtering_score(
        self,
        student_id: str,
        course_id: str
    ) -> float:
        """
        Score based on what similar students took.

        Uses user-based collaborative filtering.
        """
        try:
            # Find similar students
            similar_students = self._find_similar_students(student_id, top_k=20)

            if not similar_students:
                return 0.5  # Neutral score

            # How many similar students took this course and succeeded?
            successful_count = 0
            total_count = 0

            for similar_student_id, similarity in similar_students:
                similar_profile = self._get_student_profile(similar_student_id)

                if course_id in similar_profile['completed_courses']:
                    total_count += 1
                    grade = similar_profile['grades'].get(course_id)

                    # Consider A, B as success
                    if grade and grade in ['A', 'B']:
                        successful_count += 1

            if total_count == 0:
                return 0.5  # No data

            # Score based on success rate among similar students
            success_rate = successful_count / total_count

            # Boost if many similar students took it
            popularity_boost = min(total_count / 10, 0.2)  # Up to 0.2 boost

            return min(success_rate + popularity_boost, 1.0)

        except Exception as e:
            logger.error(f"Error in collaborative filtering: {e}")
            return 0.5

    def _find_similar_students(
        self,
        student_id: str,
        top_k: int = 20
    ) -> List[Tuple[str, float]]:
        """
        Find students with similar course history.

        Uses Jaccard similarity on course sets.
        """
        profile = self._get_student_profile(student_id)
        student_courses = set(profile['completed_courses'])

        if not student_courses:
            return []

        similarities = []

        # Compare with other students
        for other_id, other_profile in self.student_profiles.items():
            if other_id == student_id:
                continue

            other_courses = set(other_profile['completed_courses'])

            if not other_courses:
                continue

            # Jaccard similarity
            intersection = len(student_courses & other_courses)
            union = len(student_courses | other_courses)

            if union > 0:
                similarity = intersection / union
                similarities.append((other_id, similarity))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]

    def _content_based_score(
        self,
        student_profile: Dict,
        course_id: str
    ) -> float:
        """
        Score based on course content matching student interests.

        Considers major, completed courses, preferences.
        """
        score = 0.5  # Base score

        course_meta = self._get_course_metadata(course_id)

        # Major alignment
        if student_profile.get('major') == course_meta.get('department'):
            score += 0.3

        # Level appropriateness
        credits_completed = student_profile.get('credits_completed', 0)
        course_level = course_meta.get('level', 100)

        if 0 <= credits_completed < 30:  # Freshman
            if 100 <= course_level < 200:
                score += 0.2
        elif 30 <= credits_completed < 60:  # Sophomore
            if 200 <= course_level < 300:
                score += 0.2
        elif 60 <= credits_completed < 90:  # Junior
            if 300 <= course_level < 400:
                score += 0.2
        else:  # Senior
            if course_level >= 300:
                score += 0.2

        return min(score, 1.0)

    def _performance_based_score(
        self,
        student_profile: Dict,
        course_id: str
    ) -> float:
        """
        Predict student's likelihood of success in this course.

        Based on GPA, past performance in similar courses.
        """
        gpa = student_profile.get('gpa', 0.0)
        course_meta = self._get_course_metadata(course_id)

        # Base probability from GPA
        if gpa >= 3.5:
            base_prob = 0.9
        elif gpa >= 3.0:
            base_prob = 0.8
        elif gpa >= 2.5:
            base_prob = 0.7
        elif gpa >= 2.0:
            base_prob = 0.6
        else:
            base_prob = 0.5

        # Adjust for course difficulty
        difficulty = course_meta.get('difficulty', 'medium')

        if difficulty == 'easy':
            base_prob = min(base_prob + 0.1, 1.0)
        elif difficulty == 'hard':
            base_prob = max(base_prob - 0.1, 0.3)

        return base_prob

    def _popularity_score(self, course_id: str) -> float:
        """
        Score based on course popularity and ratings.
        """
        course_meta = self._get_course_metadata(course_id)

        # Enrollment count
        enrollments = course_meta.get('total_enrollments', 0)
        popularity = min(enrollments / 100, 1.0)  # Normalize

        # Course rating
        rating = course_meta.get('average_rating', 3.0)
        rating_score = (rating - 1) / 4  # Normalize 1-5 to 0-1

        return (popularity + rating_score) / 2

    def _get_course_metadata(self, course_id: str) -> Dict:
        """Get course metadata"""
        if course_id in self.course_metadata:
            return self.course_metadata[course_id]

        metadata = {
            'course_id': course_id,
            'department': None,
            'level': 100,
            'difficulty': 'medium',
            'total_enrollments': 0,
            'average_rating': 3.0,
            'prerequisites': []
        }

        # Load from database
        if self.db:
            try:
                from education_system.university_system.infrastructure.database.db import get_connection

                with get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT department, credits
                        FROM courses
                        WHERE course_id = ?
                    """, (course_id,))

                    row = cursor.fetchone()
                    if row:
                        metadata['department'] = row[0]
                        # Extract level from course_id (e.g., CS101 -> 100)
                        import re
                        match = re.search(r'(\d+)', course_id)
                        if match:
                            metadata['level'] = int(match.group(1)[0]) * 100

            except Exception as e:
                logger.error(f"Error loading course metadata: {e}")

        self.course_metadata[course_id] = metadata
        return metadata

    def _create_recommendation(
        self,
        course_id: str,
        score_data: Dict,
        student_profile: Dict
    ) -> CourseRecommendation:
        """Create detailed recommendation object"""
        course_meta = self._get_course_metadata(course_id)

        # Generate reasoning
        reasoning = []
        component_scores = score_data['component_scores']

        if component_scores['collaborative'] > 0.7:
            reasoning.append("Students similar to you succeeded in this course")
        if component_scores['content_based'] > 0.7:
            reasoning.append("Aligns well with your major and interests")
        if component_scores['performance'] > 0.8:
            reasoning.append("High predicted success rate based on your GPA")
        if component_scores['popularity'] > 0.7:
            reasoning.append("Highly rated by other students")

        # Check prerequisites (simplified)
        prerequisites_met = True  # TODO: Implement prerequisite checking

        # Estimate difficulty
        difficulty_map = {'easy': 0.3, 'medium': 0.5, 'hard': 0.8}
        estimated_difficulty = difficulty_map.get(
            course_meta.get('difficulty', 'medium'),
            0.5
        )

        return CourseRecommendation(
            course_id=course_id,
            course_name=course_meta.get('name', course_id),
            score=score_data['score'],
            reasoning=reasoning,
            prerequisites_met=prerequisites_met,
            estimated_difficulty=estimated_difficulty,
            success_probability=component_scores['performance']
        )

    def train_model(self, historical_data: Optional[Dict] = None):
        """
        Train the recommendation model.

        Args:
            historical_data: Optional historical enrollment and grade data
        """
        logger.info("Training course recommendation model...")

        # Load all student profiles for collaborative filtering
        if self.db:
            try:
                from education_system.university_system.infrastructure.database.db import get_connection

                with get_connection() as conn:
                    # Load all students
                    cursor = conn.execute("SELECT DISTINCT student_id FROM students")
                    student_ids = [row[0] for row in cursor]

                    for student_id in student_ids:
                        self._get_student_profile(student_id)

                logger.info(f"Loaded {len(student_ids)} student profiles")

            except Exception as e:
                logger.error(f"Error training model: {e}")

        logger.info("Course recommendation model trained")


# Singleton instance
_course_recommender: Optional['RecommendationEngine'] = None


class RecommendationEngine:
    """Wrapper for backward compatibility"""
    def __init__(self):
        self.recommender = CourseRecommender()


def get_course_recommender() -> CourseRecommender:
    """Get singleton course recommender instance"""
    global _course_recommender
    if _course_recommender is None:
        _course_recommender = CourseRecommender()
    return _course_recommender
