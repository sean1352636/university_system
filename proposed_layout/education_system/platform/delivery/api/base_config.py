"""Shared base API configuration for all system APIs."""

import os
import secrets


class BaseAPIConfig:
    """Base configuration shared by all system API servers."""
    JWT_EXPIRY_HOURS = 24
    JSON_SORT_KEYS = False
    DEBUG = os.getenv("API_DEBUG", "false").lower() == "true"
    SECRET_KEY = os.getenv("API_SECRET_KEY", secrets.token_hex(32))
