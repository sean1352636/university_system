"""Student management mixin for AIDetector - student profiles, comparisons, reports, flags, progression."""

import json
import statistics
from datetime import datetime
from typing import Dict, List, Any

from university_system.utils.ai.ai_detector.core.constants import logger


class StudentManagementMixin:
    """Mixin providing student management functions (9-14)."""

    # =========================================================================
    # STUDENT MANAGEMENT FUNCTIONS (9-14)
    # =========================================================================

    def view_student_profile(self, student_id: str) -> Dict[str, Any]:
        """
        Comprehensive view of student's submission history, risk level, and patterns.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Get all submissions for student
            cursor.execute('''
            SELECT s.*, r.ai_score, r.confidence, r.created_at as analysis_date
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.student_id = ?
            ORDER BY s.submission_date DESC
            ''', (student_id,))

            submissions = cursor.fetchall()

            # Get style fingerprint
            cursor.execute('''
            SELECT fingerprint_data, updated_at
            FROM style_fingerprints
            WHERE student_id = ?
            ''', (student_id,))

            fingerprint_row = cursor.fetchone()

            # Get any flags
            cursor.execute('''
            SELECT * FROM student_review_flags
            WHERE student_id = ?
            ORDER BY flagged_at DESC
            ''', (student_id,))

            flags = cursor.fetchall()
            conn.close()

            if not submissions:
                return {
                    'student_id': student_id,
                    'error': 'No submissions found for this student',
                    'profile': None
                }

            # Calculate statistics
            ai_scores = [s['ai_score'] for s in submissions if s['ai_score'] is not None]

            profile = {
                'student_id': student_id,
                'total_submissions': len(submissions),
                'ai_score_stats': {
                    'average': round(sum(ai_scores) / len(ai_scores), 3) if ai_scores else 0,
                    'max': round(max(ai_scores), 3) if ai_scores else 0,
                    'min': round(min(ai_scores), 3) if ai_scores else 0,
                    'std_dev': round(statistics.stdev(ai_scores), 3) if len(ai_scores) > 1 else 0
                },
                'high_risk_submissions': len([s for s in ai_scores if s >= 0.7]),
                'risk_level': self._calculate_student_risk_level(ai_scores),
                'courses': list(set(s['course_code'] for s in submissions if s['course_code'])),
                'first_submission': submissions[-1]['submission_date'] if submissions else None,
                'last_submission': submissions[0]['submission_date'] if submissions else None,
                'has_fingerprint': fingerprint_row is not None,
                'fingerprint_updated': fingerprint_row['updated_at'] if fingerprint_row else None,
                'active_flags': len([f for f in flags if f['status'] == 'active']) if flags else 0,
                'recent_submissions': [
                    {
                        'id': s['id'],
                        'title': s['title'],
                        'date': s['submission_date'],
                        'ai_score': s['ai_score'],
                        'course': s['course_code']
                    } for s in submissions[:5]
                ],
                'generated_at': datetime.now().isoformat()
            }

            return {
                'student_id': student_id,
                'profile': profile,
                'flags': [dict(f) for f in flags] if flags else []
            }

        except Exception as e:
            logger.error(f"Error viewing student profile: {e}")
            return {'student_id': student_id, 'error': str(e), 'profile': None}

    def _calculate_student_risk_level(self, ai_scores: List[float]) -> str:
        """Calculate overall risk level for a student"""
        if not ai_scores:
            return 'unknown'

        avg_score = sum(ai_scores) / len(ai_scores)
        high_risk_ratio = len([s for s in ai_scores if s >= 0.7]) / len(ai_scores)

        if avg_score >= 0.8 or high_risk_ratio >= 0.5:
            return 'critical'
        elif avg_score >= 0.6 or high_risk_ratio >= 0.3:
            return 'high'
        elif avg_score >= 0.4 or high_risk_ratio >= 0.1:
            return 'medium'
        else:
            return 'low'

    def compare_students(self, student_id_1: str, student_id_2: str) -> Dict[str, Any]:
        """
        Side-by-side comparison of two students' writing patterns.
        """
        try:
            # Get profiles for both students
            profile_1 = self.view_student_profile(student_id_1)
            profile_2 = self.view_student_profile(student_id_2)

            # Get fingerprints
            fp_1 = self.analyze_writing_style_fingerprint(student_id_1)
            fp_2 = self.analyze_writing_style_fingerprint(student_id_2)

            # Calculate similarity if both have fingerprints
            similarity = None
            if fp_1.get('fingerprint') and fp_2.get('fingerprint'):
                similarity = self._calculate_fingerprint_similarity(
                    fp_1['fingerprint'],
                    fp_2['fingerprint']
                )

            comparison = {
                'student_1': {
                    'id': student_id_1,
                    'profile': profile_1.get('profile'),
                    'fingerprint_summary': self._summarize_fingerprint(fp_1.get('fingerprint'))
                },
                'student_2': {
                    'id': student_id_2,
                    'profile': profile_2.get('profile'),
                    'fingerprint_summary': self._summarize_fingerprint(fp_2.get('fingerprint'))
                },
                'similarity_analysis': similarity,
                'potential_collaboration': similarity and similarity.get('overall_similarity', 0) > 0.8,
                'compared_at': datetime.now().isoformat()
            }

            return comparison

        except Exception as e:
            logger.error(f"Error comparing students: {e}")
            return {'error': str(e)}

    def _calculate_fingerprint_similarity(self, fp_1: Dict, fp_2: Dict) -> Dict[str, Any]:
        """Calculate similarity between two fingerprints"""
        similarities = {}

        # Compare vocabulary metrics
        if 'vocabulary_metrics' in fp_1 and 'vocabulary_metrics' in fp_2:
            v1, v2 = fp_1['vocabulary_metrics'], fp_2['vocabulary_metrics']
            vocab_sim = 1 - abs(v1.get('lexical_diversity', 0) - v2.get('lexical_diversity', 0))
            similarities['vocabulary'] = round(vocab_sim, 3)

        # Compare sentence patterns
        if 'sentence_metrics' in fp_1 and 'sentence_metrics' in fp_2:
            s1, s2 = fp_1['sentence_metrics'], fp_2['sentence_metrics']
            if s1.get('avg_length') and s2.get('avg_length'):
                len_sim = 1 - abs(s1['avg_length'] - s2['avg_length']) / max(s1['avg_length'], s2['avg_length'])
                similarities['sentence_structure'] = round(max(0, len_sim), 3)

        # Compare formality
        if 'formality_score' in fp_1 and 'formality_score' in fp_2:
            form_sim = 1 - abs(fp_1['formality_score'] - fp_2['formality_score'])
            similarities['formality'] = round(form_sim, 3)

        # Overall similarity
        if similarities:
            overall = sum(similarities.values()) / len(similarities)
        else:
            overall = 0

        return {
            'dimension_similarities': similarities,
            'overall_similarity': round(overall, 3),
            'interpretation': 'Very similar' if overall > 0.85 else 'Similar' if overall > 0.7 else 'Different'
        }

    def _summarize_fingerprint(self, fingerprint: Dict) -> Dict[str, Any]:
        """Create a summary of a fingerprint"""
        if not fingerprint:
            return None

        return {
            'vocabulary_diversity': fingerprint.get('vocabulary_metrics', {}).get('lexical_diversity'),
            'avg_sentence_length': fingerprint.get('sentence_metrics', {}).get('avg_length'),
            'formality': fingerprint.get('formality_score'),
            'transition_frequency': fingerprint.get('transition_usage', {}).get('transitions_per_100_words')
        }

    def generate_student_report_card(self, student_id: str) -> Dict[str, Any]:
        """
        Generate academic integrity report card for a student.
        """
        try:
            profile = self.view_student_profile(student_id)

            if profile.get('error'):
                return profile

            student_profile = profile.get('profile', {})

            # Calculate integrity score (inverse of risk)
            risk_scores = {'low': 0.9, 'medium': 0.7, 'high': 0.4, 'critical': 0.2, 'unknown': 0.5}
            integrity_score = risk_scores.get(student_profile.get('risk_level', 'unknown'), 0.5)

            # Trend analysis
            submissions = student_profile.get('recent_submissions', [])
            trend = 'stable'
            if len(submissions) >= 3:
                recent_scores = [s.get('ai_score', 0) or 0 for s in submissions[:3]]
                older_scores = [s.get('ai_score', 0) or 0 for s in submissions[3:6]] if len(submissions) > 3 else recent_scores

                recent_avg = sum(recent_scores) / len(recent_scores)
                older_avg = sum(older_scores) / len(older_scores)

                if recent_avg > older_avg + 0.1:
                    trend = 'worsening'
                elif recent_avg < older_avg - 0.1:
                    trend = 'improving'

            report_card = {
                'student_id': student_id,
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'integrity_score': round(integrity_score, 2),
                    'grade': self._score_to_grade(integrity_score),
                    'risk_level': student_profile.get('risk_level', 'unknown'),
                    'trend': trend
                },
                'statistics': {
                    'total_submissions': student_profile.get('total_submissions', 0),
                    'high_risk_submissions': student_profile.get('high_risk_submissions', 0),
                    'average_ai_score': student_profile.get('ai_score_stats', {}).get('average', 0),
                    'active_flags': student_profile.get('active_flags', 0)
                },
                'recommendations': self._generate_recommendations(student_profile),
                'detailed_profile': student_profile
            }

            return report_card

        except Exception as e:
            logger.error(f"Error generating report card: {e}")
            return {'error': str(e), 'student_id': student_id}

    def _score_to_grade(self, score: float) -> str:
        """Convert integrity score to letter grade"""
        if score >= 0.9:
            return 'A'
        elif score >= 0.8:
            return 'B'
        elif score >= 0.7:
            return 'C'
        elif score >= 0.6:
            return 'D'
        else:
            return 'F'

    def _generate_recommendations(self, profile: Dict) -> List[str]:
        """Generate recommendations based on profile"""
        recommendations = []

        risk_level = profile.get('risk_level', 'unknown')

        if risk_level == 'critical':
            recommendations.append("Immediate academic integrity review recommended")
            recommendations.append("Consider scheduling meeting with student")
        elif risk_level == 'high':
            recommendations.append("Monitor future submissions closely")
            recommendations.append("Consider requiring in-class writing sample for comparison")
        elif risk_level == 'medium':
            recommendations.append("Continue standard monitoring")

        if profile.get('active_flags', 0) > 0:
            recommendations.append("Review and resolve active flags")

        if not profile.get('has_fingerprint'):
            recommendations.append("Generate writing style fingerprint for future comparisons")

        return recommendations if recommendations else ["No specific recommendations at this time"]

    def flag_student_for_review(self, student_id: str, reason: str, flagged_by: str = None,
                                severity: str = 'medium', submission_id: int = None) -> Dict[str, Any]:
        """
        Manually flag student for academic integrity review.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Create flags table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_review_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                submission_id INTEGER,
                reason TEXT NOT NULL,
                severity TEXT NOT NULL,
                flagged_by TEXT,
                flagged_at TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                resolved_at TEXT,
                resolved_by TEXT,
                resolution_notes TEXT
            )
            ''')

            # Insert flag
            cursor.execute('''
            INSERT INTO student_review_flags
            (student_id, submission_id, reason, severity, flagged_by, flagged_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            ''', (
                student_id,
                submission_id,
                reason,
                severity,
                flagged_by or 'system',
                datetime.now().isoformat()
            ))

            flag_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return {
                'success': True,
                'flag_id': flag_id,
                'student_id': student_id,
                'reason': reason,
                'severity': severity,
                'flagged_at': datetime.now().isoformat(),
                'message': f'Student {student_id} has been flagged for review'
            }

        except Exception as e:
            logger.error(f"Error flagging student: {e}")
            return {'success': False, 'error': str(e)}

    def view_student_progression(self, student_id: str) -> Dict[str, Any]:
        """
        Track how student's writing has evolved over time.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.id, s.submission_text, s.title, s.submission_date, s.word_count,
                   s.course_code, r.ai_score, r.confidence
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.student_id = ?
            ORDER BY s.submission_date ASC
            ''', (student_id,))

            submissions = cursor.fetchall()
            conn.close()

            if len(submissions) < 2:
                return {
                    'student_id': student_id,
                    'error': 'Need at least 2 submissions to track progression',
                    'progression': None
                }

            # Analyze each submission
            progression = []
            for sub in submissions:
                text = sub['submission_text']
                analysis = {
                    'submission_id': sub['id'],
                    'date': sub['submission_date'],
                    'title': sub['title'],
                    'course': sub['course_code'],
                    'word_count': sub['word_count'],
                    'ai_score': sub['ai_score'],
                    'metrics': {
                        'vocabulary_richness': self._calculate_vocabulary_richness(text),
                        'sentence_complexity': self._calculate_sentence_complexity(text),
                        'formality': self._calculate_formality(text)
                    }
                }
                progression.append(analysis)

            # Calculate trends
            trends = self._calculate_progression_trends(progression)

            # Identify anomalies
            anomalies = self._identify_progression_anomalies(progression)

            return {
                'student_id': student_id,
                'total_submissions': len(submissions),
                'date_range': {
                    'first': submissions[0]['submission_date'],
                    'last': submissions[-1]['submission_date']
                },
                'progression': progression,
                'trends': trends,
                'anomalies': anomalies,
                'summary': self._generate_progression_summary(trends, anomalies),
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error viewing student progression: {e}")
            return {'student_id': student_id, 'error': str(e)}

    def _calculate_progression_trends(self, progression: List[Dict]) -> Dict[str, Any]:
        """Calculate trends across submissions"""
        if len(progression) < 2:
            return {}

        ai_scores = [p['ai_score'] for p in progression if p['ai_score'] is not None]
        vocab_scores = [p['metrics']['vocabulary_richness'] for p in progression]
        complexity_scores = [p['metrics']['sentence_complexity'] for p in progression]

        def calculate_trend(values):
            if len(values) < 2:
                return 'insufficient_data'
            first_half = values[:len(values)//2]
            second_half = values[len(values)//2:]
            diff = (sum(second_half)/len(second_half)) - (sum(first_half)/len(first_half))

            if diff > 0.1:
                return 'increasing'
            elif diff < -0.1:
                return 'decreasing'
            else:
                return 'stable'

        return {
            'ai_score_trend': calculate_trend(ai_scores) if ai_scores else 'insufficient_data',
            'vocabulary_trend': calculate_trend(vocab_scores),
            'complexity_trend': calculate_trend(complexity_scores),
            'avg_ai_score': round(sum(ai_scores)/len(ai_scores), 3) if ai_scores else None,
            'avg_vocabulary': round(sum(vocab_scores)/len(vocab_scores), 3),
            'avg_complexity': round(sum(complexity_scores)/len(complexity_scores), 3)
        }

    def _identify_progression_anomalies(self, progression: List[Dict]) -> List[Dict]:
        """Identify anomalies in progression"""
        anomalies = []

        for i in range(1, len(progression)):
            current = progression[i]
            previous = progression[i-1]

            # Check for sudden AI score jumps
            if current['ai_score'] and previous['ai_score']:
                score_jump = current['ai_score'] - previous['ai_score']
                if abs(score_jump) > 0.4:
                    anomalies.append({
                        'type': 'ai_score_anomaly',
                        'submission_id': current['submission_id'],
                        'date': current['date'],
                        'change': round(score_jump, 3),
                        'direction': 'increase' if score_jump > 0 else 'decrease'
                    })

            # Check for vocabulary jumps
            vocab_jump = current['metrics']['vocabulary_richness'] - previous['metrics']['vocabulary_richness']
            if abs(vocab_jump) > 0.3:
                anomalies.append({
                    'type': 'vocabulary_anomaly',
                    'submission_id': current['submission_id'],
                    'date': current['date'],
                    'change': round(vocab_jump, 3)
                })

        return anomalies

    def _generate_progression_summary(self, trends: Dict, anomalies: List) -> str:
        """Generate human-readable progression summary"""
        summary_parts = []

        if trends.get('ai_score_trend') == 'increasing':
            summary_parts.append("AI detection scores are trending upward, which may warrant attention.")
        elif trends.get('ai_score_trend') == 'decreasing':
            summary_parts.append("AI detection scores are decreasing, indicating improvement.")

        if trends.get('vocabulary_trend') == 'increasing':
            summary_parts.append("Vocabulary richness is improving over time.")

        if anomalies:
            summary_parts.append(f"Found {len(anomalies)} anomaly(ies) in the progression that may need review.")

        return ' '.join(summary_parts) if summary_parts else "Progression appears normal."

    def bulk_student_analysis(self, student_ids: List[str] = None, course_code: str = None,
                             limit: int = 100) -> Dict[str, Any]:
        """
        Analyze all submissions from a class/cohort at once.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Build query
            if student_ids:
                placeholders = ','.join(['?' for _ in student_ids])
                cursor.execute(f'''
                SELECT DISTINCT student_id FROM ai_detector_submissions
                WHERE student_id IN ({placeholders})
                LIMIT ?
                ''', (*student_ids, limit))
            elif course_code:
                cursor.execute('''
                SELECT DISTINCT student_id FROM ai_detector_submissions
                WHERE course_code = ?
                LIMIT ?
                ''', (course_code, limit))
            else:
                cursor.execute('''
                SELECT DISTINCT student_id FROM ai_detector_submissions
                LIMIT ?
                ''', (limit,))

            students = [row['student_id'] for row in cursor.fetchall()]
            conn.close()

            if not students:
                return {
                    'error': 'No students found matching criteria',
                    'analyzed': 0
                }

            # Analyze each student
            results = []
            high_risk_students = []

            for student_id in students:
                profile = self.view_student_profile(student_id)
                if profile.get('profile'):
                    student_summary = {
                        'student_id': student_id,
                        'risk_level': profile['profile'].get('risk_level'),
                        'avg_ai_score': profile['profile'].get('ai_score_stats', {}).get('average'),
                        'submission_count': profile['profile'].get('total_submissions'),
                        'high_risk_submissions': profile['profile'].get('high_risk_submissions')
                    }
                    results.append(student_summary)

                    if profile['profile'].get('risk_level') in ['high', 'critical']:
                        high_risk_students.append(student_summary)

            # Calculate cohort statistics
            all_avg_scores = [r['avg_ai_score'] for r in results if r['avg_ai_score']]

            cohort_stats = {
                'total_students': len(results),
                'avg_ai_score': round(sum(all_avg_scores)/len(all_avg_scores), 3) if all_avg_scores else 0,
                'high_risk_count': len(high_risk_students),
                'risk_distribution': {
                    'low': len([r for r in results if r['risk_level'] == 'low']),
                    'medium': len([r for r in results if r['risk_level'] == 'medium']),
                    'high': len([r for r in results if r['risk_level'] == 'high']),
                    'critical': len([r for r in results if r['risk_level'] == 'critical'])
                }
            }

            return {
                'analyzed_students': len(results),
                'course_code': course_code,
                'cohort_statistics': cohort_stats,
                'high_risk_students': high_risk_students,
                'all_results': results,
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in bulk student analysis: {e}")
            return {'error': str(e)}
