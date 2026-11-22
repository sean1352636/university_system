"""REST API interface for the Secondary School system.

Holds this system's own route blueprints. The shared API platform
(`education_system.platform.delivery.api`) hosts and mounts them under
``/api/v1/school``. The pre-rebuild routes are in ``remove/`` (they called the
old secondary domain, which no longer exists).
"""
