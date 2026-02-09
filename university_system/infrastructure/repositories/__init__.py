"""Repository pattern implementation for the university system.

This package provides an abstraction layer over database access, implementing
the Repository pattern to decouple business logic from data persistence.

Benefits:
- Testability: Repositories can be mocked for unit tests
- Flexibility: Different storage backends can be swapped
- Consistency: Centralized data access patterns
- Maintainability: Clear separation of concerns

Usage:
    from university_system.infrastructure.repositories import (
        StudentRepository,
        get_student_repository,
    )

    # Get the default repository (SQLite)
    repo = get_student_repository()

    # Find a student
    student = repo.get_by_id("S12345")

    # Save a student
    repo.save(student)

    # Query students
    students = repo.find_by_course("Computer Science")
"""

from university_system.infrastructure.repositories.base import (
    Repository,
    Entity,
)
from university_system.infrastructure.repositories.student import (
    Student,
    StudentRepository,
    SQLiteStudentRepository,
    get_student_repository,
)

__all__ = [
    # Base classes
    "Repository",
    "Entity",
    # Student repository
    "Student",
    "StudentRepository",
    "SQLiteStudentRepository",
    "get_student_repository",
]
