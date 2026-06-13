"""Backup template operations."""
import json

from education_system.university_system.modules.shared.gui.database.shared_imports import (
    BACKUP_TEMPLATES_DIR, USER_BACKUP_TEMPLATES_DIR, logger,
)
from education_system.university_system.modules.shared.gui.database.config import config, save_config


def list_backup_templates():
    """List all available backup templates from JSON files and config"""
    templates = {}

    try:
        # Load shipped seeds first, then user-saved templates (user overrides seeds by name)
        for templates_dir in (BACKUP_TEMPLATES_DIR, USER_BACKUP_TEMPLATES_DIR):
            if not templates_dir.exists():
                continue
            for template_file in templates_dir.glob("*.json"):
                try:
                    with open(template_file, 'r') as f:
                        template_data = json.load(f)
                        template_name = template_data.get("name", template_file.stem.replace('_', ' ').title())
                        templates[template_name] = {
                            "source": "file",
                            "path": str(template_file),
                            "description": template_data.get("description", "No description available")
                        }
                except Exception as e:
                    logger.error(f"Error loading template from {template_file}: {e}")

        # Also include templates from config (backward compatibility)
        config_templates = config.get("backup_templates", {})
        for name in config_templates:
            if name not in templates:
                templates[name] = {
                    "source": "config",
                    "description": "User-created template"
                }

    except Exception as e:
        logger.error(f"Error listing backup templates: {e}")

    return templates

def save_backup_template(name, settings):
    """Save backup configuration as a template to JSON file"""
    try:
        # Save to both config (backward compatibility) and JSON file
        if "backup_templates" not in config:
            config["backup_templates"] = {}

        config["backup_templates"][name] = settings.copy()
        save_config()

        # Also save to JSON file in the user-writable templates dir
        USER_BACKUP_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        template_file = USER_BACKUP_TEMPLATES_DIR / f"{name.lower().replace(' ', '_')}.json"

        template_data = settings.copy()
        template_data["name"] = name

        with open(template_file, 'w') as f:
            json.dump(template_data, f, indent=2)

        logger.info(f"Template '{name}' saved to {template_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving backup template: {e}")
        return False

def load_backup_template(name):
    """Load backup configuration from template (JSON file or config)"""
    try:
        # Try user-saved templates first, then fall back to shipped seeds
        filename = f"{name.lower().replace(' ', '_')}.json"
        for template_file in (USER_BACKUP_TEMPLATES_DIR / filename, BACKUP_TEMPLATES_DIR / filename):
            if template_file.exists():
                with open(template_file, 'r') as f:
                    template = json.load(f)
                    # Remove 'name' and 'description' fields before updating config
                    template_settings = {k: v for k, v in template.items()
                                       if k not in ['name', 'description']}
                    config.update(template_settings)
                    save_config()
                    logger.info(f"Template '{name}' loaded from {template_file}")
                    return True

        # Fallback: try to load from config (backward compatibility)
        templates = config.get("backup_templates", {})
        if name in templates:
            template = templates[name]
            config.update(template)
            save_config()
            logger.info(f"Template '{name}' loaded from config")
            return True

        logger.warning(f"Template '{name}' not found")
        return False

    except Exception as e:
        logger.error(f"Error loading backup template: {e}")
        return False
