def migrate_legacy_user(auth, *args, **kwargs):
    return auth._migrate_legacy_to_shared(*args, **kwargs)
