"""Split from cli_menus.py — assembled in package __init__.py."""
from __future__ import annotations

import sys
import json
import logging
import random
import secrets
import string
from pathlib import Path
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    DatabaseError,
)

logger = logging.getLogger("education_system.post_18.university_system.infrastructure.auth.cli.cli_menus")

def _save_cli_remember_token(username, token, device_fingerprint):
    """Save remember me token to file for CLI"""
    try:
        token_file = Path.home() / '.university_system' / 'cli_remember_me.json'
        token_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'username': username,
            'token': token,
            'device_fingerprint': device_fingerprint
        }

        with open(token_file, 'w') as f:
            json.dump(data, f)

        print("✅ Remember me token saved. You'll be automatically logged in next time.")

    except Exception as e:
        logging.warning(f"Failed to save remember me token: {e}")

def _load_cli_remember_token():
    """Load remember me token from file for CLI"""
    try:
        token_file = Path.home() / '.university_system' / 'cli_remember_me.json'

        if not token_file.exists():
            return None

        with open(token_file, 'r') as f:
            data = json.load(f)

        return data

    except Exception as e:
        logging.warning(f"Failed to load remember me token: {e}")
        return None

def _clear_cli_remember_token():
    """Clear remember me token from file for CLI"""
    try:
        token_file = Path.home() / '.university_system' / 'cli_remember_me.json'

        if token_file.exists():
            token_file.unlink()
            print("Remember me token cleared.")

    except Exception as e:
        logging.warning(f"Failed to clear remember me token: {e}")

def _check_cli_remember_me_token(auth):
    """Check for remember me token and auto-login if valid"""
    try:
        from education_system.post_18.university_system.infrastructure.auth.enhanced_auth import EnhancedAuth, create_enhanced_auth

        # Load saved token
        token_data = _load_cli_remember_token()
        if not token_data:
            return auth, False

        username = token_data.get('username')
        token = token_data.get('token')
        device_fingerprint = token_data.get('device_fingerprint')

        if not all([username, token, device_fingerprint]):
            return auth, False

        # Create/use EnhancedAuth
        if not isinstance(auth, EnhancedAuth):
            auth = create_enhanced_auth()

        # Verify token
        result = auth.verify_remember_me_token(
            token=token,
            device_fingerprint=device_fingerprint,
            ip_address="127.0.0.1"
        )

        if result.get('success'):
            # Update saved token if rotated
            if result.get('new_token'):
                _save_cli_remember_token(username, result['new_token'], device_fingerprint)

            print(f"\n🔓 Auto-login successful! Welcome back, {username}!")
            return auth, True
        else:
            # Token invalid or expired - clear it
            _clear_cli_remember_token()
            return auth, False

    except Exception as e:
        logging.warning(f"Remember me auto-login failed: {e}")
        return auth, False

# ============================================================================
# Main Authentication Menu
# ============================================================================

