"""Names the plagiarism screens import. The old standalone demo (which
signed in as the first user in the database), sample-document writers and
setup routines are in ``remove/``; the rules are in
``university/application/integrity/plagiarism_checks`` and ``integrity_*``."""

from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.domains.integrity.domain.plagiarism.exceptions import (  # noqa: E501
    DatabaseError,
    FileProcessingError,
    IntegrationError,
    PlagiarismCheckerError,
)
from education_system.systems.university.domains.integrity.domain.plagiarism.checker import (  # noqa: E501
    PlagiarismChecker,
)

logger = configure_logging(name=__name__)

__all__ = ["PlagiarismChecker", "PlagiarismCheckerError", "DatabaseError",
           "FileProcessingError", "IntegrationError", "logger"]
