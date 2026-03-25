"""Flask API configuration for the College system."""

import os

from education_system.shared.api.base_config import BaseAPIConfig
from education_system.college_system.core.defaults import JWT_SECRET, API_DEBUG


class Config(BaseAPIConfig):
    """College-specific configuration."""
    SECRET_KEY = os.getenv("COLLEGE_SECRET_KEY", JWT_SECRET)
    JWT_SECRET_KEY = JWT_SECRET
    DEBUG = API_DEBUG
