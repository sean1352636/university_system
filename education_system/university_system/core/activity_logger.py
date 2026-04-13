"""
Centralized Activity Logger for University System
Provides consistent logging across all modules with daily log rotation.

Format: User - Action - DateTime

This module is in the core package and has no dependencies on infrastructure
or modules, preventing circular imports.
"""

import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional


class ActivityLogger:
    """Centralized activity logger with daily rotation and consistent formatting."""

    _instance = None
    _current_user = None
    logger = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ActivityLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.log_dir = self._get_log_directory()
        self.logger = self._setup_logger()

    def _get_log_directory(self) -> Path:
        """Get or create the logs directory."""
        try:
            from education_system.university_system.modules.shared.constants import paths
            log_dir = paths.LOG_DIR
        except (ImportError, AttributeError):
            # Fallback to default location
            log_dir = Path(__file__).parent.parent / 'logs'

        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def _setup_logger(self) -> logging.Logger:
        """Set up the logger with daily rotation."""
        logger = logging.getLogger('UniversitySystemActivity')
        logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()

        # Daily rotating file handler
        log_file = self.log_dir / 'activity.log'
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when='midnight',
            interval=1,
            backupCount=90,  # Keep 90 days of logs
            encoding='utf-8'
        )
        handler.when = 'midnight'
        handler.interval = 1

        # Set the filename format for rotated logs: activity_YYYY-MM-DD.log
        handler.suffix = "%Y-%m-%d.log"
        handler.namer = lambda name: name.replace('.log', '')

        # Custom formatter: User - Action - DateTime
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        ActivityLogger.logger = logger

        return logger

    def set_user(self, username: str):
        """Set the current user for logging."""
        self._current_user = username

    def get_user(self) -> str:
        """Get the current user, or 'System' if not set."""
        return self._current_user or 'System'

    def log(self, action: str, user: Optional[str] = None):
        """
        Log an activity with format: User - Action - DateTime

        Args:
            action: Description of the action performed
            user: Username (optional, uses current user if not provided)
        """
        username = user or self.get_user()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        log_entry = f"{username} - {action} - {timestamp}"
        target_logger = getattr(ActivityLogger, 'logger', None) or self.logger
        try:
            target_logger.info(log_entry)
        except Exception as exc:
            import sys
            print(f"[ActivityLogger] Failed to write audit log: {exc}", file=sys.stderr)

    def log_login(self, username: str, success: bool = True):
        """Log a login attempt."""
        action = "Logged in successfully" if success else "Failed login attempt"
        self.set_user(username)
        self.log(action, username)

    def log_logout(self, username: str):
        """Log a logout."""
        self.log("Logged out", username)
        self._current_user = None

    def log_create(self, item_type: str, item_name: str = ""):
        """Log creation of an item."""
        action = f"Created {item_type}"
        if item_name:
            action += f": {item_name}"
        self.log(action)

    def log_read(self, item_type: str, item_name: str = ""):
        """Log reading/viewing of an item."""
        action = f"Viewed {item_type}"
        if item_name:
            action += f": {item_name}"
        self.log(action)

    def log_update(self, item_type: str, item_name: str = ""):
        """Log updating of an item."""
        action = f"Updated {item_type}"
        if item_name:
            action += f": {item_name}"
        self.log(action)

    def log_delete(self, item_type: str, item_name: str = ""):
        """Log deletion of an item."""
        action = f"Deleted {item_type}"
        if item_name:
            action += f": {item_name}"
        self.log(action)

    def log_search(self, search_type: str, query: str = ""):
        """Log a search operation."""
        action = f"Searched {search_type}"
        if query:
            action += f" for: {query}"
        self.log(action)

    def log_export(self, export_type: str, format: str = ""):
        """Log an export operation."""
        action = f"Exported {export_type}"
        if format:
            action += f" as {format}"
        self.log(action)

    def log_import(self, import_type: str, source: str = ""):
        """Log an import operation."""
        action = f"Imported {import_type}"
        if source:
            action += f" from {source}"
        self.log(action)

    def log_error(self, error_message: str):
        """Log an error."""
        action = f"ERROR: {error_message}"
        self.log(action)

    def log_access(self, resource: str):
        """Log access to a resource or module."""
        action = f"Accessed {resource}"
        self.log(action)

    def log_permission_denied(self, resource: str):
        """Log a permission denial."""
        action = f"Permission denied: {resource}"
        self.log(action)


# Global instance
_activity_logger = ActivityLogger()


# Convenience functions for easy importing
def set_user(username: str):
    """Set the current user for logging."""
    _activity_logger.set_user(username)


def get_user() -> str:
    """Get the current user."""
    return _activity_logger.get_user()


def log_activity(action: str, entity_type: str = None, user: Optional[str] = None, user_id: Optional[int] = None, details: dict = None):
    """
    Log a general activity.

    Args:
        action: The action type (e.g., 'create', 'update', 'delete', 'view')
        entity_type: The type of entity being acted upon (e.g., 'user', 'student_records')
        user: Username (optional)
        user_id: User ID (optional, will be ignored - for backwards compatibility)
        details: Additional details (optional, will be ignored - for backwards compatibility)
    """
    # Build action message
    if entity_type:
        action_msg = f"{action.capitalize()} {entity_type}"
    else:
        action_msg = action

    _activity_logger.log(action_msg, user)


def log_login(username: str, success: bool = True):
    """Log a login attempt."""
    _activity_logger.log_login(username, success)


def log_logout(username: str):
    """Log a logout."""
    _activity_logger.log_logout(username)


def log_create(item_type: str, item_name: str = ""):
    """Log creation of an item."""
    _activity_logger.log_create(item_type, item_name)


def log_read(item_type: str, item_name: str = ""):
    """Log reading/viewing of an item."""
    _activity_logger.log_read(item_type, item_name)


def log_update(item_type: str, item_name: str = ""):
    """Log updating of an item."""
    _activity_logger.log_update(item_type, item_name)


def log_delete(item_type: str, item_name: str = ""):
    """Log deletion of an item."""
    _activity_logger.log_delete(item_type, item_name)


def log_search(search_type: str, query: str = ""):
    """Log a search operation."""
    _activity_logger.log_search(search_type, query)


def log_export(export_type: str, format: str = ""):
    """Log an export operation."""
    _activity_logger.log_export(export_type, format)


def log_import(import_type: str, source: str = ""):
    """Log an import operation."""
    _activity_logger.log_import(import_type, source)


def log_error(error_message: str):
    """Log an error."""
    _activity_logger.log_error(error_message)


def log_access(resource: str):
    """Log access to a resource or module."""
    _activity_logger.log_access(resource)


def log_permission_denied(resource: str):
    """Log a permission denial."""
    _activity_logger.log_permission_denied(resource)


# Export the logger instance for advanced usage
logger = _activity_logger

__all__ = [
    "ActivityLogger",
    "set_user",
    "get_user",
    "log_activity",
    "log_login",
    "log_logout",
    "log_create",
    "log_read",
    "log_update",
    "log_delete",
    "log_search",
    "log_export",
    "log_import",
    "log_error",
    "log_access",
    "log_permission_denied",
    "logger",
]
