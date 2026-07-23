"""
Batch Operations API for the University System.

Provides support for bulk administrative operations with proper
transaction handling, progress tracking, and error reporting.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction, DEFAULT_DB_PATH
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.i18n import get_text, _

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class BatchStatus(Enum):
    """Status of a batch operation."""
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    PARTIALLY_COMPLETED = 'partially_completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


@dataclass
class OperationResult:
    """Result of a single operation within a batch."""
    success: bool
    id: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Any] = None
    duration_ms: float = 0.0


@dataclass
class BatchResult:
    """Result of a batch operation."""
    batch_id: str
    status: BatchStatus
    total: int
    succeeded: int
    failed: int
    results: List[OperationResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.succeeded / self.total) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            'batch_id': self.batch_id,
            'status': self.status.value,
            'total': self.total,
            'succeeded': self.succeeded,
            'failed': self.failed,
            'success_rate': round(self.success_rate, 2),
            'duration_seconds': round(self.duration_seconds, 2),
            'errors': self.errors[:10],  # Limit errors in response
        }


@dataclass
class EnrollmentRequest:
    """Request to enroll a student in a course."""
    student_id: str
    course_id: str
    semester: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GradeUpdateRequest:
    """Request to update a student's grade."""
    student_id: str
    course_id: str
    grade: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BatchSizeExceeded(Exception):
    """Exception raised when batch size limit is exceeded."""

    def __init__(self, message: str, max_size: int, requested_size: int):
        super().__init__(message)
        self.max_size = max_size
        self.requested_size = requested_size


class BatchOperations:
    """
    Handles bulk administrative operations with proper error handling.

    Example:
        >>> batch = BatchOperations()
        >>>
        >>> # Bulk enrollment
        >>> enrollments = [
        ...     EnrollmentRequest(student_id='S001', course_id='C101'),
        ...     EnrollmentRequest(student_id='S002', course_id='C101'),
        ... ]
        >>> result = batch.bulk_enroll(enrollments)
        >>> print(f"Enrolled: {result.succeeded}/{result.total}")
    """

    MAX_BATCH_SIZE = 1000
    DEFAULT_BATCH_SIZE = 100

    def __init__(
        self,
        db_path: Optional[str] = None,
        max_batch_size: int = MAX_BATCH_SIZE,
    ):
        """
        Initialize batch operations handler.

        Args:
            db_path: Database path
            max_batch_size: Maximum items per batch
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.max_batch_size = max_batch_size
        self._batch_counter = 0
        self._lock = threading.Lock()

        logger.info(f"BatchOperations initialized, max_batch_size: {max_batch_size}")

    def _generate_batch_id(self) -> str:
        """Generate unique batch ID."""
        with self._lock:
            self._batch_counter += 1
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            return f"batch_{timestamp}_{self._batch_counter}"

    def _validate_batch_size(self, items: List[Any], operation_name: str) -> None:
        """Validate batch size is within limits."""
        if len(items) > self.max_batch_size:
            raise BatchSizeExceeded(
                f"Batch size {len(items)} exceeds maximum {self.max_batch_size} for {operation_name}",
                max_size=self.max_batch_size,
                requested_size=len(items),
            )

    def bulk_enroll(
        self,
        enrollments: List[EnrollmentRequest],
        stop_on_error: bool = False,
    ) -> BatchResult:
        """
        Bulk enroll students in courses.

        Args:
            enrollments: List of enrollment requests
            stop_on_error: Stop processing on first error

        Returns:
            BatchResult with individual operation results
        """
        self._validate_batch_size(enrollments, 'bulk_enroll')

        batch_id = self._generate_batch_id()
        start_time = datetime.now()
        results = []
        succeeded = 0
        failed = 0
        errors = []

        logger.info(f"Starting bulk enrollment: {batch_id}, {len(enrollments)} items")

        with get_connection(self.db_path) as conn:
            for enrollment in enrollments:
                op_start = time.perf_counter()
                result = self._process_enrollment(conn, enrollment)
                result.duration_ms = (time.perf_counter() - op_start) * 1000

                results.append(result)

                if result.success:
                    succeeded += 1
                else:
                    failed += 1
                    if result.error:
                        errors.append(f"{enrollment.student_id}: {result.error}")

                    if stop_on_error:
                        break

            conn.commit()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        status = BatchStatus.COMPLETED
        if failed > 0:
            status = BatchStatus.PARTIALLY_COMPLETED if succeeded > 0 else BatchStatus.FAILED

        # Log activity
        log_activity('bulk_enroll', 'enrollment', details={
            'batch_id': batch_id,
            'total': len(enrollments),
            'succeeded': succeeded,
            'failed': failed,
        })

        logger.info(
            f"Bulk enrollment completed: {batch_id}, "
            f"succeeded: {succeeded}, failed: {failed}, duration: {duration:.2f}s"
        )

        return BatchResult(
            batch_id=batch_id,
            status=status,
            total=len(enrollments),
            succeeded=succeeded,
            failed=failed,
            results=results,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            errors=errors,
        )

    def _process_enrollment(
        self,
        conn,
        enrollment: EnrollmentRequest,
    ) -> OperationResult:
        """Process a single enrollment."""
        try:
            # Check if already enrolled
            cursor = conn.execute('''
                SELECT id FROM enrollments
                WHERE student_id = ? AND course_id = ?
            ''', (enrollment.student_id, enrollment.course_id))

            if cursor.fetchone():
                return OperationResult(
                    success=False,
                    id=enrollment.student_id,
                    error='Already enrolled',
                )

            # Check course capacity
            cursor = conn.execute('''
                SELECT capacity,
                       (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id) as enrolled
                FROM courses c
                WHERE c.id = ? OR c.code = ?
            ''', (enrollment.course_id, enrollment.course_id))

            course = cursor.fetchone()
            if not course:
                return OperationResult(
                    success=False,
                    id=enrollment.student_id,
                    error='Course not found',
                )

            capacity = course[0] if course[0] else float('inf')
            enrolled = course[1] or 0
            if enrolled >= capacity:
                return OperationResult(
                    success=False,
                    id=enrollment.student_id,
                    error='Course is full',
                )

            # Insert enrollment
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            semester = enrollment.semester or self._get_current_semester()

            cursor = conn.execute('''
                INSERT INTO enrollments (student_id, course_id, semester, enrolled_at, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (enrollment.student_id, enrollment.course_id, semester, timestamp))

            return OperationResult(
                success=True,
                id=str(cursor.lastrowid),
                data={'student_id': enrollment.student_id, 'course_id': enrollment.course_id},
            )

        except Exception as e:
            return OperationResult(
                success=False,
                id=enrollment.student_id,
                error=str(e),
            )

    def bulk_grade_update(
        self,
        updates: List[GradeUpdateRequest],
        stop_on_error: bool = False,
    ) -> BatchResult:
        """
        Bulk update student grades.

        Args:
            updates: List of grade update requests
            stop_on_error: Stop processing on first error

        Returns:
            BatchResult with individual operation results
        """
        self._validate_batch_size(updates, 'bulk_grade_update')

        batch_id = self._generate_batch_id()
        start_time = datetime.now()
        results = []
        succeeded = 0
        failed = 0
        errors = []

        logger.info(f"Starting bulk grade update: {batch_id}, {len(updates)} items")

        with get_connection(self.db_path) as conn:
            for update in updates:
                op_start = time.perf_counter()
                result = self._process_grade_update(conn, update)
                result.duration_ms = (time.perf_counter() - op_start) * 1000

                results.append(result)

                if result.success:
                    succeeded += 1
                else:
                    failed += 1
                    if result.error:
                        errors.append(f"{update.student_id}/{update.course_id}: {result.error}")

                    if stop_on_error:
                        break

            conn.commit()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        status = BatchStatus.COMPLETED
        if failed > 0:
            status = BatchStatus.PARTIALLY_COMPLETED if succeeded > 0 else BatchStatus.FAILED

        log_activity('bulk_grade_update', 'grades', details={
            'batch_id': batch_id,
            'total': len(updates),
            'succeeded': succeeded,
            'failed': failed,
        })

        logger.info(
            f"Bulk grade update completed: {batch_id}, "
            f"succeeded: {succeeded}, failed: {failed}, duration: {duration:.2f}s"
        )

        return BatchResult(
            batch_id=batch_id,
            status=status,
            total=len(updates),
            succeeded=succeeded,
            failed=failed,
            results=results,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            errors=errors,
        )

    def _process_grade_update(
        self,
        conn,
        update: GradeUpdateRequest,
    ) -> OperationResult:
        """Process a single grade update."""
        try:
            # Validate grade
            valid_grades = {'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'I', 'W', 'P', 'NP'}
            if update.grade.upper() not in valid_grades:
                return OperationResult(
                    success=False,
                    id=f"{update.student_id}_{update.course_id}",
                    error=f'Invalid grade: {update.grade}',
                )

            # Check enrollment exists
            cursor = conn.execute('''
                SELECT id FROM enrollments
                WHERE student_id = ? AND course_id = ?
            ''', (update.student_id, update.course_id))

            enrollment = cursor.fetchone()
            if not enrollment:
                return OperationResult(
                    success=False,
                    id=f"{update.student_id}_{update.course_id}",
                    error='No enrollment found',
                )

            # Update or insert grade
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor = conn.execute('''
                SELECT id FROM grades
                WHERE student_id = ? AND course_id = ?
            ''', (update.student_id, update.course_id))

            existing = cursor.fetchone()
            if existing:
                conn.execute('''
                    UPDATE grades
                    SET grade = ?, updated_at = ?
                    WHERE student_id = ? AND course_id = ?
                ''', (update.grade.upper(), timestamp, update.student_id, update.course_id))
            else:
                conn.execute('''
                    INSERT INTO grades (student_id, course_id, grade, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (update.student_id, update.course_id, update.grade.upper(), timestamp, timestamp))

            return OperationResult(
                success=True,
                id=f"{update.student_id}_{update.course_id}",
                data={'grade': update.grade.upper()},
            )

        except Exception as e:
            return OperationResult(
                success=False,
                id=f"{update.student_id}_{update.course_id}",
                error=str(e),
            )

    def bulk_user_status_update(
        self,
        user_ids: List[int],
        is_active: bool,
    ) -> BatchResult:
        """
        Bulk update user active status.

        Args:
            user_ids: List of user IDs to update
            is_active: New active status

        Returns:
            BatchResult with operation results
        """
        self._validate_batch_size(user_ids, 'bulk_user_status_update')

        batch_id = self._generate_batch_id()
        start_time = datetime.now()
        results = []
        succeeded = 0
        failed = 0
        errors = []

        logger.info(f"Starting bulk user status update: {batch_id}, {len(user_ids)} users")

        with get_connection(self.db_path) as conn:
            for user_id in user_ids:
                op_start = time.perf_counter()

                try:
                    cursor = conn.execute(
                        "UPDATE user_accounts SET is_active = ? WHERE user_id = ?",
                        (1 if is_active else 0, user_id)
                    )

                    if cursor.rowcount > 0:
                        results.append(OperationResult(
                            success=True,
                            id=str(user_id),
                            duration_ms=(time.perf_counter() - op_start) * 1000,
                        ))
                        succeeded += 1
                    else:
                        results.append(OperationResult(
                            success=False,
                            id=str(user_id),
                            error='User not found',
                            duration_ms=(time.perf_counter() - op_start) * 1000,
                        ))
                        failed += 1
                        errors.append(f"User {user_id}: Not found")

                except Exception as e:
                    results.append(OperationResult(
                        success=False,
                        id=str(user_id),
                        error=str(e),
                        duration_ms=(time.perf_counter() - op_start) * 1000,
                    ))
                    failed += 1
                    errors.append(f"User {user_id}: {str(e)}")

            conn.commit()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        status = BatchStatus.COMPLETED
        if failed > 0:
            status = BatchStatus.PARTIALLY_COMPLETED if succeeded > 0 else BatchStatus.FAILED

        log_activity('bulk_user_status_update', 'user', details={
            'batch_id': batch_id,
            'total': len(user_ids),
            'succeeded': succeeded,
            'failed': failed,
            'new_status': 'active' if is_active else 'inactive',
        })

        return BatchResult(
            batch_id=batch_id,
            status=status,
            total=len(user_ids),
            succeeded=succeeded,
            failed=failed,
            results=results,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            errors=errors,
        )

    def bulk_delete_enrollments(
        self,
        enrollment_ids: List[int],
    ) -> BatchResult:
        """
        Bulk delete enrollments.

        Args:
            enrollment_ids: List of enrollment IDs to delete

        Returns:
            BatchResult with operation results
        """
        self._validate_batch_size(enrollment_ids, 'bulk_delete_enrollments')

        batch_id = self._generate_batch_id()
        start_time = datetime.now()
        results = []
        succeeded = 0
        failed = 0
        errors = []

        logger.info(f"Starting bulk enrollment deletion: {batch_id}, {len(enrollment_ids)} items")

        with get_connection(self.db_path) as conn:
            for enrollment_id in enrollment_ids:
                op_start = time.perf_counter()

                try:
                    cursor = conn.execute(
                        "DELETE FROM enrollments WHERE id = ?",
                        (enrollment_id,)
                    )

                    if cursor.rowcount > 0:
                        results.append(OperationResult(
                            success=True,
                            id=str(enrollment_id),
                            duration_ms=(time.perf_counter() - op_start) * 1000,
                        ))
                        succeeded += 1
                    else:
                        results.append(OperationResult(
                            success=False,
                            id=str(enrollment_id),
                            error='Enrollment not found',
                            duration_ms=(time.perf_counter() - op_start) * 1000,
                        ))
                        failed += 1

                except Exception as e:
                    results.append(OperationResult(
                        success=False,
                        id=str(enrollment_id),
                        error=str(e),
                        duration_ms=(time.perf_counter() - op_start) * 1000,
                    ))
                    failed += 1
                    errors.append(f"Enrollment {enrollment_id}: {str(e)}")

            conn.commit()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        status = BatchStatus.COMPLETED
        if failed > 0:
            status = BatchStatus.PARTIALLY_COMPLETED if succeeded > 0 else BatchStatus.FAILED

        log_activity('bulk_delete', 'enrollment', details={
            'batch_id': batch_id,
            'total': len(enrollment_ids),
            'succeeded': succeeded,
            'failed': failed,
        })

        return BatchResult(
            batch_id=batch_id,
            status=status,
            total=len(enrollment_ids),
            succeeded=succeeded,
            failed=failed,
            results=results,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            errors=errors,
        )

    def _get_current_semester(self) -> str:
        """Get current semester string."""
        now = datetime.now()
        year = now.year
        month = now.month

        if month >= 8:
            return f"Fall {year}"
        elif month >= 5:
            return f"Summer {year}"
        elif month >= 1:
            return f"Spring {year}"
        return f"Fall {year - 1}"


__all__ = [
    'BatchOperations',
    'BatchResult',
    'BatchStatus',
    'OperationResult',
    'EnrollmentRequest',
    'GradeUpdateRequest',
    'BatchSizeExceeded',
]
