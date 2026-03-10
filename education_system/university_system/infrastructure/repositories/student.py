"""Student repository implementation.

This module provides the Student entity and its repository implementations,
abstracting database access for student data management.

Usage:
    from education_system.university_system.infrastructure.repositories.student import (
        Student,
        get_student_repository,
    )

    # Get the repository
    repo = get_student_repository()

    # Find a student
    student = repo.get_by_id("S12345")
    if student:
        print(f"Found: {student.first_name} {student.last_name}")

    # Create a new student
    new_student = Student(
        student_id="S12346",
        first_name="John",
        last_name="Doe",
        email_address="john.doe@university.edu",
        course="Computer Science",
    )
    repo.save(new_student)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

from education_system.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.university_system.infrastructure.exceptions import (
    StudentNotFoundError,
    DuplicateStudentError,
    DatabaseError,
    ValidationError,
)
from education_system.university_system.infrastructure.repositories.base import (
    Entity,
    Repository,
    QueryableRepository,
    BatchRepository,
)
from education_system.university_system.core import paths
from education_system.university_system.core.sql_safety import validate_identifier

logger = logging.getLogger(__name__)


# =============================================================================
# Student Entity
# =============================================================================

@dataclass
class Student(Entity):
    """Domain entity representing a student.

    This class represents the core student data in the university system.
    It inherits from Entity to provide identity and timestamp tracking.

    Attributes:
        student_id: The unique student identifier (e.g., "S12345").
        email_address: Student's email address.
        title: Honorific title (Mr, Ms, Dr, etc.).
        first_name: Student's first name.
        middle_name: Student's middle name (optional).
        last_name: Student's last name.
        gender: Student's gender.
        dob: Date of birth (as string, format: YYYY-MM-DD).
        age: Student's age (calculated or stored).
        course: The course/program the student is enrolled in.
        registration_datetime: When the student registered.
        status: Student status (Active, Inactive, Graduated, etc.).
        enrollment_date: Date of enrollment.
    """

    student_id: Optional[str] = None
    email_address: Optional[str] = None
    title: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None
    age: Optional[int] = None
    course: Optional[str] = None
    registration_datetime: Optional[str] = None
    status: str = "Active"
    enrollment_date: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize entity with student_id as the entity id."""
        # Use student_id as the entity id
        if self.student_id and not self.id:
            self.id = self.student_id
        elif self.id and not self.student_id:
            self.student_id = self.id
        super().__post_init__()

    @property
    def full_name(self) -> str:
        """Get the student's full name."""
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def is_active(self) -> bool:
        """Check if the student is currently active."""
        return self.status.lower() == "active"

    @classmethod
    def from_row(cls, row: Any) -> Optional["Student"]:
        """Create a Student from a database row.

        Args:
            row: A database row (sqlite3.Row or dict-like object).

        Returns:
            A Student instance, or None if row is None.
        """
        if row is None:
            return None

        # Handle both sqlite3.Row and dict
        if hasattr(row, "keys"):
            data = {k: row[k] for k in row.keys()}
        else:
            data = dict(row) if hasattr(row, "__iter__") else {}

        return cls(
            student_id=data.get("student_id"),
            email_address=data.get("email_address"),
            title=data.get("title"),
            first_name=data.get("first_name"),
            middle_name=data.get("middle_name"),
            last_name=data.get("last_name"),
            gender=data.get("gender"),
            dob=data.get("dob"),
            age=data.get("age"),
            course=data.get("course"),
            registration_datetime=data.get("registration_datetime"),
            status=data.get("status", "Active"),
            enrollment_date=data.get("enrollment_date"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert student to a dictionary for database operations."""
        return {
            "student_id": self.student_id,
            "email_address": self.email_address,
            "title": self.title,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "gender": self.gender,
            "dob": self.dob,
            "age": self.age,
            "course": self.course,
            "registration_datetime": self.registration_datetime,
            "status": self.status,
            "enrollment_date": self.enrollment_date,
        }


# =============================================================================
# Student Repository Interface
# =============================================================================

class StudentRepository(QueryableRepository[Student, str], BatchRepository[Student, str], ABC):
    """Abstract repository interface for Student entities.

    This interface defines all operations available for student data access.
    Concrete implementations (SQLite, PostgreSQL, etc.) must implement
    all these methods.

    Example:
        repo: StudentRepository = get_student_repository()
        student = repo.get_by_id("S12345")
        if student:
            student.course = "Updated Course"
            repo.save(student)
    """

    @abstractmethod
    def find_by_email(self, email: str) -> Optional[Student]:
        """Find a student by their email address.

        Args:
            email: The email address to search for.

        Returns:
            The student if found, None otherwise.
        """
        ...

    @abstractmethod
    def find_by_course(self, course: str) -> list[Student]:
        """Find all students enrolled in a specific course.

        Args:
            course: The course name to search for.

        Returns:
            List of students in the course.
        """
        ...

    @abstractmethod
    def find_by_status(self, status: str) -> list[Student]:
        """Find all students with a specific status.

        Args:
            status: The status to search for (e.g., "Active", "Inactive").

        Returns:
            List of students with the given status.
        """
        ...

    @abstractmethod
    def find_by_name(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> list[Student]:
        """Find students by name.

        Args:
            first_name: First name to search (case-insensitive).
            last_name: Last name to search (case-insensitive).

        Returns:
            List of matching students.
        """
        ...

    @abstractmethod
    def search(self, query: str) -> list[Student]:
        """Search students by a query string.

        Searches across multiple fields (name, email, course, etc.).

        Args:
            query: The search query.

        Returns:
            List of matching students.
        """
        ...


# =============================================================================
# SQLite Implementation
# =============================================================================

class SQLiteStudentRepository(StudentRepository):
    """SQLite implementation of the StudentRepository.

    This implementation uses the centralized database connection utilities
    from infrastructure.database.db to access the students table.

    Example:
        repo = SQLiteStudentRepository()
        student = repo.get_by_id("S12345")
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the repository.

        Args:
            db_path: Optional path to the database file.
                     Uses default if not specified.
        """
        self.db_path = db_path

    def get_by_id(self, student_id: str) -> Optional[Student]:
        """Retrieve a student by their ID.

        Args:
            student_id: The unique student identifier.

        Returns:
            The student if found, None otherwise.
        """
        with get_connection(db_path=self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?",
                (student_id,)
            ).fetchone()
            return Student.from_row(row)

    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> list[Student]:
        """Retrieve all students with optional pagination.

        Args:
            limit: Maximum number of students to return.
            offset: Number of students to skip.

        Returns:
            List of students.
        """
        with get_connection(db_path=self.db_path) as conn:
            if limit is not None:
                rows = conn.execute(
                    "SELECT * FROM students LIMIT ? OFFSET ?",
                    (limit, offset)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM students OFFSET ?",
                    (offset,)
                ).fetchall()
            return [Student.from_row(row) for row in rows if row]

    def save(self, student: Student) -> Student:
        """Persist a student (insert or update).

        Args:
            student: The student to persist.

        Returns:
            The persisted student.

        Raises:
            DuplicateStudentError: If inserting with an existing ID.
            ValidationError: If required fields are missing.
        """
        if not student.student_id:
            raise ValidationError("Student ID is required")

        student.mark_updated()

        try:
            with transaction(db_path=self.db_path) as conn:
                # Check if student exists
                existing = conn.execute(
                    "SELECT 1 FROM students WHERE student_id = ?",
                    (student.student_id,)
                ).fetchone()

                if existing:
                    # Update existing student
                    conn.execute(
                        """
                        UPDATE students SET
                            email_address = ?,
                            title = ?,
                            first_name = ?,
                            middle_name = ?,
                            last_name = ?,
                            gender = ?,
                            dob = ?,
                            age = ?,
                            course = ?,
                            status = ?,
                            enrollment_date = ?
                        WHERE student_id = ?
                        """,
                        (
                            student.email_address,
                            student.title,
                            student.first_name,
                            student.middle_name,
                            student.last_name,
                            student.gender,
                            student.dob,
                            student.age,
                            student.course,
                            student.status,
                            student.enrollment_date,
                            student.student_id,
                        )
                    )
                    logger.debug(f"Updated student: {student.student_id}")
                else:
                    # Insert new student
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        """
                        INSERT INTO students (
                            student_id, email_address, title, first_name,
                            middle_name, last_name, gender, dob, age,
                            course, registration_datetime, status, enrollment_date
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            student.student_id,
                            student.email_address,
                            student.title,
                            student.first_name,
                            student.middle_name,
                            student.last_name,
                            student.gender,
                            student.dob,
                            student.age,
                            student.course,
                            student.registration_datetime or now,
                            student.status,
                            student.enrollment_date,
                        )
                    )
                    logger.debug(f"Inserted new student: {student.student_id}")

            return student

        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise DuplicateStudentError(student.student_id)
            raise DatabaseError(f"Failed to save student: {e}")

    def delete(self, student_id: str) -> bool:
        """Delete a student by their ID.

        Args:
            student_id: The student ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        try:
            with transaction(db_path=self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM students WHERE student_id = ?",
                    (student_id,)
                )
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.debug(f"Deleted student: {student_id}")
                return deleted
        except Exception as e:
            raise DatabaseError(f"Failed to delete student: {e}")

    def exists(self, student_id: str) -> bool:
        """Check if a student exists.

        Args:
            student_id: The student ID to check.

        Returns:
            True if the student exists.
        """
        with get_connection(db_path=self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?",
                (student_id,)
            ).fetchone()
            return row is not None

    def count(self) -> int:
        """Count all students.

        Returns:
            The total number of students.
        """
        with get_connection(db_path=self.db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM students").fetchone()
            return row[0] if row else 0

    def find_by(self, **criteria: Any) -> list[Student]:
        """Find students matching criteria.

        Args:
            **criteria: Field-value pairs to match.

        Returns:
            List of matching students.
        """
        if not criteria:
            return self.get_all()

        conditions = []
        values = []
        for field, value in criteria.items():
            if value is not None:
                safe_field = validate_identifier(field, "column")
                conditions.append(safe_field + " = ?")
                values.append(value)

        if not conditions:
            return self.get_all()

        query = "SELECT * FROM students WHERE " + " AND ".join(conditions)

        with get_connection(db_path=self.db_path) as conn:
            rows = conn.execute(query, values).fetchall()
            return [Student.from_row(row) for row in rows if row]

    def find_one_by(self, **criteria: Any) -> Optional[Student]:
        """Find a single student matching criteria.

        Args:
            **criteria: Field-value pairs to match.

        Returns:
            The first matching student, or None.
        """
        results = self.find_by(**criteria)
        return results[0] if results else None

    def save_many(self, students: Iterable[Student]) -> list[Student]:
        """Save multiple students at once.

        Args:
            students: Iterable of students to save.

        Returns:
            List of saved students.
        """
        saved = []
        for student in students:
            saved.append(self.save(student))
        return saved

    def delete_many(self, student_ids: Iterable[str]) -> int:
        """Delete multiple students at once.

        Args:
            student_ids: Iterable of student IDs to delete.

        Returns:
            Number of students deleted.
        """
        deleted_count = 0
        for student_id in student_ids:
            if self.delete(student_id):
                deleted_count += 1
        return deleted_count

    def find_by_email(self, email: str) -> Optional[Student]:
        """Find a student by email address.

        Args:
            email: The email address to search for.

        Returns:
            The student if found, None otherwise.
        """
        with get_connection(db_path=self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM students WHERE email_address = ?",
                (email,)
            ).fetchone()
            return Student.from_row(row)

    def find_by_course(self, course: str) -> list[Student]:
        """Find all students in a course.

        Args:
            course: The course name.

        Returns:
            List of students in the course.
        """
        with get_connection(db_path=self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM students WHERE course = ?",
                (course,)
            ).fetchall()
            return [Student.from_row(row) for row in rows if row]

    def find_by_status(self, status: str) -> list[Student]:
        """Find students by status.

        Args:
            status: The status to search for.

        Returns:
            List of students with that status.
        """
        with get_connection(db_path=self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM students WHERE status = ?",
                (status,)
            ).fetchall()
            return [Student.from_row(row) for row in rows if row]

    def find_by_name(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> list[Student]:
        """Find students by name.

        Args:
            first_name: First name to search (case-insensitive).
            last_name: Last name to search (case-insensitive).

        Returns:
            List of matching students.
        """
        conditions = []
        values = []

        if first_name:
            conditions.append("LOWER(first_name) = LOWER(?)")
            values.append(first_name)

        if last_name:
            conditions.append("LOWER(last_name) = LOWER(?)")
            values.append(last_name)

        if not conditions:
            return []

        query = "SELECT * FROM students WHERE " + " AND ".join(conditions)

        with get_connection(db_path=self.db_path) as conn:
            rows = conn.execute(query, values).fetchall()
            return [Student.from_row(row) for row in rows if row]

    def search(self, query: str) -> list[Student]:
        """Search students across multiple fields.

        Args:
            query: The search query.

        Returns:
            List of matching students.
        """
        search_pattern = f"%{query}%"

        sql = """
            SELECT * FROM students
            WHERE first_name LIKE ?
               OR last_name LIKE ?
               OR email_address LIKE ?
               OR student_id LIKE ?
               OR course LIKE ?
        """

        with get_connection(db_path=self.db_path) as conn:
            rows = conn.execute(
                sql,
                (search_pattern,) * 5
            ).fetchall()
            return [Student.from_row(row) for row in rows if row]


# =============================================================================
# Repository Factory
# =============================================================================

# Default repository instance (singleton pattern)
_default_repository: Optional[StudentRepository] = None


def get_student_repository(
    db_path: Optional[str] = None,
    implementation: str = "sqlite",
) -> StudentRepository:
    """Get a StudentRepository instance.

    Factory function that returns a StudentRepository implementation.
    By default, returns a SQLite implementation using the global database.

    Args:
        db_path: Optional database path override.
        implementation: Repository implementation to use ("sqlite").

    Returns:
        A StudentRepository instance.

    Example:
        repo = get_student_repository()
        student = repo.get_by_id("S12345")
    """
    global _default_repository

    # If using default path and SQLite, return cached instance
    if db_path is None and implementation == "sqlite":
        if _default_repository is None:
            _default_repository = SQLiteStudentRepository()
        return _default_repository

    # Create new instance with custom settings
    if implementation == "sqlite":
        return SQLiteStudentRepository(db_path=db_path)
    else:
        raise ValueError(f"Unknown repository implementation: {implementation}")


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Entity
    "Student",
    # Repository interface
    "StudentRepository",
    # Implementations
    "SQLiteStudentRepository",
    # Factory
    "get_student_repository",
]
