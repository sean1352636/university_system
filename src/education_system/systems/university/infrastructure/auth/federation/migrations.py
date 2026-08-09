def migrate_provider_config(config: dict) -> dict:
    migrated = dict(config)
    migrated.setdefault("enabled", True)
    return migrated
