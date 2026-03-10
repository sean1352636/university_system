"""Configuration loading and encryption key management."""

import json
import os
import secrets
from typing import Dict

from education_system.university_system.utils.ai.university_chatbot.fallbacks import Fernet


def load_config(config_path: str) -> Dict:
    """Load configuration from file"""
    default_config = {
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "university_db"
        },
        "email": {
            "smtp_server": "smtp.university.edu",
            "smtp_port": 587,
            "username": "chatbot@university.edu",
            "password": ""
        },
        "sms": {
            "api_key": "",
            "service_url": ""
        },
        "security": {
            "jwt_secret": secrets.token_hex(32),
            "session_timeout": 3600,
            "max_login_attempts": 3
        },
        "nlp": {
            "model_name": "distilbert-base-uncased",
            "confidence_threshold": 0.7
        },
        "features": {
            "voice_enabled": True,
            "push_notifications": True,
            "analytics_enabled": True
        },
        "voice": {
            "sample_rate": 16000,
            "chunk_size": 1024,
            "threshold": 500,
            "silence_limit": 2,
            "language": "en-US"
        }
    }

    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
            return {**default_config, **config}
    else:
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config


def load_or_generate_encryption_key() -> bytes:
    """Load or generate encryption key"""
    key_path = "encryption.key"
    if os.path.exists(key_path):
        with open(key_path, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, 'wb') as f:
            f.write(key)
        return key
