"""REST API interface for the University system.

Holds this system's own route blueprints. The shared API platform
(`education_system.platform.delivery.api`) remains responsible for hosting,
middleware, router registration and common protocol support; the routes it
registers live here, with the system that owns them.
"""
