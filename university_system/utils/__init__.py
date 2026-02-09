"""
University System Utilities Package
Provides common utility functions and error logging
"""

from university_system.utils.error_logger import (
    log_error,
    log_critical_error,
    get_error_logger,
    ErrorLogger
)

__all__ = [
    'log_error',
    'log_critical_error',
    'get_error_logger',
    'ErrorLogger'
]
