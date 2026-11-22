"""Submission management mixin for AIDetector: listing readings, one
reading's details and statistics — all limited to the modules the signed-in
person reviews (every module for reviewers and integrity officers), all
judged against the one review threshold (``ai_review_threshold``)."""

import json
from datetime import datetime
from typing import Dict, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger  # noqa: F401


class SubmissionMixin:
    """Mixin providing submission listing, detail retrieval, and statistics."""

    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """Counts over the readings the signed-in person may see."""
        conn = self._safe_db_connect()
        try:
            scope, params = self._scope_sql(self._module_scope(conn))
            limit = self.detection_threshold
            base = ("FROM ai_detector_submissions s LEFT JOIN ai_detector_results r ON "
                    "r.submission_id = s.id WHERE 1 = 1" + scope)
            row = conn.execute(
                "SELECT COUNT(DISTINCT s.id) AS total, COUNT(DISTINCT s.student_id) AS students, "
                "AVG(r.ai_score) AS avg, COUNT(CASE WHEN r.ai_score >= ? THEN 1 END) AS flagged, "
                "COUNT(CASE WHEN r.level LIKE 'not %' THEN 1 END) AS not_read " + base,
                [limit] + params).fetchone()
            recent = conn.execute(
                "SELECT COUNT(*) FROM ai_detector_submissions s WHERE s.submission_date >= "
                "datetime('now', '-7 days')" + scope, params).fetchone()[0]
        finally:
            conn.close()
        return {
            'total_submissions': row['total'] or 0,
            'unique_students': row['students'] or 0,
            'average_ai_score': round(row['avg'] or 0.0, 3),
            'recent_submissions_7_days': recent,
            'high_risk_submissions': row['flagged'] or 0,
            'needs_review': row['flagged'] or 0,
            'not_enough_text': row['not_read'] or 0,
            'detection_threshold': limit,
            'active_style_profiles': len(getattr(self, 'style_profiles', {})),
            'active_detection_methods': len(getattr(self, 'detection_methods', {})),
            'database_status': 'connected',
            'generated_at': datetime.now().isoformat()
        }

    def list_submissions(self, student_id: str = None, limit: int = 10,
                         include_text: bool = False) -> Dict[str, Any]:
        """Readings, newest first, on the signed-in person's modules."""
        history = self.get_submission_history(student_id=student_id, limit=limit)
        limit_at = self.detection_threshold
        submissions = []
        for item in history['submissions']:
            item['risk_level'] = self._calculate_risk_level(item.get('ai_score') or 0, limit_at)
            submissions.append(item)
        if include_text:
            conn = self._safe_db_connect()
            try:
                for item in submissions:
                    row = conn.execute("SELECT submission_text FROM ai_detector_submissions "
                                       "WHERE id = ?", (item['id'],)).fetchone()
                    item['submission_text'] = row[0] if row else ''
            finally:
                conn.close()
        return {'submissions': submissions, 'total': len(submissions),
                'student_filter': student_id, 'limit': limit, 'include_text': include_text}

    def _calculate_risk_level(self, ai_score: float, limit: float = None) -> str:
        """low / medium / high against the review threshold."""
        limit = self.detection_threshold if limit is None else limit
        if ai_score is None or ai_score < limit:
            return 'low'
        return 'high' if ai_score >= max(limit, 0.85) else 'medium'

    def get_submission_details(self, submission_id: int) -> Dict[str, Any]:
        """One reading (``submission_id`` is the detector's submission id)."""
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        conn = self._safe_db_connect()
        try:
            who = self.require_staff(conn)
            row = conn.execute('''
            SELECT s.*, r.id AS result_id, r.ai_score, r.confidence, r.level, r.method,
                   r.detailed_results, r.created_at AS analysis_date
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.id = ? ORDER BY r.id DESC LIMIT 1
            ''', (submission_id,)).fetchone()
            if not row:
                raise ValueError(f"No reading for submission {submission_id}")
            if not (integrity_access.is_officer(conn, who)
                    or integrity_access.can_review(conn, who, row['course_code'])):
                raise PermissionError("You do not review this module")
            limit = self.detection_threshold
        finally:
            conn.close()
        submission = dict(row)
        if submission.get('detailed_results'):
            try:
                submission['detailed_results'] = json.loads(submission['detailed_results'])
            except (ValueError, TypeError):
                submission['detailed_results'] = {}
        score = submission.get('ai_score') or 0
        submission['needs_review'] = score >= limit
        submission['is_ai_generated'] = submission['needs_review']
        submission['risk_level'] = self._calculate_risk_level(score, limit)
        text = submission.get('submission_text') or ''
        submission['word_count'] = submission.get('word_count') or len(text.split())
        submission['character_count'] = submission.get('character_count') or len(text)
        return submission
