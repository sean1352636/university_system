class PlagiarismCheckerError(Exception):
    """Base exception for plagiarism checker errors"""
    pass


class DatabaseError(PlagiarismCheckerError):
    """Database-related errors"""
    pass


class FileProcessingError(PlagiarismCheckerError):
    """File processing related errors"""
    pass


class IntegrationError(PlagiarismCheckerError):
    """Integration-related errors"""
    pass
