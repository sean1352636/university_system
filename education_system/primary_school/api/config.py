"""Flask API configuration for the Primary School system."""

import os

from education_system.primary_school.core.defaults import JWT_SECRET, API_DEBUG


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("PRIMARY_SCHOOL_SECRET_KEY", JWT_SECRET)
    JWT_SECRET_KEY = JWT_SECRET
    JWT_EXPIRY_HOURS = 24
    DEBUG = API_DEBUG
    JSON_SORT_KEYS = False
