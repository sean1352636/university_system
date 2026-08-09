REQUIRED_AUTH_TABLES = frozenset({"users", "roles", "permissions"})

def missing_tables(existing_tables) -> set[str]:
    return set(REQUIRED_AUTH_TABLES) - set(existing_tables)
