from education_system.post_18.university_system.modules.domain.academics.services.plagiarism.exceptions import (
    PlagiarismCheckerError,
    DatabaseError,
    FileProcessingError,
    IntegrationError,
)
from education_system.post_18.university_system.modules.domain.academics.services.plagiarism.checker import PlagiarismChecker
from education_system.post_18.university_system.modules.domain.academics.services.plagiarism.db import get_safe_db_connection

__all__ = [
    "PlagiarismChecker",
    "PlagiarismCheckerError",
    "DatabaseError",
    "FileProcessingError",
    "IntegrationError",
    "get_safe_db_connection",
]
