"""
Utility functions for housing accommodation GUI.

This module contains shared utility functions used across the housing GUI.
"""

from datetime import datetime
from university_system.infrastructure.database.db import get_connection
from university_system.modules.domain.housing.services.housing_accommodation import generate_id


def format_currency(amount):
    """Format amount as currency"""
    return f"£{amount:,.2f}"


def format_date(date_str):
    """Format date string consistently"""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.strptime(str(date_str), '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return str(date_str)


def validate_date(date_str, date_format='%Y-%m-%d'):
    """Validate date format"""
    try:
        datetime.strptime(date_str, date_format)
        return True
    except (ValueError, TypeError):
        return False


def get_current_timestamp():
    """Get current timestamp in standard format"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """Safely convert value to int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
