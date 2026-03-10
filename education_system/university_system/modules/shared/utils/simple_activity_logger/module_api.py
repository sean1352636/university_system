import json
from typing import Dict, List, Any

from .models import LogLevel, SecurityLevel
from .logger import EnhancedActivityLogger
from .plugins.base import LoggerPlugin, PluginManager


# Create singleton instance with plugin support
logger = EnhancedActivityLogger()
plugin_manager = PluginManager()


# Module-level log_activity function for direct imports
def log_activity(user_id, username, role, action, module, details=None, status="success", **kwargs):
    """
    Module-level wrapper for the logger's log_activity method
    """
    return logger.log_activity(
        user_id, username, role, action, module,
        details, status, **kwargs
    )


# Helper functions for backward compatibility
def log_login(user_id, username, role, status="success", details=None):
    """Log a user login attempt"""
    return logger.log_activity(
        user_id, username, role, "login", "authentication",
        details, status, LogLevel.INFO, SecurityLevel.LOW
    )

def log_logout(user_id, username, role):
    """Log a user logout"""
    return logger.log_activity(
        user_id, username, role, "logout", "authentication",
        status="success", log_level=LogLevel.INFO
    )

def log_dynamic_activity(action, module, details=None, **kwargs):
    """
    Log an activity dynamically within a function
    """
    # Simplified user context (no auth imports)
    user_id = 'system'
    username = 'system'
    role = 'system'

    return logger.log_activity(user_id, username, role, action, module, details, **kwargs)


# Configuration management
def load_logger_config(config_path: str):
    """Load logger configuration from file"""
    global logger
    if logger:
        logger.shutdown()
    logger = EnhancedActivityLogger(config_path)

def get_logger_instance() -> EnhancedActivityLogger:
    """Get the singleton logger instance"""
    return logger

def register_plugin(plugin: LoggerPlugin):
    """Register a plugin with the logger"""
    plugin_manager.register_plugin(plugin)

def unregister_plugin(plugin_class: str):
    """Unregister a plugin by class name"""
    plugin_manager.unregister_plugin(plugin_class)

def get_plugin_status() -> List[Dict[str, Any]]:
    """Get status of all registered plugins"""
    return plugin_manager.get_plugin_status()


# Utility functions
def create_default_config(output_path: str = 'logger_config.json'):
    """Create a default configuration file"""
    default_config = {
        "log_dir": "enhanced_logs",
        "min_log_level": "INFO",
        "output_formats": ["json", "database"],
        "queue_size": 10000,
        "batch_size": 100,
        "flush_interval": 5,
        "encrypt_logs": False,
        "enable_pii_detection": True,
        "security": {
            "max_failed_attempts": 5,
            "lockout_window": 15,
            "max_requests_per_minute": 100,
            "sensitive_actions": [
                "delete", "modify_permissions", "create_admin",
                "export_data", "system_config"
            ],
            "privileged_roles": ["admin", "superuser", "root"]
        },
        "rotation": {
            "max_file_size": 100 * 1024 * 1024,
            "retention_days": 30,
            "compress_old_logs": True
        },
        "cloud": {
            "enabled_services": [],
            "webhook_url": None,
            "elasticsearch": {
                "url": "http://localhost:9200",
                "index": "activity-logs"
            }
        },
        "security_alerts": {
            "webhook_enabled": False,
            "webhook_url": None
        }
    }

    with open(output_path, 'w') as f:
        json.dump(default_config, f, indent=2)

    print(f"Default configuration created at: {output_path}")
    return output_path
