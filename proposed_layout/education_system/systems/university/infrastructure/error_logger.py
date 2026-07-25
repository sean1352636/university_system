#!/usr/bin/env python3
"""
Error Logging Utility Module
Provides centralized error logging functionality for the University Management System
"""

import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json


class ErrorLogger:
    """Centralized error logging class for the University Management System"""

    def __init__(self, log_directory: str = "logs", log_filename: str = "error_log.txt"):
        """
        Initialize the ErrorLogger

        Args:
            log_directory: Directory to store log files
            log_filename: Name of the error log file
        """
        self.log_directory = Path(log_directory)
        self.log_filename = log_filename
        self.log_file_path = self.log_directory / self.log_filename

        # Create logs directory if it doesn't exist
        self.log_directory.mkdir(parents=True, exist_ok=True)

        # Setup logging configuration
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging configuration"""
        # Create a logger using module name for consistency
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.ERROR)

        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create file handler
        file_handler = logging.FileHandler(self.log_file_path, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.ERROR)

        # Create console handler for all errors
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.ERROR)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None,
                  file_path: Optional[str] = None, function_name: Optional[str] = None):
        """
        Log an error with detailed information

        Args:
            error: The exception that occurred
            context: Additional context information
            file_path: The file where the error occurred
            function_name: The function where the error occurred
        """
        try:
            # Get caller information if not provided
            if file_path is None or function_name is None:
                frame = sys._getframe(1)
                if file_path is None:
                    file_path = frame.f_code.co_filename
                if function_name is None:
                    function_name = frame.f_code.co_name

            # Create error entry
            error_entry = {
                'timestamp': datetime.now().isoformat(),
                'error_type': type(error).__name__,
                'error_message': str(error),
                'file_path': file_path,
                'function_name': function_name,
                'line_number': getattr(error, 'lineno', 'unknown'),
                'traceback': traceback.format_exc(),
                'context': context or {}
            }

            # Format log message
            log_message = self._format_error_message(error_entry)

            # Log to file
            self.logger.error(log_message)

            # Also write detailed JSON entry to a separate file
            self._write_json_log(error_entry)

        except Exception as logging_error:
            # Fallback logging in case the logger itself fails
            fallback_message = f"LOGGING ERROR: {logging_error}\nORIGINAL ERROR: {error}"
            print(fallback_message, file=sys.stderr)
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()} | LOGGING_ERROR | {fallback_message}\n")

    def _format_error_message(self, error_entry: Dict[str, Any]) -> str:
        """Format error message for logging"""
        return (
            f"ERROR: {error_entry['error_type']}: {error_entry['error_message']} "
            f"in {os.path.basename(error_entry['file_path'])}:{error_entry['function_name']}() "
            f"at line {error_entry['line_number']}"
        )

    def _write_json_log(self, error_entry: Dict[str, Any]):
        """Write detailed error entry to JSON log file"""
        json_log_path = self.log_directory / "error_log_detailed.json"

        try:
            # Read existing entries
            if json_log_path.exists():
                with open(json_log_path, 'r', encoding='utf-8') as f:
                    try:
                        entries = json.load(f)
                    except json.JSONDecodeError:
                        entries = []
            else:
                entries = []

            # Add new entry
            entries.append(error_entry)

            # Keep only last 1000 entries to prevent file from growing too large
            if len(entries) > 1000:
                entries = entries[-1000:]

            # Write back to file
            with open(json_log_path, 'w', encoding='utf-8') as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Failed to write JSON log: {e}")

    def log_critical_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Log a critical error that might cause system shutdown"""
        self.log_error(error, context)
        self.logger.critical(f"CRITICAL ERROR: {type(error).__name__}: {error}")

    def get_error_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get a summary of errors from the last N days

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with error statistics
        """
        json_log_path = self.log_directory / "error_log_detailed.json"

        if not json_log_path.exists():
            return {"total_errors": 0, "error_types": {}, "files_with_errors": {}}

        try:
            with open(json_log_path, 'r', encoding='utf-8') as f:
                entries = json.load(f)

            # Filter entries from last N days
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)

            recent_entries = [
                entry for entry in entries
                if datetime.fromisoformat(entry['timestamp']) >= cutoff_date
            ]

            # Generate summary
            summary = {
                "total_errors": len(recent_entries),
                "error_types": {},
                "files_with_errors": {},
                "functions_with_errors": {}
            }

            for entry in recent_entries:
                error_type = entry['error_type']
                file_path = os.path.basename(entry['file_path'])
                function_name = entry['function_name']

                summary["error_types"][error_type] = summary["error_types"].get(error_type, 0) + 1
                summary["files_with_errors"][file_path] = summary["files_with_errors"].get(file_path, 0) + 1
                summary["functions_with_errors"][function_name] = summary["functions_with_errors"].get(function_name, 0) + 1

            return summary

        except Exception as e:
            self.logger.error(f"Failed to generate error summary: {e}")
            return {"error": f"Failed to generate summary: {e}"}


# Global error logger instance
_error_logger = None

def get_error_logger() -> ErrorLogger:
    """Get the global error logger instance"""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger

def log_error(error: Exception, context: Optional[Dict[str, Any]] = None,
              file_path: Optional[str] = None, function_name: Optional[str] = None):
    """Convenience function to log an error"""
    logger = get_error_logger()
    logger.log_error(error, context, file_path, function_name)

def log_critical_error(error: Exception, context: Optional[Dict[str, Any]] = None):
    """Convenience function to log a critical error"""
    logger = get_error_logger()
    logger.log_critical_error(error, context)