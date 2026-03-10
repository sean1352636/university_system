"""Configuration management for data backup GUI."""
import json
import threading

from education_system.university_system.modules.shared.gui.database.shared_imports import (
    BACKUP_DIR, logger,
)

# Initialize basic config if not available
config = {
    "backup_directory": str(BACKUP_DIR),
    "scheduled_backup_time": "02:00",
    "backup_frequency": "daily",
    "max_backups": 10,
    "auto_backup_enabled": True,
    # Security settings
    "encryption_enabled": False,
    "encryption_password": "",
    "secure_deletion": False,
    "verify_integrity": True,
    # Compression settings
    "compression_enabled": True,
    "compression_format": "gzip",  # gzip, zip
    "compression_level": 6,
    # Cloud storage settings
    "cloud_enabled": False,
    "cloud_provider": "aws",  # aws, google, azure
    "aws_bucket": "",
    "aws_access_key": "",
    "aws_secret_key": "",
    "aws_region": "us-east-1",
    # Remote storage settings
    "remote_enabled": False,
    "remote_type": "ftp",  # ftp, sftp
    "remote_host": "",
    "remote_username": "",
    "remote_password": "",
    "remote_path": "/backups",
    # Backup types
    "backup_type": "full",  # full, incremental, differential
    "enable_incremental": False,
    "enable_selective": False,
    "selective_tables": [],
    # Notifications
    "email_notifications": False,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "email_username": "",
    "email_password": "",
    "notification_recipients": [],
    "slack_webhook": "",
    "discord_webhook": "",
    # Storage management
    "storage_quota_gb": 10,
    "enable_deduplication": False,
    # Advanced features
    "cron_schedule": "",
    "enable_change_detection": False,
    "parallel_backup": False,
    "max_threads": 4,
    "bandwidth_limit_mbps": 0,  # 0 = unlimited
    # Retention policies
    "retention_policy": {
        "daily_keep": 7,
        "weekly_keep": 4,
        "monthly_keep": 12,
        "yearly_keep": 5
    },
    # Validation
    "auto_validate": False,
    "validation_frequency": "weekly",
    # Export settings
    "export_formats": ["csv", "json", "xml"],
    # Templates
    "backup_templates": {}
}

_cron_schedule_lock = threading.Lock()
_next_cron_run = None

# Thread-safe incremental/differential backup context
_last_incremental_context = {}
_last_differential_context = {}
_backup_context_lock = threading.Lock()

# Scheduler state
scheduler_thread = None
scheduler_running = False

# Configuration for GUI preferences
GUI_CONFIG = {
    "auto_start_gui": True,
    "remember_window_size": True,
    "theme": "default",
    "show_splash": True,
    "minimize_to_tray": False,
    "auto_refresh_interval": 30000  # milliseconds
}


def save_config():
    """Save configuration to file"""
    try:
        with open("backup_config.json", "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Could not save config: {e}")

def load_config():
    """Load configuration from file"""
    global config
    try:
        with open("backup_config.json", "r") as f:
            loaded_config = json.load(f)
            config.update(loaded_config)
    except FileNotFoundError:
        save_config()  # Create default config
    except Exception as e:
        print(f"Could not load config: {e}")

def save_gui_config():
    """Save GUI-specific configuration"""
    try:
        with open("gui_config.json", "w") as f:
            json.dump(GUI_CONFIG, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save GUI config: {e}")

def load_gui_config():
    """Load GUI-specific configuration"""
    global GUI_CONFIG
    try:
        import os
        if os.path.exists("gui_config.json"):
            with open("gui_config.json", "r") as f:
                loaded_config = json.load(f)
                GUI_CONFIG.update(loaded_config)
    except Exception as e:
        logger.error(f"Failed to load GUI config: {e}")
