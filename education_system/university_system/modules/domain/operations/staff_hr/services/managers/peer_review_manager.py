"""
Peer Review Manager

Provides functionality for:
- Peer review cycle creation and lifecycle management
- Submission management with revision tracking
- Reviewer assignment and progress tracking
- Structured feedback collection with multi-dimensional ratings
- Shared resource library with ratings and downloads
- Reporting on cycle statistics and reviewer workload
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class PeerReviewManager:
    """Manager for peer review cycles, submissions, assignments, feedback, and resources."""

    # ==================== CYCLE MANAGEMENT ====================

    @staticmethod
    def create_cycle(name: str, description: str, cycle_type: str,
                     department: str, start_date: str, end_date: str,
                     created_by: str) -> int:
        """Create a new peer review cycle.

        Args:
            name: Name of the review cycle.
            description: Purpose or description of the cycle.
            cycle_type: Type of cycle (e.g. 'annual', 'mid_term', 'ad_hoc').
            department: Department the cycle belongs to.
            start_date: Start date for the cycle (ISO format).
            end_date: End date for the cycle (ISO format).
            created_by: User ID of the creator.

        Returns:
            The ID of the newly created cycle.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO peer_review_cycles (
                    name, description, cycle_type, department,
                    start_date, end_date, status, created_by,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)
            ''', (
                name, description, cycle_type, department,
                start_date, end_date, created_by,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            cycle_id = cursor.lastrowid
            log_activity('create', 'peer_review_cycle', details={
                'cycle_id': cycle_id, 'name': name,
                'created_by': created_by,
            })
            return cycle_id

    @staticmethod
    def get_cycle(cycle_id: int) -> Optional[Dict[str, Any]]:
        """Get a single peer review cycle by ID.

        Args:
            cycle_id: The cycle's primary key.

        Returns:
            A dict of the cycle row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM peer_review_cycles WHERE cycle_id = ?
            ''', (cycle_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_cycles(status: str = None,
                   cycle_type: str = None) -> List[Dict[str, Any]]:
        """Get peer review cycles with optional filters.

        Args:
            status: Filter by cycle status (e.g. 'draft', 'active', 'closed').
            cycle_type: Filter by cycle type.

        Returns:
            A list of cycle dicts ordered by start_date descending.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM peer_review_cycles WHERE 1=1'
            params: list = []

            if status:
                query += ' AND status = ?'
                params.append(status)

            if cycle_type:
                query += ' AND cycle_type = ?'
                params.append(cycle_type)

            query += ' ORDER BY start_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_cycle(cycle_id: int, **data) -> None:
        """Update allowed fields on a peer review cycle.

        Allowed fields: name, description, cycle_type, department,
        start_date, end_date, status.

        Args:
            cycle_id: The cycle to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'name', 'description', 'cycle_type', 'department',
            'start_date', 'end_date', 'status',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(cycle_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE peer_review_cycles SET ' + ', '.join(fields) + ' WHERE cycle_id = ?',
                values)
            log_activity('update', 'peer_review_cycle', details={
                'cycle_id': cycle_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def activate_cycle(cycle_id: int) -> None:
        """Activate a peer review cycle by setting its status to 'active'.

        Args:
            cycle_id: The cycle to activate.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE peer_review_cycles
                SET status = 'active', updated_at = ?
                WHERE cycle_id = ?
            ''', (datetime.now().isoformat(), cycle_id))
            log_activity('update', 'peer_review_cycle', details={
                'cycle_id': cycle_id, 'action': 'activated',
            })

    # ==================== SUBMISSION MANAGEMENT ====================

    @staticmethod
    def create_submission(cycle_id: int, submitter_id: str, title: str,
                          description: str, material_type: str,
                          course_code: str, file_path: str,
                          file_name: str) -> int:
        """Create a new peer review submission.

        The submission is created with status 'draft' and version 1.

        Args:
            cycle_id: The review cycle this submission belongs to.
            submitter_id: User ID of the person submitting.
            title: Title of the submission.
            description: Description of the submitted material.
            material_type: Type of material (e.g. 'syllabus', 'lecture', 'assessment').
            course_code: Course code the material is associated with.
            file_path: Path to the uploaded file.
            file_name: Original name of the uploaded file.

        Returns:
            The ID of the newly created submission.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO peer_review_submissions (
                    cycle_id, submitter_id, title, description,
                    material_type, course_code, file_path, file_name,
                    status, version, parent_submission_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', 1, NULL, ?, ?)
            ''', (
                cycle_id, submitter_id, title, description,
                material_type, course_code, file_path, file_name,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            submission_id = cursor.lastrowid
            log_activity('create', 'peer_review_submission', details={
                'submission_id': submission_id, 'cycle_id': cycle_id,
                'submitter_id': submitter_id, 'title': title,
            })
            return submission_id

    @staticmethod
    def get_submission(submission_id: int) -> Optional[Dict[str, Any]]:
        """Get a single submission by ID.

        Args:
            submission_id: The submission's primary key.

        Returns:
            A dict of the submission row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM peer_review_submissions WHERE submission_id = ?
            ''', (submission_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_submissions(cycle_id: int = None, submitter_id: str = None,
                        status: str = None) -> List[Dict[str, Any]]:
        """Get submissions with optional filters.

        Args:
            cycle_id: Filter by review cycle.
            submitter_id: Filter by submitter user ID.
            status: Filter by submission status.

        Returns:
            A list of submission dicts ordered by created_at descending.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM peer_review_submissions WHERE 1=1'
            params: list = []

            if cycle_id:
                query += ' AND cycle_id = ?'
                params.append(cycle_id)

            if submitter_id:
                query += ' AND submitter_id = ?'
                params.append(submitter_id)

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY created_at DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def submit_for_review(submission_id: int) -> None:
        """Submit a draft submission for peer review.

        Sets the submission status to 'submitted' and records the
        submitted_date as the current timestamp.

        Args:
            submission_id: The submission to submit for review.
        """
        now = datetime.now().isoformat()
        with transaction() as conn:
            conn.execute('''
                UPDATE peer_review_submissions
                SET status = 'submitted', submitted_date = ?, updated_at = ?
                WHERE submission_id = ?
            ''', (now, now, submission_id))
            log_activity('update', 'peer_review_submission', details={
                'submission_id': submission_id, 'action': 'submitted_for_review',
            })

    @staticmethod
    def create_revision(submission_id: int, file_path: str,
                        file_name: str) -> int:
        """Create a new revision of an existing submission.

        Creates a new submission record with an incremented version number,
        copying the cycle_id, submitter_id, title, description, material_type,
        and course_code from the original submission. The new submission's
        parent_submission_id is set to the original submission_id.

        Args:
            submission_id: The original submission to revise.
            file_path: Path to the new revision file.
            file_name: Original name of the new revision file.

        Returns:
            The ID of the newly created revision submission.

        Raises:
            ValueError: If the original submission is not found.
        """
        with transaction() as conn:
            row = conn.execute('''
                SELECT * FROM peer_review_submissions WHERE submission_id = ?
            ''', (submission_id,)).fetchone()

            if not row:
                raise ValueError(
                    f"Submission {submission_id} not found"
                )

            original = dict(row)

            cursor = conn.execute('''
                INSERT INTO peer_review_submissions (
                    cycle_id, submitter_id, title, description,
                    material_type, course_code, file_path, file_name,
                    status, version, parent_submission_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
            ''', (
                original['cycle_id'], original['submitter_id'],
                original['title'], original['description'],
                original['material_type'], original['course_code'],
                file_path, file_name,
                original['version'] + 1, submission_id,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            new_submission_id = cursor.lastrowid
            log_activity('create', 'peer_review_submission', details={
                'submission_id': new_submission_id,
                'parent_submission_id': submission_id,
                'version': original['version'] + 1,
                'action': 'revision',
            })
            return new_submission_id

    @staticmethod
    def get_revision_history(submission_id: int) -> List[Dict[str, Any]]:
        """Get the full revision history for a submission by walking the parent chain.

        Starting from the given submission, follows parent_submission_id
        links backwards to build the complete revision chain, ordered
        from earliest version to latest.

        Args:
            submission_id: The submission to trace the revision history for.

        Returns:
            A list of submission dicts representing the revision chain,
            ordered from the oldest version to the newest.
        """
        with get_connection() as conn:
            history = []
            current_id = submission_id

            while current_id is not None:
                row = conn.execute('''
                    SELECT * FROM peer_review_submissions WHERE submission_id = ?
                ''', (current_id,)).fetchone()

                if not row:
                    break

                submission = dict(row)
                history.append(submission)
                current_id = submission.get('parent_submission_id')

            # Reverse so oldest version comes first
            history.reverse()
            return history

    # ==================== ASSIGNMENT MANAGEMENT ====================

    @staticmethod
    def assign_reviewer(submission_id: int, reviewer_id: str,
                        assigned_by: str, due_date: str) -> int:
        """Assign a reviewer to a submission.

        Creates a new assignment with status 'assigned' and also sets the
        submission status to 'under_review'.

        Args:
            submission_id: The submission to assign a reviewer to.
            reviewer_id: User ID of the assigned reviewer.
            assigned_by: User ID of the person making the assignment.
            due_date: Due date for the review (ISO format).

        Returns:
            The ID of the newly created assignment.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO peer_review_assignments (
                    submission_id, reviewer_id, assigned_by, due_date,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'assigned', ?, ?)
            ''', (
                submission_id, reviewer_id, assigned_by, due_date,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            assignment_id = cursor.lastrowid

            # Update the submission status to under_review
            conn.execute('''
                UPDATE peer_review_submissions
                SET status = 'under_review', updated_at = ?
                WHERE submission_id = ?
            ''', (datetime.now().isoformat(), submission_id))

            log_activity('create', 'peer_review_assignment', details={
                'assignment_id': assignment_id,
                'submission_id': submission_id,
                'reviewer_id': reviewer_id,
                'assigned_by': assigned_by,
            })
            return assignment_id

    @staticmethod
    def get_assignments(submission_id: int = None, reviewer_id: str = None,
                        status: str = None) -> List[Dict[str, Any]]:
        """Get review assignments with optional filters.

        Args:
            submission_id: Filter by submission.
            reviewer_id: Filter by reviewer user ID.
            status: Filter by assignment status.

        Returns:
            A list of assignment dicts.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM peer_review_assignments WHERE 1=1'
            params: list = []

            if submission_id:
                query += ' AND submission_id = ?'
                params.append(submission_id)

            if reviewer_id:
                query += ' AND reviewer_id = ?'
                params.append(reviewer_id)

            if status:
                query += ' AND status = ?'
                params.append(status)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def decline_assignment(assignment_id: int) -> None:
        """Decline a review assignment.

        Sets the assignment status to 'declined'.

        Args:
            assignment_id: The assignment to decline.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE peer_review_assignments
                SET status = 'declined', updated_at = ?
                WHERE assignment_id = ?
            ''', (datetime.now().isoformat(), assignment_id))
            log_activity('update', 'peer_review_assignment', details={
                'assignment_id': assignment_id, 'action': 'declined',
            })

    @staticmethod
    def start_review(assignment_id: int) -> None:
        """Start working on a review assignment.

        Sets the assignment status to 'in_progress'.

        Args:
            assignment_id: The assignment to start.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE peer_review_assignments
                SET status = 'in_progress', updated_at = ?
                WHERE assignment_id = ?
            ''', (datetime.now().isoformat(), assignment_id))
            log_activity('update', 'peer_review_assignment', details={
                'assignment_id': assignment_id, 'action': 'started',
            })

    # ==================== FEEDBACK MANAGEMENT ====================

    @staticmethod
    def submit_feedback(assignment_id: int, submission_id: int,
                        reviewer_id: str, overall_rating: int,
                        content_quality: int, clarity: int,
                        alignment_with_outcomes: int,
                        engagement_potential: int,
                        strengths: str, improvements: str,
                        detailed_comments: str, recommendation: str,
                        is_confidential: bool = False) -> int:
        """Submit feedback for a peer review assignment.

        Records the structured feedback with multi-dimensional ratings and
        marks the associated assignment as 'completed'.

        Args:
            assignment_id: The assignment this feedback is for.
            submission_id: The submission being reviewed.
            reviewer_id: User ID of the reviewer submitting feedback.
            overall_rating: Overall rating score (e.g. 1-5).
            content_quality: Rating for content quality.
            clarity: Rating for clarity of the material.
            alignment_with_outcomes: Rating for alignment with learning outcomes.
            engagement_potential: Rating for engagement potential.
            strengths: Description of the material's strengths.
            improvements: Suggested improvements.
            detailed_comments: Detailed reviewer comments.
            recommendation: Reviewer's recommendation (e.g. 'approve',
                           'revise', 'reject').
            is_confidential: Whether this feedback is confidential
                            (default False).

        Returns:
            The ID of the newly created feedback record.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO peer_review_feedback (
                    assignment_id, submission_id, reviewer_id,
                    overall_rating, content_quality, clarity,
                    alignment_with_outcomes, engagement_potential,
                    strengths, improvements, detailed_comments,
                    recommendation, is_confidential, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                assignment_id, submission_id, reviewer_id,
                overall_rating, content_quality, clarity,
                alignment_with_outcomes, engagement_potential,
                strengths, improvements, detailed_comments,
                recommendation, int(is_confidential),
                datetime.now().isoformat(),
            ))
            feedback_id = cursor.lastrowid

            # Mark the assignment as completed
            conn.execute('''
                UPDATE peer_review_assignments
                SET status = 'completed', updated_at = ?
                WHERE assignment_id = ?
            ''', (datetime.now().isoformat(), assignment_id))

            log_activity('create', 'peer_review_feedback', details={
                'feedback_id': feedback_id,
                'assignment_id': assignment_id,
                'submission_id': submission_id,
                'reviewer_id': reviewer_id,
                'recommendation': recommendation,
            })
            return feedback_id

    @staticmethod
    def get_feedback(submission_id: int = None,
                     assignment_id: int = None) -> List[Dict[str, Any]]:
        """Get feedback records with optional filters.

        Args:
            submission_id: Filter by submission.
            assignment_id: Filter by assignment.

        Returns:
            A list of feedback dicts.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM peer_review_feedback WHERE 1=1'
            params: list = []

            if submission_id:
                query += ' AND submission_id = ?'
                params.append(submission_id)

            if assignment_id:
                query += ' AND assignment_id = ?'
                params.append(assignment_id)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_feedback_summary(submission_id: int) -> Dict[str, Any]:
        """Get a summary of all feedback for a submission.

        Calculates the average of each of the five rating dimensions,
        the total count of reviews, and a list of all recommendations.

        Args:
            submission_id: The submission to summarise feedback for.

        Returns:
            A dict containing::

                {
                    'submission_id': int,
                    'review_count': int,
                    'avg_overall_rating': float or None,
                    'avg_content_quality': float or None,
                    'avg_clarity': float or None,
                    'avg_alignment_with_outcomes': float or None,
                    'avg_engagement_potential': float or None,
                    'recommendations': list[str],
                }
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT
                    COUNT(*) AS review_count,
                    AVG(overall_rating) AS avg_overall_rating,
                    AVG(content_quality) AS avg_content_quality,
                    AVG(clarity) AS avg_clarity,
                    AVG(alignment_with_outcomes) AS avg_alignment_with_outcomes,
                    AVG(engagement_potential) AS avg_engagement_potential
                FROM peer_review_feedback
                WHERE submission_id = ?
            ''', (submission_id,)).fetchone()

            summary = dict(row) if row else {
                'review_count': 0,
                'avg_overall_rating': None,
                'avg_content_quality': None,
                'avg_clarity': None,
                'avg_alignment_with_outcomes': None,
                'avg_engagement_potential': None,
            }
            summary['submission_id'] = submission_id

            # Collect all recommendations
            rec_rows = conn.execute('''
                SELECT recommendation FROM peer_review_feedback
                WHERE submission_id = ?
            ''', (submission_id,)).fetchall()
            summary['recommendations'] = [
                dict(r)['recommendation'] for r in rec_rows
            ]

            return summary

    # ==================== RESOURCE MANAGEMENT ====================

    @staticmethod
    def share_resource(title: str, description: str, resource_type: str,
                       subject_area: str, course_code: str,
                       file_path: str, file_name: str,
                       shared_by: str) -> int:
        """Share a new resource in the peer review resource library.

        The resource is created with is_approved=0, download_count=0,
        rating_sum=0, and rating_count=0.

        Args:
            title: Title of the resource.
            description: Description of the resource.
            resource_type: Type of resource (e.g. 'template', 'rubric', 'example').
            subject_area: Subject area the resource relates to.
            course_code: Course code the resource is associated with.
            file_path: Path to the uploaded file.
            file_name: Original name of the uploaded file.
            shared_by: User ID of the person sharing the resource.

        Returns:
            The ID of the newly created resource.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO peer_review_shared_resources (
                    title, description, resource_type, subject_area,
                    course_code, file_path, file_name, shared_by,
                    is_approved, download_count, rating_sum, rating_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?)
            ''', (
                title, description, resource_type, subject_area,
                course_code, file_path, file_name, shared_by,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            resource_id = cursor.lastrowid
            log_activity('create', 'peer_review_resource', details={
                'resource_id': resource_id, 'title': title,
                'shared_by': shared_by,
            })
            return resource_id

    @staticmethod
    def get_resources(resource_type: str = None, subject_area: str = None,
                      is_approved: int = None) -> List[Dict[str, Any]]:
        """Get shared resources with optional filters.

        Args:
            resource_type: Filter by resource type.
            subject_area: Filter by subject area.
            is_approved: Filter by approval status (0 or 1).

        Returns:
            A list of resource dicts ordered by created_at descending.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM peer_review_shared_resources WHERE 1=1'
            params: list = []

            if resource_type:
                query += ' AND resource_type = ?'
                params.append(resource_type)

            if subject_area:
                query += ' AND subject_area = ?'
                params.append(subject_area)

            if is_approved is not None:
                query += ' AND is_approved = ?'
                params.append(is_approved)

            query += ' ORDER BY created_at DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_resource(resource_id: int) -> Optional[Dict[str, Any]]:
        """Get a single shared resource by ID.

        Args:
            resource_id: The resource's primary key.

        Returns:
            A dict of the resource row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM peer_review_shared_resources WHERE resource_id = ?
            ''', (resource_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def rate_resource(resource_id: int, user_id: str, rating: int,
                      comment: str = None) -> None:
        """Rate a shared resource.

        Uses INSERT OR REPLACE to upsert the rating for the given
        (resource_id, user_id) pair, enforcing the UNIQUE constraint.
        After upserting, recalculates rating_sum and rating_count on the
        resource record.

        Args:
            resource_id: The resource to rate.
            user_id: The user submitting the rating.
            rating: The rating value (e.g. 1-5).
            comment: Optional comment accompanying the rating.
        """
        with transaction() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO peer_review_resource_ratings (
                    resource_id, user_id, rating, comment, created_at
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                resource_id, user_id, rating, comment,
                datetime.now().isoformat(),
            ))

            # Recalculate rating_sum and rating_count on the resource
            row = conn.execute('''
                SELECT COALESCE(SUM(rating), 0) AS rating_sum,
                       COUNT(*) AS rating_count
                FROM peer_review_resource_ratings
                WHERE resource_id = ?
            ''', (resource_id,)).fetchone()

            totals = dict(row)
            conn.execute('''
                UPDATE peer_review_shared_resources
                SET rating_sum = ?, rating_count = ?, updated_at = ?
                WHERE resource_id = ?
            ''', (
                totals['rating_sum'], totals['rating_count'],
                datetime.now().isoformat(), resource_id,
            ))

            log_activity('update', 'peer_review_resource', details={
                'resource_id': resource_id, 'user_id': user_id,
                'action': 'rated', 'rating': rating,
            })

    @staticmethod
    def increment_download(resource_id: int) -> None:
        """Increment the download count for a shared resource.

        Args:
            resource_id: The resource that was downloaded.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE peer_review_shared_resources
                SET download_count = download_count + 1, updated_at = ?
                WHERE resource_id = ?
            ''', (datetime.now().isoformat(), resource_id))
            log_activity('update', 'peer_review_resource', details={
                'resource_id': resource_id, 'action': 'downloaded',
            })

    @staticmethod
    def approve_resource(resource_id: int) -> None:
        """Approve a shared resource for visibility.

        Sets is_approved to 1 on the resource record.

        Args:
            resource_id: The resource to approve.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE peer_review_shared_resources
                SET is_approved = 1, updated_at = ?
                WHERE resource_id = ?
            ''', (datetime.now().isoformat(), resource_id))
            log_activity('update', 'peer_review_resource', details={
                'resource_id': resource_id, 'action': 'approved',
            })

    # ==================== REPORTING ====================

    @staticmethod
    def get_cycle_statistics(cycle_id: int) -> Dict[str, Any]:
        """Get statistics for a peer review cycle.

        Calculates the total number of submissions, completed reviews,
        pending reviews, and average overall rating for the given cycle.

        Args:
            cycle_id: The cycle to generate statistics for.

        Returns:
            A dict containing::

                {
                    'cycle_id': int,
                    'total_submissions': int,
                    'completed_reviews': int,
                    'pending_reviews': int,
                    'avg_overall_rating': float or None,
                }
        """
        with get_connection() as conn:
            # Count submissions in this cycle
            sub_row = conn.execute('''
                SELECT COUNT(*) AS total_submissions
                FROM peer_review_submissions
                WHERE cycle_id = ?
            ''', (cycle_id,)).fetchone()
            total_submissions = dict(sub_row)['total_submissions']

            # Count completed reviews (assignments with status='completed')
            # for submissions in this cycle
            completed_row = conn.execute('''
                SELECT COUNT(*) AS completed_reviews
                FROM peer_review_assignments a
                JOIN peer_review_submissions s ON a.submission_id = s.submission_id
                WHERE s.cycle_id = ? AND a.status = 'completed'
            ''', (cycle_id,)).fetchone()
            completed_reviews = dict(completed_row)['completed_reviews']

            # Count pending reviews (assignments not completed or declined)
            pending_row = conn.execute('''
                SELECT COUNT(*) AS pending_reviews
                FROM peer_review_assignments a
                JOIN peer_review_submissions s ON a.submission_id = s.submission_id
                WHERE s.cycle_id = ? AND a.status NOT IN ('completed', 'declined')
            ''', (cycle_id,)).fetchone()
            pending_reviews = dict(pending_row)['pending_reviews']

            # Average overall rating from feedback for this cycle
            rating_row = conn.execute('''
                SELECT AVG(f.overall_rating) AS avg_overall_rating
                FROM peer_review_feedback f
                JOIN peer_review_submissions s ON f.submission_id = s.submission_id
                WHERE s.cycle_id = ?
            ''', (cycle_id,)).fetchone()
            avg_overall_rating = dict(rating_row)['avg_overall_rating']

            return {
                'cycle_id': cycle_id,
                'total_submissions': total_submissions,
                'completed_reviews': completed_reviews,
                'pending_reviews': pending_reviews,
                'avg_overall_rating': avg_overall_rating,
            }

    @staticmethod
    def get_reviewer_workload(reviewer_id: str = None) -> List[Dict[str, Any]]:
        """Get reviewer workload statistics.

        For each reviewer (or a specific reviewer), returns the number of
        assigned, completed, and pending review assignments.

        Args:
            reviewer_id: Optional filter for a specific reviewer. If None,
                        returns workload for all reviewers.

        Returns:
            A list of dicts, one per reviewer, containing::

                {
                    'reviewer_id': str,
                    'assigned': int,
                    'completed': int,
                    'pending': int,
                }
        """
        with get_connection() as conn:
            query = '''
                SELECT
                    reviewer_id,
                    COUNT(*) AS assigned,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN status NOT IN ('completed', 'declined') THEN 1 ELSE 0 END) AS pending
                FROM peer_review_assignments
                WHERE 1=1
            '''
            params: list = []

            if reviewer_id:
                query += ' AND reviewer_id = ?'
                params.append(reviewer_id)

            query += ' GROUP BY reviewer_id'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
