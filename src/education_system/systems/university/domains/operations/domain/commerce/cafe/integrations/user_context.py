from education_system.systems.university.domains.operations.domain.commerce.cafe import *  # noqa: F401,F403

def set_auth(auth_instance: Any) -> None:
    """Set the global auth instance for cafe CLI."""
    global auth
    auth = auth_instance
    if HAS_AUTH:
        set_auth_instance(auth_instance)
        try:
            set_shared_auth(auth_instance)
        except Exception as e:
            logger.warning(f"Failed to set auth in shared_context: {e}")

