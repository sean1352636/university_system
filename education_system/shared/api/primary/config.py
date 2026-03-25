"""Flask API configuration for the Primary School system."""

import os

from education_system.shared.api.base_config import BaseAPIConfig
from education_system.primary_school.core.defaults import JWT_SECRET, API_DEBUG


class Config(BaseAPIConfig):
    """Primary School-specific configuration."""
    SECRET_KEY = os.getenv("PRIMARY_SCHOOL_SECRET_KEY", JWT_SECRET)
    JWT_SECRET_KEY = JWT_SECRET
    DEBUG = API_DEBUG
