from typing import Dict, Optional
from .config import CalendarConfig


# Factory function for easy setup
def create_calendar_manager(db_file: str = None,
                          config_overrides: Optional[Dict] = None):
    """Factory function to create a properly configured calendar manager"""
    from .calendar_core import AcademicCalendarManager

    # Create configuration
    config = CalendarConfig()
    if config_overrides:
        for key, value in config_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

    config.db_file = db_file

    # Create and return calendar manager
    return AcademicCalendarManager(config=config)
