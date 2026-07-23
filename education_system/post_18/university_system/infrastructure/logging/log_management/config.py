"""Configuration management for the log system."""

import os
import json
import secrets

# i18n support
try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, **kwargs):
        """Fallback translation function"""
        return key


class LogConfig:
    """Configuration management for the log system"""

    def __init__(self):
        from education_system.post_18.university_system.core import paths
        self.config_file = str(paths.LOG_DIR / "log_config.json")
        self.default_config = {
            "retention_days": 90,
            "auto_archive_days": 30,
            "max_log_size_mb": 100,
            "enable_real_time": True,
            "enable_alerts": True,
            "alert_email": "",
            "smtp_server": "",
            "smtp_port": 587,
            "smtp_username": "",
            "smtp_password": "",
            "enable_encryption": True,
            "api_enabled": False,
            "api_secret_key": os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32)),
            "webhook_secret": "webhook-secret-key-change-this",
            "max_search_results": 1000,
            "enable_analytics": True,
            "chart_export_format": "png"
        }
        self.load_config()

    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = {**self.default_config, **json.load(f)}
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = self.default_config.copy()

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value
        self.save_config()


# Create global config instance
config = LogConfig()
