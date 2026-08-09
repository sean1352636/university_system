from .integrations import cleanup_database_on_startup, init_all_databases

def initialize_application() -> bool:
    cleanup_database_on_startup()
    return bool(init_all_databases())
