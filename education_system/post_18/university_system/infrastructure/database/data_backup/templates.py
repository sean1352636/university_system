"""Backup configuration templates."""

from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.infrastructure.database.data_backup.config import config, save_config

logger = configure_logging(name=__name__)


def save_backup_template(name, settings):
    """Save backup configuration as a template"""
    try:
        if "backup_templates" not in config:
            config["backup_templates"] = {}

        config["backup_templates"][name] = settings
        save_config()
        logger.info(f"Backup template '{name}' saved")
        return True
    except (KeyError, TypeError) as e:
        logger.error(f"Error saving backup template - invalid data: {e}")
        return False


def load_backup_template(name):
    """Load backup configuration from template"""
    try:
        if name in config.get("backup_templates", {}):
            template = config["backup_templates"][name]
            # Apply template settings to current config
            for key, value in template.items():
                if key in config:
                    config[key] = value
            logger.info(f"Backup template '{name}' loaded")
            return True
        else:
            logger.error(f"Backup template '{name}' not found")
            return False
    except (KeyError, TypeError) as e:
        logger.error(f"Error loading backup template - invalid data: {e}")
        return False
