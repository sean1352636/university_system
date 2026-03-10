"""Flask API configuration for the Secondary School system."""

import os
import secrets

from education_system.secondary_school.core.defaults import API_HOST, API_PORT

JWT_SECRET = os.getenv("SCHOOL_JWT_SECRET", secrets.token_hex(32))
API_DEBUG = os.getenv("SCHOOL_API_DEBUG", "false").lower() == "true"


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SCHOOL_SECRET_KEY", JWT_SECRET)
    JWT_SECRET_KEY = JWT_SECRET
    JWT_EXPIRY_HOURS = 24
    DEBUG = API_DEBUG
    JSON_SORT_KEYS = False
