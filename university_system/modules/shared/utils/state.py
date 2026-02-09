"""
Global state management for the university system.

This module provides a centralized location for maintaining
global state across the application, particularly for:
- Authentication state
- User session information
- System configuration
"""

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
def get_auth():
    """Get the current authentication instance."""
    return auth

def set_config(key, value):
    """Set a configuration value."""
    global config
    config[key] = value

def get_config(key, default=None):
    """Get a configuration value."""
    return config.get(key, default)

def initialize_state():
    """Initialize the global state."""
    global app_state
    from datetime import datetime

    app_state['initialized'] = True
    app_state['startup_time'] = datetime.now()

def is_initialized():
    """Check if the system state is initialized."""
    return app_state.get('initialized', False)

def reset_state():
    """Reset all global state (useful for testing)."""
    global auth, config, app_state

    auth = None
    config = {}
    app_state = {
        'initialized': False,
        'startup_time': None,
        'debug_mode': False
    }